# Skill Reviews & Ratings — v4.13 Feature Spec

## 1. Overview

Add a comprehensive reviews and ratings system for purchased products. This addresses the buyer pain point of "孤立决策" (isolated decision-making) by providing social proof through verified purchaser reviews, helpful voting, and rating summaries.

## 2. Problem Statement

**Buyer Pain Point #9**: "缺乏社区参考 — 孤立决策"

- Buyers have no way to see other users' real experiences with a Skill before purchasing
- Only purchase count and a basic score are shown — no written reviews, no Q&A
- Decisions are made in isolation without social proof
- Buyers who purchased a Skill have no channel to share feedback or help others

**Current State**:
- Basic rating and download count displayed on product cards
- No written reviews, no review listing, no helpful voting
- No way for buyers to share experiences
- No review management for users

**Goal**: Enable verified purchasers to write reviews (1-5 stars + text), vote on review helpfulness, and view aggregated rating summaries — creating social proof that drives conversion.

## 3. Scope

### In Scope
- Create review with rating (1-5 stars), title, and content (verified purchasers only)
- List product reviews with pagination and sorting
- "Helpful/Unhelpful" voting on reviews
- Review summary: average rating, distribution breakdown, recent reviews
- My reviews: users can view, edit, and delete their own reviews
- One review per user per product (enforced by unique constraint)
- Verified purchase badge on reviews

### Out of Scope
- Review moderation/flagging
- Seller responses to reviews
- Review photos/videos
- Q&A section
- Review incentivization

## 4. Database Schema

### 4.1 New table: `reviews`

```sql
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    is_verified_purchase INTEGER DEFAULT 1,
    helpful_count INTEGER DEFAULT 0,
    unhelpful_count INTEGER DEFAULT 0,
    is_edited INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE(product_id, user_id)
);
```

### 4.2 New table: `review_votes`

```sql
CREATE TABLE review_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    vote TEXT NOT NULL CHECK (vote IN ('helpful', 'unhelpful')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (review_id) REFERENCES reviews(id),
    UNIQUE(review_id, user_id)
);
```

### 4.3 Product table updates

Add review aggregate columns to `products` table for efficient summary queries:

```sql
ALTER TABLE products ADD COLUMN avg_rating REAL DEFAULT 0;
ALTER TABLE products ADD COLUMN review_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_1_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_2_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_3_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_4_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_5_count INTEGER DEFAULT 0;
```

> **Note**: These denormalized columns are maintained by trigger or service layer on review create/update/delete, enabling fast summary queries without aggregating the reviews table each time.

## 5. API Endpoints

### 5.1 POST `/api/v4/reviews`

Create a review for a purchased product.

**Auth**: Required (must be a verified purchaser)
**Request**:
```json
{
    "product_id": 42,
    "rating": 5,
    "title": "非常实用的 Skill",
    "content": "用了两周，提升了我的工作效率..."
}
```

**Response** (201):
```json
{
    "id": 1,
    "product_id": 42,
    "user_id": "user_abc",
    "username": "johndoe",
    "rating": 5,
    "title": "非常实用的 Skill",
    "content": "用了两周，提升了我的工作效率...",
    "is_verified_purchase": true,
    "helpful_count": 0,
    "unhelpful_count": 0,
    "is_edited": false,
    "created_at": "2026-09-19T10:00:00",
    "updated_at": "2026-09-19T10:00:00"
}
```

**Error Responses**:
- `400`: Rating must be 1-5, title/content too long
- `403`: Not a purchaser of this product
- `409`: Already reviewed this product
- `404`: Product not found

**Business Rules**:
- User must have at least one completed purchase for the product
- One review per user per product (enforced by DB unique constraint)
- Rating must be integer 1-5
- Title max 100 chars, content max 2000 chars
- `is_verified_purchase` is automatically set to true

---

### 5.2 GET `/api/v4/products/{id}/reviews`

List reviews for a product with pagination and sorting.

**Auth**: Optional (public endpoint)
**Query Params**:
- `page` (default: 1) — page number
- `limit` (default: 10, max: 50) — items per page
- `sort` (default: "helpful") — "helpful" | "recent" | "rating_high" | "rating_low"
- `rating` (optional) — filter by rating (1-5)

**Response** (200):
```json
{
    "reviews": [
        {
            "id": 1,
            "user_id": "user_abc",
            "username": "johndoe",
            "avatar_url": "https://...",
            "rating": 5,
            "title": "非常实用的 Skill",
            "content": "用了两周，提升了我的工作效率...",
            "is_verified_purchase": true,
            "helpful_count": 12,
            "unhelpful_count": 0,
            "is_edited": false,
            "created_at": "2026-09-19T10:00:00",
            "updated_at": "2026-09-19T10:00:00"
        }
    ],
    "total": 45,
    "page": 1,
    "limit": 10,
    "total_pages": 5
}
```

**Business Rules**:
- Returns empty array if product has no reviews
- Sorted by helpful_count DESC by default
- Pagination max 50 per page

---

### 5.3 PUT `/api/v4/reviews/{id}`

Update own review.

**Auth**: Required (review author only)
**Request**:
```json
{
    "rating": 4,
    "title": "Updated title",
    "content": "Updated content after more usage..."
}
```

**Response** (200):
```json
{
    "id": 1,
    "product_id": 42,
    "user_id": "user_abc",
    "username": "johndoe",
    "rating": 4,
    "title": "Updated title",
    "content": "Updated content after more usage...",
    "is_verified_purchase": true,
    "helpful_count": 12,
    "unhelpful_count": 0,
    "is_edited": true,
    "created_at": "2026-09-19T10:00:00",
    "updated_at": "2026-09-20T14:30:00"
}
```

**Business Rules**:
- Only the review author can update
- Rating change resets helpful votes (requires re-voting)
- `is_edited` is set to true on any update
- Title max 100 chars, content max 2000 chars

---

### 5.4 DELETE `/api/v4/reviews/{id}`

Delete own review.

**Auth**: Required (review author only)
**Response**: `204 No Content`

**Business Rules**:
- Only the review author can delete
- Delete is permanent (no soft delete)
- Product review counts and aggregates are recalculated

---

### 5.5 POST `/api/v4/reviews/{id}/helpful`

Vote on a review's helpfulness.

**Auth**: Required
**Request**:
```json
{
    "vote": "helpful"
}
```

Where `vote` is either `"helpful"` or `"unhelpful"`.

**Response** (200):
```json
{
    "review_id": 1,
    "vote": "helpful",
    "helpful_count": 13,
    "unhelpful_count": 0,
    "user_vote": "helpful"
}
```

**Business Rules**:
- One vote per user per review (toggling changes vote)
- Changing vote from helpful to unhelpful decrements helpful_count and increments unhelpful_count
- Users cannot vote on their own reviews

---

### 5.6 GET `/api/v4/products/{id}/review-summary`

Get aggregated rating statistics for a product.

**Auth**: Optional (public endpoint)
**Response** (200):
```json
{
    "product_id": 42,
    "avg_rating": 4.3,
    "review_count": 45,
    "rating_distribution": {
        "5": 28,
        "4": 10,
        "3": 4,
        "2": 2,
        "1": 1
    },
    "recent_reviews": [
        {
            "id": 1,
            "username": "johndoe",
            "rating": 5,
            "title": "非常实用的 Skill",
            "created_at": "2026-09-19T10:00:00"
        }
    ]
}
```

**Business Rules**:
- Returns zero values if no reviews exist
- `recent_reviews` returns up to 3 most recent reviews (summary only)
- Distribution values sum to `review_count`

---

### 5.7 GET `/api/v4/reviews/my`

Get the current user's reviews across all products.

**Auth**: Required
**Query Params**:
- `page` (default: 1)
- `limit` (default: 20, max: 50)

**Response** (200):
```json
{
    "reviews": [
        {
            "id": 1,
            "product_id": 42,
            "product_name": "SEO 文章生成器",
            "product_cover_url": "https://...",
            "rating": 5,
            "title": "非常实用的 Skill",
            "content": "用了两周...",
            "is_verified_purchase": true,
            "helpful_count": 12,
            "is_edited": false,
            "created_at": "2026-09-19T10:00:00",
            "updated_at": "2026-09-19T10:00:00"
        }
    ],
    "total": 3,
    "page": 1,
    "limit": 20
}
```

## 6. Models (`models.py`)

```python
class ReviewCreateRequest(BaseModel):
    product_id: int
    rating: int  # 1-5
    title: str = ""
    content: str = ""

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("Title must be 100 characters or less")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("Content must be 2000 characters or less")
        return v


class ReviewUpdateRequest(BaseModel):
    rating: int | None = None
    title: str | None = None
    content: str | None = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    user_id: str
    username: str
    avatar_url: str | None = None
    rating: int
    title: str
    content: str
    is_verified_purchase: bool
    helpful_count: int
    unhelpful_count: int
    is_edited: bool
    created_at: str
    updated_at: str


class ReviewVoteRequest(BaseModel):
    vote: str  # "helpful" | "unhelpful"

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: str) -> str:
        if v not in ("helpful", "unhelpful"):
            raise ValueError("Vote must be 'helpful' or 'unhelpful'")
        return v


class ReviewVoteResponse(BaseModel):
    review_id: int
    vote: str
    helpful_count: int
    unhelpful_count: int
    user_vote: str | None = None


class ReviewSummaryResponse(BaseModel):
    product_id: int
    avg_rating: float
    review_count: int
    rating_distribution: dict[str, int]  # {"5": 28, "4": 10, ...}
    recent_reviews: list[dict]


class MyReviewsResponse(BaseModel):
    reviews: list[dict]
    total: int
    page: int
    limit: int
```

## 7. Service Layer

### 7.1 `reviews_service.py` (new file)

```python
async def create_review(user_id: str, data: ReviewCreateRequest) -> dict:
    """Create a review for a product.

    Validates:
    - Product exists
    - User has purchased the product
    - User hasn't already reviewed this product

    Creates review with is_verified_purchase=True.
    Updates product aggregate stats.
    """

async def get_product_reviews(product_id: int, page: int, limit: int,
                               sort: str, rating: int | None) -> dict:
    """List reviews for a product with pagination and sorting."""

async def update_review(user_id: str, review_id: int, data: ReviewUpdateRequest) -> dict:
    """Update own review.

    Sets is_edited=True.
    If rating changes, recalculate product aggregates.
    """

async def delete_review(user_id: str, review_id: int) -> None:
    """Delete own review and recalculate product aggregates."""

async def vote_review(user_id: str, review_id: int, vote: str) -> dict:
    """Vote helpful/unhelpful on a review.

    Toggles vote if user already voted.
    Cannot vote on own review.
    Returns updated counts.
    """

async def get_review_summary(product_id: int) -> dict:
    """Get rating summary for a product.

    Returns avg_rating, distribution, and recent reviews.
    Uses denormalized product columns for fast lookup.
    """

async def get_my_reviews(user_id: str, page: int, limit: int) -> dict:
    """Get current user's reviews with product info."""

async def _recalculate_product_stats(product_id: int) -> None:
    """Recalculate product aggregate rating stats.

    Called after review create/update/delete.
    Updates: avg_rating, review_count, rating_1-5_count.
    """
```

### 7.2 `reviews_v4.py` (new router file)

```python
router = APIRouter(prefix="/api/v4", tags=["reviews"])

@router.post("/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(...): ...

@router.get("/products/{product_id}/reviews", response_model=dict)
async def list_reviews(...): ...

@router.put("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(...): ...

@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(...): ...

@router.post("/reviews/{review_id}/helpful", response_model=ReviewVoteResponse)
async def vote_helpful(...): ...

@router.get("/products/{product_id}/review-summary", response_model=ReviewSummaryResponse)
async def review_summary(...): ...

@router.get("/reviews/my", response_model=MyReviewsResponse)
async def my_reviews(...): ...
```

## 8. Frontend Changes

### 8.1 Review Form (Product Detail Page)

- Star rating selector (interactive 1-5 stars)
- Title input (max 100 chars)
- Content textarea (max 2000 chars, with character counter)
- Submit button (disabled until rating selected)
- "Verified Purchase" badge shown automatically
- Shows on product detail for users who purchased but haven't reviewed

### 8.2 Reviews List Section (Product Detail Page)

- Overall rating summary (big star + average + count)
- Rating distribution bar chart (5-star to 1-star bars)
- Filter by star rating
- Sort dropdown (Most Helpful, Most Recent, Highest, Lowest)
- Individual review cards with:
  - User avatar + username
  - Star rating display
  - Title + content (truncated with "show more")
  - Verified Purchase badge
  - Helpful/Unhelpful buttons with counts
  - "Edited" label if applicable
  - Timestamp (relative: "2 days ago")
- Pagination at bottom
- Empty state: "No reviews yet. Be the first!"

### 8.3 My Reviews Page

- List of user's reviews across all products
- Each row: product thumbnail, product name, rating stars, review title
- Edit/Delete actions per review
- Edit modal with pre-filled form

### 8.4 Rating Widget (Product Cards/List)

- Small star display on product cards when reviews exist
- "4.3 (45)" format — avg rating + review count
- Shows "New" or "0 reviews" for unreviewed products

## 9. Implementation Phases

### Phase 1: Database & Service Layer
- Migration: create reviews and review_votes tables
- Migration: alter products table for denormalized stats
- Service layer functions in `reviews_service.py`
- Aggregate recalculation logic

### Phase 2: API Endpoints
- All 7 endpoints in `reviews_v4.py` router
- Auth checks, purchase verification
- Error handling and validation

### Phase 3: Frontend Components
- Review form component
- Reviews list with filtering/sorting
- Rating summary widget
- My reviews page
- Product card rating display

### Phase 4: Tests & Polish
- 10 tests (TDD)
- Run full suite (target 259/259+)
- Commit

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| RV-01 | `test_create_review_as_verified_purchaser` | Buyer can review purchased product |
| RV-02 | `test_cannot_review_without_purchase` | Non-purchaser gets 403 |
| RV-03 | `test_one_review_per_user_per_product` | Duplicate review returns 409 |
| RV-04 | `test_list_product_reviews_with_pagination` | Pagination and sorting work |
| RV-05 | `test_review_helpful_voting` | Helpful/unhelpful voting with toggle |
| RV-06 | `test_cannot_vote_own_review` | Self-vote rejected |
| RV-07 | `test_review_summary_aggregates` | Avg rating and distribution correct |
| RV-08 | `test_update_own_review` | Edit review, is_edited flag, aggregate update |
| RV-09 | `test_delete_own_review` | Delete review, aggregates recalculated |
| RV-10 | `test_my_reviews_lists_all_user_reviews` | My reviews endpoint returns user's reviews |
