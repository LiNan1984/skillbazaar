import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TrendingUp, Clock, ArrowUpCircle, ArrowDownCircle, Star } from 'lucide-react'
import HeroBanner, { HeroAdvantages } from '../components/HeroBanner'
import CategoryTabs from '../components/CategoryTabs'
import ProductCard from '../components/ProductCard'
import { getProducts } from '../services/api'

const SORT_OPTIONS = [
  { key: 'popular', label: '热门', icon: TrendingUp },
  { key: 'newest', label: '最新', icon: Clock },
  { key: 'price_asc', label: '价格↑', icon: ArrowUpCircle },
  { key: 'price_desc', label: '价格↓', icon: ArrowDownCircle },
  { key: 'rating', label: '评分', icon: Star },
]

const PAGE_SIZE = 12

function ProductSkeleton() {
  return (
    <div className="product-card skeleton">
      <div className="product-card-top">
        <div className="skeleton-header shimmer" />
      </div>
      <div className="skeleton-line shimmer" style={{ width: '70%', height: '18px' }} />
      <div className="skeleton-line shimmer" style={{ width: '90%' }} />
      <div className="skeleton-line shimmer" style={{ width: '50%' }} />
      <div className="skeleton-footer shimmer" />
    </div>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalItems, setTotalItems] = useState(0)

  const sort = searchParams.get('sort') || 'popular'
  const keyword = searchParams.get('keyword') || ''
  const category = searchParams.get('category') || ''
  const subcategory = searchParams.get('subcategory') || ''
  const minPrice = searchParams.get('min_price') || ''
  const maxPrice = searchParams.get('max_price') || ''

  useEffect(() => {
    setCurrentPage(1)
  }, [category, subcategory, keyword, minPrice, maxPrice, sort])

  useEffect(() => {
    setLoading(true)
    getProducts({
      category,
      subcategory,
      keyword,
      minPrice,
      maxPrice,
      sort,
      page: currentPage,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        const items = data.items || data.products || data.data || []
        const total = data.total || data.total_count || items.length
        setProducts(items)
        setTotalItems(total)
        setTotalPages(Math.ceil(total / PAGE_SIZE))
      })
      .catch(() => {
        setProducts([])
        setTotalPages(1)
      })
      .finally(() => setLoading(false))
  }, [category, subcategory, keyword, minPrice, maxPrice, sort, currentPage])

  const handleSort = (key) => {
    const params = new URLSearchParams(searchParams)
    params.set('sort', key)
    setSearchParams(params)
  }

  return (
    <>
      <HeroBanner />
      <CategoryTabs />

      <div className="home-page">
        <div className="catalog-heading">
          <div>
            <h2>市场货架</h2>
            <p>浏览 Agent / Skill / Cron / Workflow，按分类与关键词筛选</p>
          </div>
        </div>
        <div className="sort-bar">
          <span className="result-count">
            共 <strong>{totalItems}</strong> 个商品
            {keyword && (
              <>
                {' '}· 搜索「<strong>{keyword}</strong>」
              </>
            )}
          </span>
          <div className="sort-options">
            {SORT_OPTIONS.map((opt) => {
              const Icon = opt.icon
              return (
                <button
                  key={opt.key}
                  className={`sort-btn ${sort === opt.key ? 'active' : ''}`}
                  onClick={() => handleSort(opt.key)}
                >
                  <Icon size={14} />
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>

        {loading ? (
          <div className="product-grid">
            {Array.from({ length: 9 }).map((_, i) => (
              <ProductSkeleton key={i} />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🔍</span>
            <h3>没有找到相关商品</h3>
            <p>试试调整筛选条件或搜索其他关键词</p>
            <div className="empty-actions">
              <button className="btn btn-primary" onClick={() => setSearchParams({})}>
                查看全部商品
              </button>
              <button className="btn btn-ghost" onClick={() => navigate('/publish')}>
                发布商品
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="product-grid">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="page-btn"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => p - 1)}
                >
                  上一页
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(
                    (p) =>
                      p === 1 ||
                      p === totalPages ||
                      Math.abs(p - currentPage) <= 2
                  )
                  .map((p, idx, arr) => (
                    <span key={p}>
                      {idx > 0 && arr[idx - 1] < p - 1 && <span className="page-ellipsis">...</span>}
                      <button
                        className={`page-btn ${p === currentPage ? 'active' : ''}`}
                        onClick={() => setCurrentPage(p)}
                      >
                        {p}
                      </button>
                    </span>
                  ))}
                <button
                  className="page-btn"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => p + 1)}
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}

        <HeroAdvantages />
      </div>
    </>
  )
}
