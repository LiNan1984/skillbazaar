# Seller Dashboard — v4.14 Feature Spec

## 1. Overview

Add a Seller Dashboard providing aggregated analytics for sellers to understand their business performance. This extends v4.2 Analytics Dashboard with seller-level aggregated views, addressing the seller pain point "缺乏数据反馈 — 不知道如何优化".

## 2. Problem Statement

**Seller Pain Point #7**: "缺乏数据反馈 — 不知道如何优化"
- Sellers don't know which products perform well
- No overview of total revenue, views, and conversion rate
- No trend data to understand seasonality or campaign impact
- Current v4.2 analytics requires navigating to each product individually

**Current State**:
- v4.2 Analytics: per-product analytics, category breakdown, platform overview
- But no seller-level dashboard that aggregates ALL their products
- No trend/time-series data

**Goal**: Provide a one-page seller dashboard with key metrics and trends.

## 3. Scope

### In Scope
- Seller dashboard overview (total stats across all products)
- Per-product performance list with key metrics
- Daily trend data (views, purchases, revenue over last 30 days)

### Out of Scope
- Real-time analytics (cached, refreshed hourly)
- Comparative analytics (vs other sellers)
- Predictive analytics / forecasting
- Export to CSV

## 4. Database Schema

### 4.1 Reuses existing tables

- `products` — seller_name, views, rating, price
- `transactions` — type='buy', status='completed' for purchase tracking
- `product_analytics` — per-product analytics events (if exists)
- `trial_runs` — trial usage tracking

### 4.2 No new tables needed

All data derived from existing tables.

## 5. API Endpoints

### 5.1 GET `/api/v4/seller/dashboard`

Seller's overall business overview.

**Auth**: Required (seller only)
**Query Params**: None
**Response**:
```json
{
    "total_products": 12,
    "total_views": 3450,
    "total_purchases": 89,
    "total_revenue": 8900.00,
    "conversion_rate": 2.58,
    "avg_rating": 4.2,
    "top_products": [
        {"id": 1, "name": "Product A", "revenue": 2500.00, "purchases": 25},
        {"id": 2, "name": "Product B", "revenue": 1800.00, "purchases": 18}
    ],
    "recent_activity": [
        {"date": "2026-01-15", "views": 120, "purchases": 5, "revenue": 500.00}
    ]
}
```

**Business Rules**:
- Only returns data for products owned by the authenticated seller
- Revenue = sum of (price * quantity) for completed purchases
- Conversion rate = purchases / views * 100 (min 0)
- Top products limited to top 5 by revenue
- Recent activity limited to last 7 days

### 5.2 GET `/api/v4/seller/products`

List of seller's products with performance metrics.

**Auth**: Required (seller only)
**Query Params**: `page` (default 1), `limit` (default 20), `sort` (revenue|views|purchases|rating, default: revenue)
**Response**:
```json
{
    "products": [
        {
            "id": 1,
            "name": "Product A",
            "price": 100.00,
            "status": "active",
            "views": 500,
            "purchases": 25,
            "revenue": 2500.00,
            "rating": 4.5,
            "conversion_rate": 5.0,
            "trend": "up"
        }
    ],
    "total": 12,
    "page": 1,
    "limit": 20
}
```

**Business Rules**:
- Sort by specified metric (default: revenue desc)
- trend: "up" if revenue increased vs previous period, "down" if decreased, "stable" if < 5% change
- Only seller's own products

### 5.3 GET `/api/v4/seller/trends`

Time-series data for seller's products.

**Auth**: Required (seller only)
**Query Params**: `period` (7d|30d|90d, default: 30d)
**Response**:
```json
{
    "period": "30d",
    "data": [
        {"date": "2025-12-16", "views": 120, "purchases": 5, "revenue": 500.00},
        {"date": "2025-12-17", "views": 98, "purchases": 3, "revenue": 300.00}
    ],
    "summary": {
        "total_views": 3450,
        "total_purchases": 89,
        "total_revenue": 8900.00
    }
}
```

**Business Rules**:
- Period determines date range: 7d, 30d, or 90 days
- Data aggregated by date
- Days with no activity included with zeros

## 6. Models (`models.py`)

```python
class SellerDashboardResponse(BaseModel):
    total_products: int
    total_views: int
    total_purchases: int
    total_revenue: float
    conversion_rate: float
    avg_rating: float
    top_products: list[dict]
    recent_activity: list[dict]

class SellerProductItem(BaseModel):
    id: int
    name: str
    price: float
    status: str
    views: int
    purchases: int
    revenue: float
    rating: float
    conversion_rate: float
    trend: str  # "up" | "down" | "stable"

class SellerProductsResponse(BaseModel):
    products: list[SellerProductItem]
    total: int
    page: int
    limit: int

class SellerTrendResponse(BaseModel):
    period: str
    data: list[dict]
    summary: dict
```

## 7. Service Layer

### 7.1 `seller_dashboard_service.py` (new file)

```python
async def get_seller_dashboard(seller_name: str) -> dict:
    """Get aggregated dashboard stats for a seller."""

async def get_seller_products(seller_name: str, page: int, limit: int, sort: str) -> dict:
    """Get seller's products with performance metrics."""

async def get_seller_trends(seller_name: str, period: str) -> dict:
    """Get time-series data for seller's products."""
```

## 8. Router

### 8.1 `routers/seller_dashboard_v4.py` (new file)

```python
router = APIRouter(prefix="/api/v4/seller", tags=["seller-dashboard-v4"])

@router.get("/dashboard", response_model=SellerDashboardResponse)
async def get_dashboard(request: Request): ...

@router.get("/products", response_model=SellerProductsResponse)
async def get_products(request: Request, page: int = 1, limit: int = 20, sort: str = "revenue"): ...

@router.get("/trends", response_model=SellerTrendResponse)
async def get_trends(request: Request, period: str = "30d"): ...
```

## 9. Database Helpers

New helpers in `database.py`:

```python
async def get_seller_product_stats(seller_name: str) -> list[dict]:
    """Get stats (views, purchases, revenue) per product for a seller."""

async def get_seller_transaction_stats(seller_name: str, days: int = 30) -> list[dict]:
    """Get daily transaction stats for a seller over N days."""

async def get_seller_total_stats(seller_name: str) -> dict:
    """Get total stats across all seller's products."""
```

## 10. Implementation Phases

### Phase 1: Backend
- Database helpers
- Service layer
- Router with 3 endpoints
- Models

### Phase 2: Tests
- 8 tests (TDD)
- Test dashboard aggregation
- Test sorting/filtering
- Test trend data
- Test auth/seller isolation

### Phase 3: Integration
- Register router in main.py
- Run full suite
- Commit

## 11. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| SD-01 | `test_seller_dashboard_basic` | Returns correct aggregated stats |
| SD-02 | `test_seller_dashboard_empty` | Returns zeros for seller with no products |
| SD-03 | `test_seller_products_list` | Returns paginated product list with metrics |
| SD-04 | `test_seller_products_sort` | Sorting by revenue/views/purchases/rating |
| SD-05 | `test_seller_products_isolated` | Only returns own products |
| SD-06 | `test_seller_trends_7d` | Returns 7-day trend data |
| SD-07 | `test_seller_trends_30d` | Returns 30-day trend data |
| SD-08 | `test_seller_trends_empty_days` | Includes days with zero activity |