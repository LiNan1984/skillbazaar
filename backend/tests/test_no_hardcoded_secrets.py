"""S-01: no plaintext LLM API keys in backend source.

The GLM key used to be hardcoded in agents/nodes.py (and a few services).
It must come from environment variables instead. The previously committed
keys are considered leaked and must be rotated on the platform side.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SK_PREFIX_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
# Assembled at runtime so this guard file itself contains no literal key.
LEGACY_KEY_FRAGMENT = "sk-" + "bV3"


def _iter_python_sources():
    for path in BACKEND_DIR.rglob("*.py"):
        # Skip the test suite itself and any fixtures/data files.
        if path.name == Path(__file__).name:
            continue
        if "fixtures" in path.parts:
            continue
        yield path


class TestNoHardcodedSecrets(unittest.TestCase):
    def test_no_plaintext_llm_api_key_in_source(self):
        offenders = []
        for path in _iter_python_sources():
            source = path.read_text(encoding="utf-8")
            if LEGACY_KEY_FRAGMENT in source or SK_PREFIX_RE.search(source):
                offenders.append(str(path.relative_to(BACKEND_DIR)))
        self.assertEqual(
            offenders, [],
            f"发现明文 API key，必须改为环境变量读取: {offenders}",
        )

        nodes_source = (BACKEND_DIR / "agents" / "nodes.py").read_text(encoding="utf-8")
        self.assertIn(
            "environ", nodes_source,
            "agents/nodes.py 必须通过 os.environ/os.getenv 读取 LLM_API_KEY",
        )
        self.assertNotIn(
            'LLM_API_KEY = "sk-', nodes_source,
            "agents/nodes.py 不允许再用 sk- 字面量赋值 LLM_API_KEY",
        )
        self.assertRegex(
            nodes_source,
            r'LLM_API_KEY\s*=\s*os\.(environ\.get|getenv)\(',
            "agents/nodes.py 的 LLM_API_KEY 必须来自环境变量",
        )


if __name__ == "__main__":
    unittest.main()
