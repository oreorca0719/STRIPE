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
        <RouterLink to="/admin/stats" class="nav-item">
          <span class="nav-icon">📊</span>
          <span>진단 통계</span>
        </RouterLink>
        <RouterLink to="/admin/texts" class="nav-item">
          <span class="nav-icon">📝</span>
          <span>텍스트 풀</span>
        </RouterLink>
        <RouterLink to="/admin/system" class="nav-item">
          <span class="nav-icon">⚙️</span>
          <span>시스템 모니터링</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
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
</style>
