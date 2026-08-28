<template>
  <div class="admin-layout">
    <!-- 사이드바 -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">📚</span>
        <div>
          <div class="logo-title">STRIPE</div>
          <div class="logo-sub">관리자</div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <RouterLink to="/admin" class="nav-item" exact>
          <span class="nav-icon">🏠</span>
          <span>대시보드</span>
        </RouterLink>
        <RouterLink to="/admin/users" class="nav-item">
          <span class="nav-icon">👥</span>
          <span>사용자 관리</span>
        </RouterLink>
        <RouterLink to="/admin/diagnoses" class="nav-item">
          <span class="nav-icon">🗂️</span>
          <span>진단 결과</span>
        </RouterLink>
        <RouterLink to="/admin/stats" class="nav-item">
          <span class="nav-icon">📊</span>
          <span>진단 통계</span>
        </RouterLink>
        <RouterLink to="/admin/consents" class="nav-item">
          <span class="nav-icon">📋</span>
          <span>보호자 동의</span>
        </RouterLink>
        <RouterLink to="/admin/pilot" class="nav-item">
          <span class="nav-icon">🔬</span>
          <span>파일럿 분석</span>
        </RouterLink>
        <RouterLink to="/admin/texts" class="nav-item">
          <span class="nav-icon">📝</span>
          <span>텍스트 풀</span>
        </RouterLink>
        <RouterLink to="/admin/books" class="nav-item">
          <span class="nav-icon">📚</span>
          <span>도서 카탈로그</span>
        </RouterLink>
        <RouterLink to="/admin/disposals" class="nav-item">
          <span class="nav-icon">🗑</span>
          <span>개인정보 파기</span>
        </RouterLink>
        <RouterLink to="/admin/system" class="nav-item">
          <span class="nav-icon">⚙️</span>
          <span>시스템 모니터링</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <!-- 관리자도 학생이 보는 화면을 직접 확인할 수 있게 -->
        <RouterLink to="/student" class="student-btn">
          <span>👀</span> 학생 화면 보기
        </RouterLink>
        <button class="logout-btn" @click="handleLogout()">
          <span>🚪</span> 로그아웃
        </button>
      </div>
    </aside>

    <!-- 메인 콘텐츠 -->
    <div class="admin-main">
      <header class="admin-header">
        <div class="header-title">
          <slot name="title">대시보드</slot>
        </div>
        <div class="header-info">
          <span class="admin-badge">관리자</span>
          <span class="admin-name">Admin</span>
        </div>
      </header>
      <div class="admin-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
  background: #0f1117;
  font-family: 'Nunito', sans-serif;
}

/* 사이드바 */
.sidebar {
  width: 240px;
  background: #1a1d27;
  display: flex;
  flex-direction: column;
  padding: 1.5rem 0;
  position: fixed;
  height: 100vh;
  border-right: 1px solid #2a2d3e;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0 1.5rem 1.5rem;
  border-bottom: 1px solid #2a2d3e;
  margin-bottom: 1.5rem;
}
.logo-icon { font-size: 2rem; }
.logo-title { font-size: 1.2rem; font-weight: 900; color: #4ECDC4; }
.logo-sub { font-size: 0.7rem; color: #666; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0 0.8rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  text-decoration: none;
  color: #888;
  font-weight: 700;
  font-size: 0.9rem;
  transition: all 0.2s;
}
.nav-item:hover { background: #252836; color: #ccc; }
.nav-item.router-link-active { background: rgba(78, 205, 196, 0.15); color: #4ECDC4; }
.nav-icon { font-size: 1.1rem; width: 24px; text-align: center; }

.sidebar-footer {
  padding: 1rem 1.2rem 0;
  border-top: 1px solid #2a2d3e;
  margin-top: 1rem;
}
.logout-btn {
  width: 100%;
  background: none;
  border: 1px solid #2a2d3e;
  color: #666;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}
.logout-btn:hover { border-color: #FF6B6B; color: #FF6B6B; }

.student-btn {
  display: flex; align-items: center; justify-content: center; gap: 0.4rem;
  border: 1px solid #2a2d3e; border-radius: 8px; padding: 0.6rem;
  color: #888; font-size: 0.85rem; font-weight: 700; text-decoration: none;
  margin-bottom: 0.5rem; transition: all 0.2s;
}
.student-btn:hover { border-color: #4ECDC4; color: #4ECDC4; }

/* 메인 */
.admin-main {
  flex: 1;
  margin-left: 240px;
  display: flex;
  flex-direction: column;
}

.admin-header {
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3e;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-title {
  font-size: 1.1rem;
  font-weight: 800;
  color: #fff;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}
.admin-badge {
  background: rgba(78, 205, 196, 0.15);
  color: #4ECDC4;
  font-size: 0.75rem;
  font-weight: 800;
  padding: 0.25rem 0.7rem;
  border-radius: 99px;
  border: 1px solid rgba(78, 205, 196, 0.3);
}
.admin-name { color: #888; font-size: 0.9rem; font-weight: 700; }

.admin-content {
  flex: 1;
  padding: 2rem;
  background: #0f1117;
}

/* ── 좁은 화면 대응 ─────────────────────────────────────────────────────
   원인 두 가지가 겹쳐 375px 에서 문서 폭이 1600px 까지 벌어졌다.

   ① .admin-main 이 flex 아이템인데 min-width 기본값이 auto 라, 내부 표가
      최소폭(860px)을 요구하면 축소되지 않고 그대로 밀어낸다.
      → min-width: 0 을 줘야 flex 아이템이 실제로 줄어든다.
   ② 사이드바 240px 고정 + margin-left 240px. 375px 에서 콘텐츠에 135px 만
      남는다.

   관리자 화면은 표 중심이라 좁은 폭에서 완전히 쓰기는 어렵다. 다만 파일럿
   현장에서 태블릿으로 진행 현황을 확인하는 상황은 있을 수 있어, 최소한
   '가로 스크롤로 화면이 깨지는' 상태는 없앤다. 표 자체는 각 화면의
   .table-wrap(overflow-x: auto)이 처리한다.                              */
.admin-main { min-width: 0; }
.admin-content { min-width: 0; }

@media (max-width: 900px) {
  /* 사이드바를 아이콘만 남긴 좁은 바로 줄인다 — 화면 전환은 유지된다.
     메뉴 이름은 title 속성으로 남겨 hover 시 확인할 수 있다. */
  .sidebar { width: 60px; padding: 1rem 0; }
  .sidebar-logo { padding: 0 0 1rem; justify-content: center; gap: 0; }
  .sidebar-logo > div { display: none; }          /* 로고 텍스트(STRIPE·관리자) */
  .logo-icon { font-size: 1.5rem; }

  .sidebar-nav { padding: 0 0.4rem; }
  .nav-item { justify-content: center; padding: 0.7rem 0; gap: 0; }
  .nav-item > span:not(.nav-icon) { display: none; }   /* 메뉴 이름 */
  .nav-icon { width: auto; }

  .sidebar-footer { padding: 0.8rem 0.4rem 0; }
  .student-btn, .logout-btn { padding: 0.55rem 0; justify-content: center; gap: 0; }
  .student-btn { font-size: 0; }                  /* 이모지만 남긴다 */
  .student-btn span, .logout-btn span { font-size: 1rem; }
  .logout-btn { font-size: 0; }

  .admin-main { margin-left: 60px; }

  .admin-header { padding: 0.8rem 1rem; }
  .admin-content { padding: 1rem 0.75rem; }
}

@media (max-width: 560px) {
  .admin-content { padding: 0.75rem 0.5rem; }
  .admin-header { padding: 0.7rem 0.75rem; }
}
</style>
