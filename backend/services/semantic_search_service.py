"""Semantic Search service v4.5.

Implements a simple in-memory cosine-similarity search using deterministic
hash-based embeddings.  No external ML library or vector DB is required.
"""
from __future__ import annotations

import hashlib
import math
import re

import database as db
from models import ProductResponse


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zA-Z0-9一-鿿]+")


def _text_to_embedding(text: str, dim: int = 128) -> list[float]:
    """Convert *text* into a deterministic sparse embedding vector.

    Strategy
    --------
    1. Lowercase and split the text into tokens (alphanumeric + CJK).
    2. For each token, hash it (MD5) and use the digest bytes as indices into
       the *dim*-length vector.  Multiple tokens can map to the same index,
       in which case the count is accumulated.
    3. L2-normalise the resulting vector so cosine similarity reduces to a
       simple dot-product.
    """
    vec = [0.0] * dim
    tokens = _WORD_RE.findall(text.lower())
    if not tokens:
        return vec

    for token in tokens:
        # Use full MD5 digest for index selection; spread across the vector.
        h = hashlib.md5(token.encode("utf-8")).digest()
        # Take 4 bytes at a time to get multiple indices per token
        for i in range(0, len(h), 4):
            idx = int.from_bytes(h[i : i + 4], "big") % dim
            vec[idx] += 1.0

    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity between two already-normalised vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # Vectors are pre-normalised so no division needed; guard against zero.
    return dot if abs(dot) <= 1.0 else 1.0 if dot > 0 else -1.0


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------

async def index_all_products() -> int:
    """Generate and persist embeddings for all active products that lack one.

    Returns the number of products newly indexed.
    """
    # Fetch all active products
    products, _ = await db.fetch_products(page=1, page_size=10000)

    indexed = 0
    for product in products:
        pid = product["id"]
        existing = await db.get_product_embedding(pid)
        if existing is not None:
            continue

        # Build a text blob from searchable fields
        name = product.get("name", "")
        desc = product.get("description", "")
        tags_raw = product.get("tags", "[]")
        try:
            tags_list = __import__("json").loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        except Exception:
            tags_list = []
        tags_text = " ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)
        blob = f"{name} {desc} {tags_text} {product.get('category', '')} {product.get('sub_category', '') or ''}"

        embedding = _text_to_embedding(blob)
        await db.save_product_embedding(pid, embedding)
        indexed += 1

    return indexed


async def search_by_text(query: str, limit: int = 10) -> list[dict]:
    """Semantic search: convert *query* to an embedding, rank all indexed
    products by cosine similarity, and return the top *limit* results.

    Each result dict contains:
        product_id, name, description, category, price, seller_name,
        rating, downloads, sales, score
    """
    all_embeddings = await db.get_all_product_embeddings()
    if not all_embeddings:
        # Lazy index: generate embeddings for all products on first search
        indexed = await index_all_products()
        if indexed > 0:
            all_embeddings = await db.get_all_product_embeddings()
    if not all_embeddings:
        return []

    query_vec = _text_to_embedding(query)
    if not any(query_vec):
        return []

    # Score every indexed product
    scored: list[tuple[float, dict]] = []
    for entry in all_embeddings:
        sim = _cosine_similarity(query_vec, entry["embedding"])
        scored.append((sim, entry))

    # Sort descending by similarity
    scored.sort(key=lambda t: t[0], reverse=True)

    top = scored[:limit]

    # Fetch product details in one shot
    ids = [entry["product_id"] for _, entry in top]
    if not ids:
        return []

    # Build result — fetch each product individually (simple, works with
    # the existing DB helpers).  For larger datasets use a single IN query.
    results: list[dict] = []
    for score_val, entry in top:
        product = await db.fetch_product_by_id(entry["product_id"])
        if not product or product.get("status") != "active":
            continue
        result = {
            "product_id": product["id"],
            "name": product["name"],
            "description": product["description"],
            "category": product["category"],
            "price": product["price"],
            "seller_name": product["seller_name"],
            "rating": product.get("rating", 0),
            "downloads": product.get("downloads", 0),
            "sales": product.get("sales", 0),
            "score": round(score_val, 4),
        }
        results.append(result)

    return results[:limit]
