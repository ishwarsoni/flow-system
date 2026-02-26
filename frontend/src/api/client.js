import axios from 'axios'

const API_BASE_URL = '/api'

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('flow_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('flow_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
