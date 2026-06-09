<template>
  <main class="home">
    <div class="hero">
      <h1 class="title">STRIPE</h1>
      <p class="subtitle">읽기 능력 진단 · 처방 AI 서비스</p>
      <p class="status">🚧 서비스 준비 중입니다</p>
      <div class="api-status">
        <span :class="['dot', apiStatus]"></span>
        <span>API: {{ apiMessage }}</span>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const apiStatus = ref<'ok' | 'error' | 'loading'>('loading')
const apiMessage = ref('연결 중...')

onMounted(async () => {
  try {
    const res = await axios.get('/api/health')
    apiStatus.value = 'ok'
    apiMessage.value = res.data.status
  } catch {
    apiStatus.value = 'error'
    apiMessage.value = '연결 실패'
  }
})
</script>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0f;
}

.hero {
  text-align: center;
  color: #fff;
}

.title {
  font-size: 5rem;
  font-weight: 800;
  letter-spacing: 0.2em;
  margin: 0;
  color: #4f9cf9;
}

.subtitle {
  font-size: 1.2rem;
  color: #888;
  margin: 1rem 0;
}

.status {
  color: #666;
  margin: 2rem 0;
}

.api-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  font-size: 0.85rem;
  color: #555;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.ok { background: #4ade80; }
.dot.error { background: #f87171; }
.dot.loading { background: #fbbf24; animation: pulse 1s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
