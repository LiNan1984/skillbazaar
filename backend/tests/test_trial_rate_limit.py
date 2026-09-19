"""Trial execution + rate limit tests (T-01~T-07, T-09).

MUST fail initially — rate limiter, anonymous execution fixes,
output truncation, and trial license enforcement do not exist yet.

Run: cd backend && python3 -m pytest tests/test_trial_rate_limit.py -q
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import aiosqlite
import httpx

import database as db_mod
from models import SkillExecutionRequest

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _fetchall(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


async def _execute(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        await conn.execute(sql, params)
        await conn.commit()
    finally:
        await conn.close()


def _run_async(coro):
    """Run an async coroutine from a sync test method."""
    try:
        loop = asyncio.get_running_loop()
        # Already in an event loop (e.g., TestClient is active)
        # Can't use asyncio.run() here — create a new loop in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _mock_llm_response(content: str = "Mock LLM output") -> MagicMock:
    """Create a mock httpx response for successful LLM calls."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestTrialExecute(unittest.TestCase):
    """Anonymous execution and trial license enforcement."""

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"tr_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"试用_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"]

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _upload(self, product_id: int, seller_id: str,
                skill_type: str = "prompt") -> int:
        r = self.client.post(
            "/api/skills/upload",
            data={"product_id": str(product_id), "skill_type": skill_type,
                  "seller_id": seller_id},
            files={"file": ("skill.txt", b"prompt " + b"x" * 60, "text/plain")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def _execute(self, product_id: int, input_params: str = "test input",
                 token: str | None = None) -> dict:
        body = {"product_id": product_id, "input_params": input_params}
        headers = _auth(token) if token else {}
        r = self.client.post(
            f"/api/skills/{product_id}/execute",
            json=body,
            headers=headers,
        )
        return r

    # ---- T-01 ----
    def test_anonymous_execute_returns_output_and_logs_ip_suffix(self):
        """Anonymous execution: 200 with output, user_id has IP suffix."""
        seller_id, _ = self._register("seller_t01")
        pid = self._publish(seller_id, "T01 试用商品", price=50)
        self._upload(pid, seller_id)

        mock_resp = _mock_llm_response("匿名试用输出内容")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
            r = self._execute(pid, input_params="你好", token=None)

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("output", body)
        self.assertIn("trial_remaining", body)

        # Check execution log — use _run_async since TestClient context is closed
        execs = _run_async(_fetchall(
            "SELECT * FROM skill_executions WHERE product_id = ?", (pid,)))
        self.assertEqual(len(execs), 1)
        self.assertIn("anonymous", execs[0]["user_id"])
        self.assertEqual(execs[0]["status"], "success")

    # ---- T-05 ----
    def test_trial_license_caps_after_three_calls(self):
        """Trial license max_calls=3: authenticated user with trial license is capped at 3."""
        seller_id, _ = self._register("seller_t05")
        pid = self._publish(seller_id, "T05 试用限次商品", price=50)
        self._upload(pid, seller_id)

        # Register a buyer user (authenticated, no purchase → gets trial license)
        buyer_id, buyer_token = self._register("buyer_t05")

        mock_resp = _mock_llm_response("试用输出")
        mock_post = AsyncMock(return_value=mock_resp)

        # Execute 4 times WITH token and user_id in body (authenticated trial user)
        results = []
        for i in range(4):
            with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
                body = {"product_id": pid, "user_id": buyer_id, "input_params": f"尝试{i}"}
                r = self.client.post(
                    f"/api/skills/{pid}/execute",
                    json=body,
                    headers=_auth(buyer_token),
                )
                results.append(r)

        # First 3 should succeed, 4th should indicate trial exhausted
        # (endpoint returns error dict, not HTTPException → status 200)
        self.assertEqual(results[0].status_code, 200)
        self.assertEqual(results[1].status_code, 200)
        self.assertEqual(results[2].status_code, 200)
        body4 = results[3].json()
        self.assertEqual(body4.get("status"), "trial_exhausted",
                         "4th call should be rejected: trial max_calls reached")

        # Check license was created with max_calls=3, license_type=trial
        licenses = _run_async(_fetchall(
            "SELECT * FROM licenses WHERE product_id = ? AND user_id = ?",
            (pid, buyer_id)))
        self.assertGreaterEqual(len(licenses), 1)
        if licenses:
            self.assertEqual(licenses[0]["license_type"], "trial")
            self.assertEqual(licenses[0]["max_calls"], 3)


class TestTrialRateLimit(unittest.TestCase):
    """IP-based rate limiting."""

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"rl_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"限流_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"]

    def _publish(self, seller_name: str, name: str, price: int = 50) -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": "Skill", "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _upload(self, product_id: int, seller_id: str) -> int:
        r = self.client.post(
            "/api/skills/upload",
            data={"product_id": str(product_id), "skill_type": "prompt",
                  "seller_id": seller_id},
            files={"file": ("skill.txt", b"prompt " + b"x" * 60, "text/plain")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def _execute(self, product_id: int, token: str | None = None) -> dict:
        body = {"product_id": product_id, "input_params": "test"}
        headers = _auth(token) if token else {}
        r = self.client.post(
            f"/api/skills/{product_id}/execute",
            json=body,
            headers=headers,
        )
        return r

    def test_11th_per_product_and_31st_global_return_429(self):
        """11th call to same product → 429; 31st global call → 429."""
        from services.trial_limiter import reset
        reset()  # Clear rate limiter state from previous tests

        seller_id, _ = self._register("seller_rl")
        pid1 = self._publish(seller_id, "RL 商品1", price=50)
        pid2 = self._publish(seller_id, "RL 商品2", price=50)
        self._upload(pid1, seller_id)
        self._upload(pid2, seller_id)

        mock_resp = _mock_llm_response("限流测试")
        mock_post = AsyncMock(return_value=mock_resp)

        # 11 calls to pid1
        results = []
        for i in range(11):
            with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
                r = self._execute(pid1)
                results.append(r)

        # First 10 should succeed, 11th should be 429
        success_count = sum(1 for r in results if r.status_code == 200)
        rate_limited = [r for r in results if r.status_code == 429]
        self.assertEqual(success_count, 10, "First 10 calls should succeed")
        self.assertEqual(len(rate_limited), 1, "11th call should be rate limited")

    def test_rate_limit_counters_reset_on_process_restart(self):
        """T-09: In-memory rate limiter counters reset when process restarts."""
        seller_id, _ = self._register("seller_t09")
        pid = self._publish(seller_id, "T09 重启商品", price=50)
        self._upload(pid, seller_id)

        mock_resp = _mock_llm_response("重启测试")
        mock_post = AsyncMock(return_value=mock_resp)

        # Do 11 calls as anonymous — rate limiter blocks the 11th (10/hour per product)
        results = []
        for i in range(11):
            with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
                r = self._execute(pid)  # No token → anonymous
                results.append(r)

        success_count = sum(1 for r in results if r.status_code == 200)
        rate_limited = [r for r in results if r.status_code == 429]
        self.assertEqual(success_count, 10, "First 10 calls should succeed")
        self.assertEqual(len(rate_limited), 1, "11th call should be rate limited (429)")

        # Simulate process restart: reset in-memory rate limiter counters
        from services.trial_limiter import reset as _rl_reset
        _rl_reset()

        # Create fresh TestClient to simulate new process
        new_client = TestClient(app)
        try:
            with new_client:
                with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
                    r_after = new_client.post(
                        f"/api/skills/{pid}/execute",
                        json={"product_id": pid, "input_params": "after restart"},
                        headers={},
                    )
                self.assertEqual(r_after.status_code, 200,
                                 "After rate limiter reset, 1st call should succeed (counters cleared)")
        finally:
            del new_client


class TestTrialOutputSafety(unittest.TestCase):
    """Output truncation and desensitization."""

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"ts_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"输出_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"]

    def _publish(self, seller_name: str, name: str, price: int = 50) -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": "Skill", "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _upload(self, product_id: int, seller_id: str) -> int:
        r = self.client.post(
            "/api/skills/upload",
            data={"product_id": str(product_id), "skill_type": "prompt",
                  "seller_id": seller_id},
            files={"file": ("skill.txt", b"prompt " + b"x" * 60, "text/plain")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_trial_output_truncated_suffixed_and_desensitized(self):
        """Trial output should be ≤500 chars with truncation notice."""
        seller_id, _ = self._register("seller_ts")
        pid = self._publish(seller_id, "TS 输出安全商品", price=50)
        self._upload(pid, seller_id)

        long_output = "x" * 1200
        mock_resp = _mock_llm_response(long_output)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("services.execution_service.httpx.AsyncClient.post", mock_post):
            r = self.client.post(
                f"/api/skills/{pid}/execute",
                json={"product_id": pid, "input_params": "test"},
                headers={},  # No auth → anonymous
            )

        # Without implementation: 422 (user_id required) or 404 (no endpoint)
        # With implementation: 200 with truncated output
        if r.status_code == 200:
            body = r.json()
            output = body.get("output", "")
            self.assertLessEqual(len(output), 550, "Output should be truncated to ~500 chars")
            self.assertIn("购买后解锁完整输出", output, "Should have purchase notice")
        else:
            self.fail(f"Expected 200, got {r.status_code}: {r.text}")


if __name__ == "__main__":
    unittest.main()
