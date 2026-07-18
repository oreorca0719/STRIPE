import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { guest: true }
    },
    {
      path: '/change-credentials',
      name: 'change-credentials',
      component: () => import('@/views/ChangeCredentialsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/student',
      name: 'student-home',
      component: () => import('@/views/StudentHomeView.vue'),
      meta: { requiresAuth: true, role: 'student' }
    },
    {
      path: '/student/diagnosis',
      name: 'diagnosis',
      component: () => import('@/views/DiagnosisView.vue'),
      meta: { requiresAuth: true, role: 'student' }
    },
    {
      path: '/student/result',
      name: 'result',
      component: () => import('@/views/ResultView.vue'),
      meta: { requiresAuth: true, role: 'student' }
    },
    {
      path: '/admin',
      name: 'admin-dashboard',
      component: () => import('@/views/admin/AdminDashboardView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/views/admin/AdminUsersView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/admin/diagnoses',
      name: 'admin-diagnoses',
      component: () => import('@/views/admin/AdminDiagnosesView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/admin/stats',
      name: 'admin-stats',
      component: () => import('@/views/admin/AdminStatsView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/admin/texts',
      name: 'admin-texts',
      component: () => import('@/views/admin/AdminTextsView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/admin/system',
      name: 'admin-system',
      component: () => import('@/views/admin/AdminSystemView.vue'),
      meta: { requiresAuth: true, role: 'admin' }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login'
    }
  ],
})

// 라우트 가드
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')

  // 비로그인 상태에서 인증 필요 페이지 접근 → 로그인으로
  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }

  // 최초 로그인(임시 비밀번호) → 자격증명 변경 강제. 새로고침·직접 URL 접근도 차단.
  if (token && user?.must_change_password && to.name !== 'change-credentials') {
    return next('/change-credentials')
  }
  // 변경 완료 후 해당 페이지 재접근 시 역할별 홈으로
  if (token && user && !user.must_change_password && to.name === 'change-credentials') {
    return next(user.role === 'admin' ? '/admin' : '/student')
  }

  // 로그인 상태에서 guest 페이지 접근 → 역할별 홈으로
  if (to.meta.guest && token && user) {
    if (user.role === 'admin') return next('/admin')
    return next('/student')
  }

  // 역할 접근 제어
  // - 관리자: 학생 화면도 열람 가능(운영·검수 목적). 모든 페이지 접근 허용.
  // - 그 외: 자기 역할 페이지만 접근 가능 (학생의 /admin 접근 차단)
  if (to.meta.role && user && to.meta.role !== user.role && user.role !== 'admin') {
    return next('/student')
  }

  next()
})

export default router
