import client from './client'

export const authAPI = {
  login: (data) => client.post('/auth/login', data),
  register: (data) => client.post('/auth/register', data),
}

export const playerAPI = {
  getProfile: () => client.get('/player/profile'),
  getShadow: () => client.get('/player/shadow'),
  allocateStats: (allocations) => client.post('/player/allocate-stats', { allocations }),
}

export const questsAPI = {
  list: (params) => client.get('/quests', { params }),
  create: (data) => client.post('/quests/create', data),
  generate: (data) => client.post('/quests/generate', data),
  generateDaily: () => client.post('/quests/generate-daily'),
  templates: (params) => client.get('/quests/templates', { params }),
  analyze: (data) => client.post('/quests/analyze', data),
  complete: (questId) => client.post(`/quests/${questId}/complete`),
  fail: (questId) => client.post(`/quests/${questId}/fail`),
  delete: (questId) => client.delete(`/quests/${questId}`),
  submitMetrics: (questId, metrics) => client.post(`/quests/${questId}/submit-metrics`, { metrics }),
}

export const analyticsAPI = {
  getOverview: () => client.get('/analytics/overview'),
  getStats: () => client.get('/analytics/stats'),
  getHistory: () => client.get('/analytics/history'),
}

export const inventoryAPI = {
  list: () => client.get('/inventory'),
  use: (itemId) => client.post('/inventory/use', { item_id: itemId }),
}

export const shopAPI = {
  getItems: (type) => client.get('/shop/items', { params: { type } }),
  buy: (slug, quantity = 1) => client.post(`/shop/buy/${slug}`, null, { params: { quantity } }),
}

export const aiAPI = {
  generateGoal: (goal) => client.post('/ai/generate', { goal }),
  generateAndSave: (goal) => client.post('/ai/generate-and-save', { goal }),
  calculateXP: (data) => client.post('/ai/calculate-xp', data),
}

export const adaptiveAPI = {
  getDaily:       (force = false) => client.get('/adaptive/daily', force ? { params: { force: true } } : {}),
  generate:       (category)     => client.get('/adaptive/generate', { params: { category } }),
  chooseTier:     (data)         => client.post('/adaptive/choose', data),
  getMindset:     ()             => client.get('/adaptive/mindset'),
  getHistory:     (params)       => client.get('/adaptive/history', { params }),
  listCustom:     (category)     => client.get('/adaptive/custom', category ? { params: { category } } : {}),
  createCustom:   (data)         => client.post('/adaptive/custom', data),
  updateCustom:   (id, data)     => client.put(`/adaptive/custom/${id}`, data),
  deleteCustom:   (id)           => client.delete(`/adaptive/custom/${id}`),
  dismissSystem:  (data)         => client.post('/adaptive/system/dismiss', data),
  restoreSystem:  (templateId)   => client.delete(`/adaptive/system/dismiss/${templateId}`),
  getDomains:     ()             => client.get('/domains'),
}

// Legacy alias for backward compatibility
export const dashboardAPI = {
  getOverview: () => client.get('/player/profile'),
}

export default client
