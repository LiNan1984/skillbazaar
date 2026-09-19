# Bulk Operations — v4.12 Feature Spec

## 1. Overview

Add bulk operations allowing sellers to manage multiple products at once. This extends the v4.1 Skill Versioning with batch actions on products, reducing the operational friction for sellers managing catalogs of Skills.

## 2. Problem Statement

**Seller Pain Point #3**: "发布流程复杂 — 多步骤容易放弃"
**Seller Pain Point #5**: "缺乏数据反馈 — 不知道如何优化"

- Sellers with 10+ products spend excessive time on repetitive management tasks
- No way to batch-publish, batch-unpublish, or batch-update prices
- Each product requires individual navigation and action
- When a seller wants to run a promotion, updating 20 products one by one is tedious

**Current State**:
- v4.1 Skill Versioning: individual version management
- v4.6 New Product Traffic Boost: individual boost_score updates
- v4.7 Skill Subscription: individual subscription plan management
- But no batch operations for sellers

**Goal**: Enable batch management of up to 50 products in a single API call.

## 3. Scope

### In Scope
- Bulk publish/unpublish products
- Bulk price update (percentage or fixed amount)
- Bulk delete products (soft delete)
- Bulk operation eligibility check
- Operation audit log

### Out of Scope
- Bulk import/export (CSV)
- Bulk image/thumbnail management
- Bulk SEO/meta tag updates
- Undo/rollback of bulk operations

## 4. Database Schema

### 4.1 New table: `bulk_operations`

```sql
CREATE TABLE bulk_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,           -- Seller who initiated
    operation TEXT NOT NULL,          -- "publish", "unpublish", "price_update", "delete"
    product_ids TEXT NOT NULL,        -- JSON array of product IDs
    params TEXT,                      -- JSON: {"percentage": 10} or {"price": 50}
    status TEXT DEFAULT "pending",    -- "pending", "completed", "failed", "partial"
    succeeded_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    error_details TEXT,               -- JSON array of per-product errors
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

## 5. API Endpoints

### 5.1 POST `/api/v4/products/bulk`

Execute a bulk operation on multiple products.

**Auth**: Required (seller only)
**Request**:
```json
{
    "operation": "publish",
    "product_ids": [1, 2, 3]
}
```

```json
{
    "operation": "price_update",
    "product_ids": [1, 2, 3],
    "params": {"percentage": 10}
}
```

```json
{
    "operation": "price_update",
    "product_ids": [1, 2, 3],
    "params": {"amount": -5}
}
```

**Response**:
```json
{
    "operation_id": 42,
    "operation": "publish",
    "status": "completed",
    "total": 3,
    "succeeded": 3,
    "failed": 0,
    "results": [
        {"product_id": 1, "status": "success", "message": "已发布"},
        {"product_id": 2, "status": "success", "message": "已发布"},
        {"product_id": 3, "status": "success", "message": "已发布"}
    ]
}
```

**Business Rules**:
- Max 50 products per bulk operation
- Only the product owner (seller) can operate on their products
- Non-existent products are counted as failures
- Price updates: percentage (0-100%) or fixed amount (can be negative)
- Price update respects minimum price of ¥1
- Delete is soft delete (sets is_published=0, not actual deletion)

### 5.2 GET `/api/v4/products/bulk/history`

Get history of bulk operations for the current seller.

**Auth**: Required (seller only)
**Query Params**: `page` (default 1), `limit` (default 20)
**Response**:
```json
{
    "operations": [
        {
            "id": 42,
            "operation": "publish",
            "status": "completed",
            "total": 3,
            "succeeded": 3,
            "failed": 0,
            "created_at": "2026-01-15T10:00:00",
            "completed_at": "2026-01-15T10:00:01"
        }
    ],
    "total": 10,
    "page": 1,
    "limit": 20
}
```

## 6. Models (`models.py`)

```python
class BulkOperationRequest(BaseModel):
    operation: str  # "publish" | "unpublish" | "price_update" | "delete"
    product_ids: list[int]
    params: dict | None = None

class BulkOperationResult(BaseModel):
    product_id: int
    status: str  # "success" | "failed"
    message: str

class BulkOperationResponse(BaseModel):
    operation_id: int
    operation: str
    status: str  # "completed" | "failed" | "partial"
    total: int
    succeeded: int
    failed: int
    results: list[BulkOperationResult]

class BulkOperationHistoryResponse(BaseModel):
    operations: list[dict]
    total: int
    page: int
    limit: int
```

## 7. Service Layer

### 7.1 `bulk_operation_service.py` (new file)

```python
async def execute_bulk_operation(user_id: str, operation: str, product_ids: list[int], params: dict | None = None) -> dict:
    """Execute a bulk operation on multiple products.

    Validates ownership, applies operation, logs results.
    Returns operation summary with per-product results.
    """

async def get_bulk_operation_history(user_id: str, page: int = 1, limit: int = 20) -> dict:
    """Get paginated history of bulk operations for a seller."""
```

## 8. Frontend Changes

### 8.1 Bulk Action Bar

Add bulk action bar on seller's product management page:
- Checkbox selection on product rows
- Action dropdown (Publish, Unpublish, Update Price, Delete)
- Count of selected products
- Confirmation dialog before execution
- Progress indicator during operation
- Success/failure summary after completion

### 8.2 Operation History

- Table showing past bulk operations
- Expandable to see per-product results
- Filter by operation type

## 9. Implementation Phases

### Phase 1: Backend API
- `POST /api/v4/products/bulk`
- `GET /api/v4/products/bulk/history`
- Database table + service layer

### Phase 2: Frontend Components
- Bulk action bar on product list
- Operation history page
- Confirmation dialogs

### Phase 3: Tests & Polish
- 10 tests (TDD)
- Run full suite
- Commit

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| BO-01 | `test_bulk_publish_products` | Publish multiple unpublished products |
| BO-02 | `test_bulk_unpublish_products` | Unpublish multiple published products |
| BO-03 | `test_bulk_price_update_percentage` | Update prices by percentage |
| BO-04 | `test_bulk_price_update_amount` | Update prices by fixed amount |
| BO-05 | `test_bulk_price_minimum_respected` | Price doesn't go below ¥1 |
| BO-06 | `test_bulk_delete_soft_delete` | Soft delete (is_published=0) |
| BO-07 | `test_bulk_rejects_other_sellers_products` | Cannot operate on other sellers' products |
| BO-08 | `test_bulk_more_than_fifty_rejected` | 50+ products returns 400 |
| BO-09 | `test_bulk_operation_history` | History endpoint returns paginated results |
| BO-10 | `test_bulk_invalid_operation_rejected` | Unknown operation type returns 400 |
