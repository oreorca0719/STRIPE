import axios from 'axios'
import router from '@/router'

// 개발: Vite 프록시(/api → localhost:8000). 배포: VITE_API_BASE_URL 지정.
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const api = axios.create({ baseURL })

// 토큰이 있으면 Authorization 헤더 부착 (향후 보호 엔드포인트 대비)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 로그인 시도 자체의 401(비밀번호 오류)은 만료가 아니므로 가로채지 않는다.
// 해당 화면이 "아이디 또는 비밀번호가 올바르지 않습니다"를 직접 보여줘야 한다.
const AUTH_ENDPOINTS = ['/api/auth/login', '/api/auth/change-credentials']

// 만료가 여러 요청에서 동시에 터져도 로그인 화면 이동은 한 번만 수행한다.
let redirecting = false

// 401 = 토큰 만료·무효. 아동 사용자는 콘솔을 보지 않으므로 화면에서 안내해야 한다.
// 토큰을 정리하고 로그인 화면으로 보내면서 사유를 쿼리로 넘긴다.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status
    const url: string = err?.config?.url || ''

    if (status === 401 && !AUTH_ENDPOINTS.some((p) => url.startsWith(p))) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')

      if (!redirecting) {
        redirecting = true
        const from = router.currentRoute.value.fullPath
        router
          .replace({ name: 'login', query: { reason: 'expired', from } })
          .finally(() => { redirecting = false })
      }
    }
    return Promise.reject(err)
  },
)
