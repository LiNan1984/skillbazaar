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

export async function sendChat(userId, message, card = null) {
  return api.post('/chat', { user_id: userId, message, card }, { timeout: 60000 })
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

export async function deleteSellerProduct(productId, token) {
  return api.delete(`/v2/seller/products/${productId}`, { headers: { Authorization: `Bearer ${token}` } })
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

export async function deleteBounty(bountyId, token) {
  return api.delete(`/bounties/${bountyId}`, { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Admin ----

export async function adminGetBounties(status = '', page = 1, token) {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  params.append('page', page)
  return api.get(`/v2/admin/bounties?${params.toString()}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminUpdateBountyStatus(bountyId, status, reason = '', token) {
  return api.put(`/v2/admin/bounties/${bountyId}/status?status=${status}&reason=${reason}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminGetSkills(page = 1, token) {
  return api.get(`/v2/admin/skills?page=${page}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminUpdateSkillStatus(skillId, status, token) {
  return api.put(`/v2/admin/skills/${skillId}/status?status=${status}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminGetUsers(page = 1, token) {
  return api.get(`/v2/admin/users?page=${page}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminUpdateUserStatus(userId, status, token) {
  return api.put(`/v2/admin/users/${userId}/status?status=${status}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function adminScanRisks(token) {
  return api.post('/v2/admin/scan-risks', {}, { headers: { Authorization: `Bearer ${token}` } }, { timeout: 60000 })
}

export async function adminGetAnalytics(token) {
  return api.get('/v2/admin/analytics', { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Cron Subscriptions ----

export async function registerCronProduct(data, token) {
  return api.post('/cron/register', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function subscribeCron(cronId, webhookUrl, token) {
  return api.post(`/cron/subscribe/${cronId}${webhookUrl ? `?webhook_url=${encodeURIComponent(webhookUrl)}` : ''}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getCronResults(subscriptionId, apiToken, limit = 20) {
  return api.get(`/cron/results/${subscriptionId}?token=${apiToken}&limit=${limit}`)
}

export async function cancelCronSubscription(subId, token) {
  return api.delete(`/cron/subscription/${subId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyCronSubscriptions(token) {
  return api.get('/cron/my-subscriptions', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyCrons(token) {
  return api.get('/cron/my-crons', { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Activities & Points ----

export async function getActivities(token) {
  return api.get('/activities', { headers: { Authorization: `Bearer ${token}` } })
}

export async function doCheckin(token) {
  return api.post('/activities/checkin', {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function claimTaskReward(taskId, token) {
  return api.post(`/activities/tasks/${taskId}/claim`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getPointsBalance(token) {
  return api.get('/activities/points/balance', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getPointsHistory(token, limit = 50) {
  return api.get(`/activities/points/history?limit=${limit}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function redeemPoints(data, token) {
  return api.post('/activities/points/redeem', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function redeemPointsForQuota(token, hours) {
  return api.post('/sandbox/redeem-quota', { hours }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getLeaderboard(limit = 20) {
  return api.get(`/activities/leaderboard?limit=${limit}`)
}

// ---- User Agents ----

export async function createAgent(data, token) {
  return api.post('/agents', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyAgents(token) {
  return api.get('/agents', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getAgentDetail(agentId, token) {
  return api.get(`/agents/${agentId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function updateAgent(agentId, data, token) {
  return api.put(`/agents/${agentId}`, data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function deleteAgent(agentId, token) {
  return api.delete(`/agents/${agentId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function runAgent(agentId, inputText, token) {
  return api.post(`/agents/${agentId}/run`, { input_text: inputText }, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getAgentRuns(agentId, limit = 20, token) {
  return api.get(`/agents/${agentId}/runs?limit=${limit}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function scheduleAgentCron(agentId, cronExpression, token) {
  return api.post(`/agents/${agentId}/schedule?cron_expression=${encodeURIComponent(cronExpression)}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export default api

// ---- 沙盒/Sandbox 相关 ----
export async function getSandboxStatus(token) { return api.get('/sandbox/status', { headers: { Authorization: `Bearer ${token}` } }) }
export async function startSandbox(language, token) { return api.post(`/sandbox/start?language=${language}`, null, { headers: { Authorization: `Bearer ${token}` } }) }
export async function executeCode(code, language, encrypted, token) { return api.post('/sandbox/execute', { code, language, encrypted: encrypted || false }, { headers: { Authorization: `Bearer ${token}` } }) }
export async function stopSandbox(token) { return api.delete('/sandbox/stop', { headers: { Authorization: `Bearer ${token}` } }) }
export async function encryptAgent(agentName, sourceCode, token) { return api.post('/sandbox/encrypt-agent', { agent_name: agentName || 'my-agent', source_code: sourceCode }, { headers: { Authorization: `Bearer ${token}` } }) }
export async function decryptAgent(encryptedBlob, token) { return api.post('/sandbox/decrypt-agent', { encrypted_blob: encryptedBlob }, { headers: { Authorization: `Bearer ${token}` } }) }
export async function npcChat(token, message) { return api.post('/sandbox/chat', { message }, { headers: { Authorization: `Bearer ${token}` }, timeout: 35000 }) }
export async function sandboxChat(model, messages, stream, token) { return api.post('/sandbox/v1/chat/completions', { model, messages, stream: stream || false }, { headers: { Authorization: `Bearer ${token}` }, timeout: 60000 }) }
export async function getSandboxApiDocs(token) { return api.get('/sandbox/api-docs', { headers: { Authorization: `Bearer ${token}` } }) }

// ---- 开发者 API Key ----
export async function listApiKeys(token) { return api.get('/sandbox/api-keys', { headers: { Authorization: `Bearer ${token}` } }) }
export async function createApiKey(name, permissions, rateLimit, token) { return api.post('/sandbox/api-keys', { name, permissions, rate_limit: rateLimit || 100 }, { headers: { Authorization: `Bearer ${token}` } }) }
export async function revokeApiKey(keyId, token) { return api.delete(`/sandbox/api-keys/${keyId}`, { headers: { Authorization: `Bearer ${token}` } }) }
export async function getCliDownload(token) { return api.get('/sandbox/cli-download', { headers: { Authorization: `Bearer ${token}` } }) }
