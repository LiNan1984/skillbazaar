import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API 错误:', error.response?.data || error.message)
    return Promise.reject(error.response?.data || error)
  }
)

// ---- 商品相关 ----

export async function getProducts(filters = {}) {
  const params = new URLSearchParams()
  if (filters.category) params.append('category', filters.category)
  if (filters.subcategory) params.append('subcategory', filters.subcategory)
  if (filters.keyword) params.append('keyword', filters.keyword)
  if (filters.minPrice !== undefined && filters.minPrice !== '')
    params.append('min_price', filters.minPrice)
  if (filters.maxPrice !== undefined && filters.maxPrice !== '')
    params.append('max_price', filters.maxPrice)
  if (filters.sort) params.append('sort_by', filters.sort)
  if (filters.page) params.append('page', filters.page)
  if (filters.pageSize) params.append('page_size', filters.pageSize)
  return api.get(`/products?${params.toString()}`)
}

export async function getProduct(id) {
  return api.get(`/products/${id}`)
}

export async function createProduct(data, token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return api.post('/products', data, { headers })
}

// ---- 用户相关 ----

export async function initUser() {
  return api.post('/users/init')
}

export async function getUser(id) {
  return api.get(`/users/${id}`)
}

// ---- 交易相关 ----

export async function buyProduct(userId, productId) {
  return api.post('/transactions/buy', { buyer_id: userId, product_id: productId })
}

export async function getTransactions(userId) {
  return api.get(`/transactions/user/${userId}`)
}

export async function getLibrary(userId) {
  return api.get(`/transactions/library/${userId}`)
}

// ---- 聊天相关 ----

export async function sendChat(userId, message) {
  return api.post('/chat', { user_id: userId, message }, { timeout: 60000 })
}

// ---- 分类相关 ----

export async function getCategories() {
  return api.get('/products/categories')
}

// ---- Skill Upload & Execution ----

export async function uploadSkill(productId, skillType, file, sellerId, skillMeta) {
  const formData = new FormData()
  formData.append('product_id', productId)
  formData.append('skill_type', skillType)
  formData.append('seller_id', sellerId)
  if (file) formData.append('file', file)
  if (skillMeta) formData.append('skill_meta', JSON.stringify(skillMeta))
  return api.post('/skills/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function executeSkill(productId, userId, inputParams) {
  return api.post(`/skills/${productId}/execute`, {
    product_id: productId,
    user_id: userId,
    input_params: inputParams,
  })
}

export async function createLicense(userId, productId, licenseType = 'permanent', maxCalls = null) {
  return api.post('/skills/license', {
    user_id: userId,
    product_id: productId,
    license_type: licenseType,
    max_calls: maxCalls,
  })
}

export async function verifyLicense(licenseToken, productId) {
  return api.post('/skills/license/verify', {
    license_token: licenseToken,
    product_id: productId,
  })
}

export async function getMySkills(userId) {
  return api.get(`/skills/my?user_id=${userId}`)
}

// ---- Auth V2 ----

export async function register(username, password, nickname) {
  return api.post('/v2/auth/register', { username, password, nickname })
}

export async function login(username, password) {
  return api.post('/v2/auth/login', { username, password })
}

export async function getMe(token) {
  return api.get('/v2/auth/me', { headers: { Authorization: `Bearer ${token}` } })
}

export async function updateProfile(data, token) {
  return api.put('/v2/profile', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getProfile(token) {
  return api.get('/v2/profile', { headers: { Authorization: `Bearer ${token}` } })
}

export async function rechargeCoins(promoCode, token) {
  return api.post('/v2/wallet/recharge', { user_id: '', promo_code: promoCode }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getWalletHistory(page = 1, token) {
  return api.get(`/v2/wallet/history?page=${page}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function logBehavior(action, targetType, targetId, metadata, token) {
  return api.post('/v2/behavior', { action, target_type: targetType, target_id: targetId, metadata }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getNotifications(unreadOnly = false, token) {
  return api.get(`/v2/notifications?unread_only=${unreadOnly}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function markNotificationRead(notifId, token) {
  return api.post(`/v2/notifications/${notifId}/read`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Seller Management ----

export async function getMyProducts(token) {
  return api.get('/v2/seller/products', { headers: { Authorization: `Bearer ${token}` } })
}

export async function updateProductStatus(productId, status, reason, token) {
  return api.put(`/v2/seller/products/${productId}/status?status=${status}&reason=${reason || ''}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getSellerStats(token) {
  return api.get('/v2/seller/stats', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getProductLifecycle(productId, token) {
  return api.get(`/v2/seller/products/${productId}/lifecycle`, { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Pricing ----

export async function getProductPricing(productId) {
  return api.get(`/skills/${productId}/pricing`)
}

export async function updateProductPricing(productId, pricingModel, token) {
  return api.put(`/skills/${productId}/pricing`, { pricing_model: pricingModel }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function recalculatePricing() {
  return api.post('/skills/pricing/recalculate')
}

// ---- Bounties ----

export async function getBounties(filters = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.append('status', filters.status)
  if (filters.category) params.append('category', filters.category)
  if (filters.keyword) params.append('keyword', filters.keyword)
  if (filters.page) params.append('page', filters.page)
  if (filters.pageSize) params.append('page_size', filters.pageSize)
  return api.get(`/bounties?${params.toString()}`)
}

export async function getBounty(id) {
  return api.get(`/bounties/${id}`)
}

export async function createBounty(data, token) {
  return api.post('/bounties', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function applyForBounty(bountyId, data, token) {
  return api.post(`/bounties/${bountyId}/apply`, data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function selectBountyDeveloper(bountyId, applicationId, token) {
  return api.post(`/bounties/${bountyId}/select`, { application_id: applicationId }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function deliverBounty(bountyId, description, file, token) {
  const formData = new FormData()
  if (description) formData.append('description', description)
  if (file) formData.append('file', file)
  return api.post(`/bounties/${bountyId}/deliver`, formData, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
  })
}

export async function reviewBountyDelivery(bountyId, deliveryId, accept, token) {
  return api.post(`/bounties/${bountyId}/review`, { delivery_id: deliveryId, accept }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyPostedBounties(userId, token) {
  return api.get(`/bounties/my/posted?user_id=${userId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyAppliedBounties(userId, token) {
  return api.get(`/bounties/my/applied?user_id=${userId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export default api
