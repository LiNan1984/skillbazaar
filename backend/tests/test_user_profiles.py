"""User profiles v4 integration tests against the real FastAPI app.

Covers spec 4.4: public profiles, profile editing, follows, user products.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database as db_mod

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestUserProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str, nickname: str = "") -> dict:
        username = f"up_{suffix}"
        nick = nickname or f"用户_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": nick},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"],
                "nickname": nick, "username": username}

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 描述",
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_public_profile_defaults(self):
        """Public profile should have sensible defaults for new users."""
        user = self._register("public_defaults", "Alice")
        r = self.client.get(f"/api/u/{user['username']}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["id"], user["id"])
        self.assertEqual(data["username"], user["username"])
        self.assertEqual(data["display_name"], user["nickname"])
        self.assertFalse(data["verified"])
        self.assertEqual(data["followers_count"], 0)
        self.assertEqual(data["following_count"], 0)
        self.assertFalse(data["is_following"])

    def test_update_profile(self):
        """Authenticated user can update their profile."""
        user = self._register("update_prof", "Bob")
        r = self.client.patch(
            "/api/profile/me",
            json={
                "display_name": "Bob Updated",
                "bio": "I love AI skills",
                "location": "Beijing",
                "website_url": "https://example.com",
                "social_links": [{"platform": "twitter", "url": "https://x.com/bob"}],
                "interests": ["prompt", "automation"],
                "city": "Beijing",
            },
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["display_name"], "Bob Updated")
        self.assertEqual(data["bio"], "I love AI skills")
        self.assertEqual(data["location"], "Beijing")
        self.assertEqual(data["website_url"], "https://example.com")
        self.assertEqual(len(data["social_links"]), 1)
        self.assertEqual(len(data["interests"]), 2)
        self.assertEqual(data["city"], "Beijing")

        # Verify via GET
        r2 = self.client.get(f"/api/u/{user['username']}")
        self.assertEqual(r2.status_code, 200, r2.text)
        d2 = r2.json()
        self.assertEqual(d2["display_name"], "Bob Updated")
        self.assertEqual(d2["bio"], "I love AI skills")

    def test_update_profile_unauth(self):
        """Unauthenticated users get 401 on profile update."""
        r = self.client.patch("/api/profile/me", json={"bio": "hacker"})
        self.assertEqual(r.status_code, 401, r.text)

    def test_follow_unfollow_flow(self):
        """Two users can follow/unollow each other."""
        alice = self._register("follow_a", "Alice")
        bob = self._register("follow_b", "Bob")

        # Alice follows Bob
        r = self.client.post(
            f"/api/u/{bob['username']}/follow",
            headers=_auth(alice["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["is_following"])

        # Verify from Alice's perspective
        r = self.client.get(f"/api/u/{bob['username']}", headers=_auth(alice["token"]))
        self.assertTrue(r.json()["is_following"])

        # Followers count
        r = self.client.get(f"/api/u/{bob['username']}/followers")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["total"], 1)

        # Unfollow
        r = self.client.delete(
            f"/api/u/{bob['username']}/follow",
            headers=_auth(alice["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["is_following"])

        # Count back to 0
        r = self.client.get(f"/api/u/{bob['username']}/followers")
        self.assertEqual(r.json()["total"], 0)

    def test_cannot_follow_self(self):
        """User cannot follow themselves."""
        user = self._register("self_follow", "Charlie")
        r = self.client.post(
            f"/api/u/{user['username']}/follow",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 400, r.text)

    def test_followers_list_pagination(self):
        """Followers list supports pagination."""
        alice = self._register("follow_pag", "Alice")
        followers = [self._register(f"flw_{i}", f"Follower_{i}") for i in range(5)]

        for f in followers:
            self.client.post(
                f"/api/u/{alice['username']}/follow",
                headers=_auth(f["token"]),
            )

        r = self.client.get(
            f"/api/u/{alice['username']}/followers",
            params={"page": 1, "page_size": 2},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["pages"], 3)

    def test_following_list(self):
        """Following list works correctly."""
        alice = self._register("following_l", "Alice")
        bob = self._register("following_b", "Bob")
        charlie = self._register("following_c", "Charlie")

        # Alice follows Bob and Charlie
        for target in [bob, charlie]:
            self.client.post(
                f"/api/u/{target['username']}/follow",
                headers=_auth(alice["token"]),
            )

        r = self.client.get(f"/api/u/{alice['username']}/following")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)

    def test_user_products(self):
        """User products endpoint shows published items."""
        seller = self._register("seller_prod", "Seller")
        buyer = self._register("buyer_prod", "Buyer")

        pid1 = self._publish(seller["nickname"], "Skill A", price=100)
        pid2 = self._publish(seller["nickname"], "Skill B", price=200)

        r = self.client.get(f"/api/u/{seller['username']}/products")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        names = {item["name"] for item in data["items"]}
        self.assertIn("Skill A", names)
        self.assertIn("Skill B", names)

    def test_get_my_profile(self):
        """GET /api/profile/me returns current user profile."""
        user = self._register("my_profile", "MyProfile")
        r = self.client.get("/api/profile/me", headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["id"], user["id"])
        self.assertEqual(data["username"], user["username"])

    def test_get_my_profile_unauth(self):
        """Unauthenticated user gets 401 for /api/profile/me."""
        r = self.client.get("/api/profile/me")
        self.assertEqual(r.status_code, 401, r.text)

    def test_404_for_nonexistent_user(self):
        """GET public profile for nonexistent user returns 404."""
        r = self.client.get("/api/u/nonexistent_user_xyz_123")
        self.assertEqual(r.status_code, 404, r.text)

    def test_follow_notification_created(self):
        """Following a user creates a notification for the target."""
        alice = self._register("follow_notif", "Alice")
        bob = self._register("follow_notif_b", "Bob")

        self.client.post(
            f"/api/u/{bob['username']}/follow",
            headers=_auth(alice["token"]),
        )

        r = self.client.get(
            "/api/v2/notifications",
            headers=_auth(bob["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        notifs = r.json()["notifications"]
        self.assertTrue(any(n["type"] == "follow" for n in notifs))

    def test_display_name_sync_to_users(self):
        """Updating display_name updates the users.nickname field."""
        user = self._register("display_sync", "Eve")
        self.client.patch(
            "/api/profile/me",
            json={"display_name": "New Name"},
            headers=_auth(user["token"]),
        )
        r = self.client.get(f"/api/u/{user['username']}")
        self.assertEqual(r.json()["display_name"], "New Name")


if __name__ == "__main__":
    unittest.main()
