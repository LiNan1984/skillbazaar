# Eval Score Badges in Search Results — v4.8 Feature Spec

## 1. Overview

Display evaluation scores as visual badges in search results and product listings, helping buyers quickly identify high-quality Skills at a glance.

## 2. Problem Statement

**Buyer Pain Point #3**: "Skill 质量参差不齐 — 缺乏可信评分体系"
- Buyers see products in search but can't quickly assess quality
- Current scores are hidden in product detail pages only
- High-quality Skills with good eval scores don't stand out

## 3. Goals

1. Show eval_score as a visual badge on product cards in search results
2. Color-code badges by score tier (excellent/good/average/poor)
3. Add filter/sort by eval_score in search
4. Show evaluation status (passed/pending/failed) alongside score

## 4. Scope

### In Scope
- Eval score badge component for product cards
- Score tier color coding
- Sort by eval_score option in search
- Eval status indicator (platform verified)

### Out of Scope
- Detailed eval breakdown on badge (hover tooltip future)
- Community ratings (separate feature)
- Seller self-reported quality scores

## 5. Data Model

Products already have these eval-related columns:
- `eval_score` (float) — 0.0 to 1.0
- `eval_status` (str) — 'passed' | 'pending' | 'failed'
- `eval_report` (text) — JSON report from evaluation engine
- `eval_version` (str) — version of eval engine used

## 6. API Changes

### 6.1 GET `/api/v4/products/search` — Enhanced response

Add to each product in results:

```json
{
    "id": 1,
    "name": "Data Analyzer",
    "price": 100,
    "eval_score": 0.92,
    "eval_status": "passed",
    "eval_badge": {
        "tier": "excellent",
        "color": "#22c55e",
        "label": "A+",
        "score_display": "92/100"
    }
}
```

**Tier mapping**:
| Score Range | Tier | Color | Label |
|-------------|------|-------|-------|
| 0.9 - 1.0 | excellent | green | A+ |
| 0.7 - 0.89 | good | blue | B+ |
| 0.5 - 0.69 | average | yellow | C+ |
| 0.0 - 0.49 | poor | red | D |

### 6.2 New sort option: `sort=eval_score`

Add `eval_score` to available sort options in search.

## 7. Frontend Changes

### 7.1 Product Card Badge

Add a small badge overlay to product cards:
- Position: top-right corner
- Size: compact (fits in card header)
- Shows score number + tier color
- Tooltip on hover: "平台评估: 92/100 — 通过"

### 7.2 Search Filter

Add filter chip: "仅显示平台认证" (eval_status = 'passed')

## 8. Backend Changes

### 8.1 `search_products` enhancement

Add optional parameter `min_eval_score` for filtering by minimum score.

### 8.2 Badge computation helper

```python
def compute_eval_badge(eval_score: float, eval_status: str) -> dict | None:
    """Compute badge info for a product's eval score."""
    if eval_status != 'passed' or eval_score is None:
        return None
    if eval_score >= 0.9:
        tier, color, label = "excellent", "#22c55e", "A+"
    elif eval_score >= 0.7:
        tier, color, label = "good", "#3b82f6", "B+"
    elif eval_score >= 0.5:
        tier, color, label = "average", "#eab308", "C+"
    else:
        tier, color, label = "poor", "#ef4444", "D"
    return {
        "tier": tier,
        "color": color,
        "label": label,
        "score_display": f"{int(eval_score * 100)}/100"
    }
```

## 9. Implementation Phases

### Phase 1: Backend API (services + routers)
- Add `compute_eval_badge` helper
- Add `min_eval_score` filter to search
- Include eval_badge in search response

### Phase 2: Frontend Components
- Add EvalBadge component
- Add filter chip for "platform verified"
- Style badges on product cards

### Phase 3: Tests & Polish
- Test badge computation for all tiers
- Test search with eval filters
- Full test suite run

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| EB-01 | `test_eval_badge_excellent` | Score 0.9+ returns A+ badge |
| EB-02 | `test_eval_badge_good` | Score 0.7-0.89 returns B+ badge |
| EB-03 | `test_eval_badge_average` | Score 0.5-0.69 returns C+ badge |
| EB-04 | `test_eval_badge_poor` | Score 0.0-0.49 returns D badge |
| EB-05 | `test_eval_badge_pending_no_badge` | Pending/failed status returns None |
| EB-06 | `test_search_with_eval_filter` | Filter by min_eval_score works |
| EB-07 | `test_search_results_include_badge` | Search response includes eval_badge |
| EB-08 | `test_sort_by_eval_score` | Sorting by eval_score works |
