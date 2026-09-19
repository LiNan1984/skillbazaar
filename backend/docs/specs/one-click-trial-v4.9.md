# One-Click Trial Run — v4.9 Feature Spec

## 1. Overview

Add a prominent "一键试运行" (One-Click Trial Run) button on product detail pages, allowing buyers to instantly try a Skill in the sandbox without purchasing. This lowers the barrier to entry and increases conversion.

## 2. Problem Statement

**Buyer Pain Point #2**: "买之前无法验证效果 — 信任缺失"
- Users want to see a Skill in action before buying
- Current trial requires navigating to the sandbox manually
- Product detail page lacks a direct "try it now" entry point

**Current State**:
- Trial mode exists (limited to 512 tokens)
- Sandbox execution engine (虾塘) is functional
- But users must manually navigate to try a Skill

**Goal**: Add a one-click trial button directly on the product detail page.

## 3. Scope

### In Scope
- "一键试运行" button on product detail page
- API endpoint to trigger trial execution
- Trial usage tracking (per user, per product)
- Trial limit enforcement (512 token output cap)
- Trial history for users

### Out of Scope
- Custom trial duration per seller
- Trial-to-purchase conversion analytics
- Trial result sharing

## 4. Database Schema

### 4.1 New Table: `trial_runs`

```sql
CREATE TABLE IF NOT EXISTS trial_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'completed' | 'failed' | 'timeout'
    input_text TEXT,
    output_text TEXT,
    error_message TEXT,
    tokens_used INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_trial_runs_user ON trial_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_trial_runs_product ON trial_runs(product_id);
```

## 5. API Endpoints

### 5.1 POST `/api/v4/trial/run`

Execute a trial run of a Skill.

**Auth**: Required
**Request**:
```json
{
    "product_id": 123,
    "input_text": "分析这个数据: [1, 2, 3, 4, 5]"
}
```

**Response**:
```json
{
    "trial_id": 1,
    "product_id": 123,
    "product_name": "Data Analyzer",
    "status": "completed",
    "output_text": "平均值: 3.0, 最大值: 5, 最小值: 1",
    "tokens_used": 128,
    "execution_time_ms": 1200,
    "created_at": "2025-01-15T10:30:00"
}
```

**Business Rules**:
- User must not have purchased the product (trials are for non-buyers)
- User must not have exceeded trial limit (e.g., 3 trials per product)
- Token output capped at 512 tokens
- Execution timeout: 30 seconds

### 5.2 GET `/api/v4/trial/my`

List current user's trial history.

**Auth**: Required
**Query Params**: `product_id` (optional)
**Response**:
```json
{
    "trials": [
        {
            "trial_id": 1,
            "product_id": 123,
            "product_name": "Data Analyzer",
            "status": "completed",
            "tokens_used": 128,
            "created_at": "2025-01-15T10:30:00"
        }
    ]
}
```

### 5.3 GET `/api/v4/trial/can-trial`

Check if user can trial a product.

**Auth**: Required
**Query Params**: `product_id`
**Response**:
```json
{
    "can_trial": true,
    "reason": null,
    "trials_remaining": 3
}
```

**Reasons for denial**:
- "已购买此商品" (already purchased)
- "试用次数已达上限" (trial limit reached)
- "商品不支持试用" (product doesn't support trial)

### 5.4 POST `/api/v4/cron/cleanup-trials`

Cron: clean up old trial runs (>30 days).

**Auth**: None (internal cron)
**Response**:
```json
{
    "deleted_count": 150,
    "message": "Cleaned up 150 old trial runs"
}
```

## 6. Models (`models.py`)

```python
class TrialRunRequest(BaseModel):
    product_id: int
    input_text: str

class TrialRunResponse(BaseModel):
    trial_id: int
    product_id: int
    product_name: str
    status: str
    output_text: str | None = None
    error_message: str | None = None
    tokens_used: int = 0
    execution_time_ms: int = 0
    created_at: str

class TrialHistoryResponse(BaseModel):
    trials: list[TrialRunResponse]

class CanTrialResponse(BaseModel):
    can_trial: bool
    reason: str | None = None
    trials_remaining: int = 3

class TrialCleanupResponse(BaseModel):
    deleted_count: int = 0
    message: str
```

## 7. Service Layer

### 7.1 `trial_service.py`

```python
async def run_trial(user_id: str, product_id: int, input_text: str) -> dict:
    """Execute a trial run of a Skill."""

async def get_trial_history(user_id: str, product_id: int = None) -> list[dict]:
    """Get trial history for a user, optionally filtered by product."""

async def can_trial(user_id: str, product_id: int) -> dict:
    """Check if user can trial a product."""

async def cleanup_old_trials() -> dict:
    """Cron: delete trial runs older than 30 days."""
```

## 8. Frontend Changes

### 8.1 Product Detail Page

Add a prominent "一键试运行" button:
- Position: Below price/buy section
- Style: Secondary action button (outlined)
- Disabled state: If purchased, trial limit reached, or product doesn't support trial
- Click → opens trial input modal
- Modal has: text input for trial prompt, submit button
- Result displayed inline with copy button

### 8.2 Trial Status Indicators

On product cards in search:
- Show "可试用" badge if trial available
- Show "已试用" if user has trialed before

## 9. Implementation Phases

### Phase 1: Database & Models
- Create `trial_runs` table
- Add Pydantic models

### Phase 2: Core Trial API
- `POST /api/v4/trial/run`
- `GET /api/v4/trial/my`
- `GET /api/v4/trial/can-trial`

### Phase 3: Cron & Cleanup
- `POST /api/v4/cron/cleanup-trials`

### Phase 4: Frontend Integration
- Add trial button to product detail page
- Add trial result display
- Disable button when not eligible

### Phase 5: Tests & Polish
- 8 tests (TDD)
- Run full suite
- Commit

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| TR-01 | `test_run_trial_success` | Trial executes, returns result |
| TR-02 | `test_cannot_trial_purchased_product` | Purchased products can't be trialed |
| TR-03 | `test_trial_limit_enforced` | Max 3 trials per product |
| TR-04 | `test_get_trial_history` | Returns user's trial history |
| TR-05 | `test_can_trial_eligible` | Correct eligibility response |
| TR-06 | `test_trial_token_limit` | Output capped at 512 tokens |
| TR-07 | `test_cron_cleanup_old_trials` | Old trials deleted |
| TR-08 | `test_trial_creates_record` | Trial run saved to DB |
