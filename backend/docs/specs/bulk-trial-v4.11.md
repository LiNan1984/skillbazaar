# Bulk Trial Run — v4.11 Feature Spec

## 1. Overview

Add a bulk trial feature allowing buyers to trial up to 5 Skills simultaneously in one action. This extends the v4.9 One-Click Trial Run with batch execution, reducing the friction of trying multiple Skills before purchasing.

## 2. Problem Statement

**Buyer Pain Point #2**: "买之前无法验证效果 — 信任缺失"
- Users want to try multiple similar Skills to find the best one
- Current v4.9 requires clicking "Trial" on each product individually
- When comparing 3-4 Skills, this means 3-4 separate trial executions
- No way to trial a batch of Skills from search results or comparison page

**Current State**:
- v4.9 One-Click Trial: single product trial via POST /api/v4/trial/run
- v4.10 Comparison Tool: side-by-side view of up to 4 products
- But no way to trial all 4 compared products at once

**Goal**: Enable bulk trial of up to 5 Skills in a single API call.

## 3. Scope

### In Scope
- Bulk trial endpoint accepting up to 5 product_ids
- Parallel/serial execution of trial runs
- Aggregate response with results for each product
- Enforce per-product trial limits (max 3 per product)
- Skip products user already purchased or trialed too many times
- Bulk trial eligibility check

### Out of Scope
- Custom trial input per product (uses default/empty input for bulk)
- Trial result persistence beyond existing trial_runs table
- Bulk trial history page
- Notifications for bulk trial completion

## 4. Database Schema

### 4.1 No new tables needed

Reuses existing `trial_runs` table from v4.9.

## 5. API Endpoints

### 5.1 POST `/api/v4/trial/bulk`

Execute bulk trial runs for up to 5 products.

**Auth**: Required
**Request**:
```json
{
    "product_ids": [1, 2, 3],
    "input_text": "帮我分析这些数据"
}
```

**Response**:
```json
{
    "total": 3,
    "succeeded": 2,
    "skipped": 1,
    "results": [
        {
            "product_id": 1,
            "product_name": "Data Analyzer",
            "status": "completed",
            "output_text": "平均值: 3.0...",
            "tokens_used": 128,
            "execution_time_ms": 1200,
            "trial_id": 15
        },
        {
            "product_id": 2,
            "product_name": "CSV Processor",
            "status": "completed",
            "output_text": "处理完成...",
            "tokens_used": 96,
            "execution_time_ms": 800,
            "trial_id": 16
        },
        {
            "product_id": 3,
            "product_name": "Chart Maker",
            "status": "skipped",
            "skip_reason": "试用次数已达上限",
            "trial_id": null
        }
    ]
}
```

**Business Rules**:
- Max 5 products per bulk trial
- Each product independently checked for trial eligibility
- Products that fail eligibility check are skipped (not errored)
- Same token cap (512) per individual trial
- Same execution timeout (30s) per individual trial
- Returns summary with succeeded/skipped counts

### 5.2 GET `/api/v4/trial/bulk/eligibility`

Check bulk trial eligibility for a list of products.

**Auth**: Required
**Query Params**: `product_ids` (comma-separated, e.g., `?product_ids=1,2,3`)
**Response**:
```json
{
    "eligible_count": 2,
    "total_count": 3,
    "products": [
        {
            "product_id": 1,
            "product_name": "Data Analyzer",
            "can_trial": true,
            "reason": null,
            "trials_remaining": 3
        },
        {
            "product_id": 2,
            "product_name": "CSV Processor",
            "can_trial": true,
            "reason": null,
            "trials_remaining": 2
        },
        {
            "product_id": 3,
            "product_name": "Chart Maker",
            "can_trial": false,
            "reason": "试用次数已达上限",
            "trials_remaining": 0
        }
    ]
}
```

## 6. Models (`models.py`)

```python
class BulkTrialRequest(BaseModel):
    product_ids: list[int]
    input_text: str = ""

class BulkTrialResult(BaseModel):
    product_id: int
    product_name: str
    status: str  # "completed" | "failed" | "skipped"
    output_text: str | None = None
    error_message: str | None = None
    tokens_used: int = 0
    execution_time_ms: int = 0
    trial_id: int | None = None
    skip_reason: str | None = None

class BulkTrialResponse(BaseModel):
    total: int
    succeeded: int
    skipped: int
    results: list[BulkTrialResult]

class BulkTrialEligibilityResponse(BaseModel):
    eligible_count: int
    total_count: int
    products: list[dict]
```

## 7. Service Layer

### 7.1 `trial_service.py` additions

```python
async def run_bulk_trial(user_id: str, product_ids: list[int], input_text: str) -> dict:
    """Execute bulk trial runs for up to 5 products.

    Returns aggregate results with per-product status.
    Skips products that are ineligible (purchased, limit reached).
    """

async def get_bulk_trial_eligibility(user_id: str, product_ids: list[int]) -> dict:
    """Check eligibility for each product in a bulk trial request."""
```

## 8. Frontend Changes

### 8.1 Bulk Trial Button

Add "批量试用" (Bulk Trial) button on:
- Search results page (select multiple products)
- Comparison page (trial all compared products at once)
- Wishlist page

Button behavior:
- Disabled when fewer than 2 or more than 5 products selected
- Shows count of eligible/total products
- Opens modal with input field for trial prompt
- On submit, shows progress for each product
- Results displayed in expandable cards

### 8.2 Trial Input Modal

- Shared input field for all products in batch
- Shows list of products to be trialed
- Progress indicator during execution
- Results shown inline after completion

## 9. Implementation Phases

### Phase 1: Backend API
- `POST /api/v4/trial/bulk`
- `GET /api/v4/trial/bulk/eligibility`
- Reuse existing `run_trial` for individual execution

### Phase 2: Frontend Components
- Bulk trial button on product cards
- Trial input modal for batch
- Results display

### Phase 3: Tests & Polish
- 8 tests (TDD)
- Run full suite
- Commit

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| BT-01 | `test_bulk_trial_two_products` | Both products trialed successfully |
| BT-02 | `test_bulk_trial_five_products` | Max 5 products allowed |
| BT-03 | `test_bulk_trial_more_than_five_rejected` | 6+ products returns 400 |
| BT-04 | `test_bulk_trial_skips_purchased` | Purchased products are skipped |
| BT-05 | `test_bulk_trial_skips_over_limit` | Products at trial limit are skipped |
| BT-06 | `test_bulk_trial_mixed_results` | Some succeed, some skip |
| BT-07 | `test_bulk_eligibility_check` | Returns correct eligibility for each product |
| BT-08 | `test_bulk_trial_nonexistent_product` | Handles non-existent product IDs |
