import axios from 'axios'

// 개발: Vite 프록시(/api → localhost:8000). 배포: VITE_API_BASE_URL 지정.
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const api = axios.create({ baseURL })

// 토큰이 있으면 Authorization 헤더 부착 (향후 보호 엔드포인트 대비)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
