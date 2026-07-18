<template>
  <AdminLayout @logout="handleLogout">
    <template #title>시스템</template>

    <div class="system-page">
      <div v-if="loading" class="loading">불러오는 중…</div>
      <div v-else-if="error" class="err-box">{{ error }}</div>

      <template v-else-if="sys">
        <!-- 서비스 상태 -->
        <div class="section">
          <h2 class="section-title">서비스 상태</h2>
          <div class="service-grid">
            <div class="service-card" v-for="svc in services" :key="svc.name">
              <div class="svc-header">
                <span class="svc-icon">{{ svc.icon }}</span>
                <span class="svc-name">{{ svc.name }}</span>
                <span class="svc-status" :class="svc.status">
                  {{ svc.status === 'ok' ? '● 정상' : svc.status === 'off' ? '● 미사용' : '● 확인 필요' }}
                </span>
              </div>
              <div class="svc-detail">{{ svc.detail }}</div>
            </div>
          </div>
        </div>

        <!-- 콘텐츠 현황 -->
        <div class="section">
          <h2 class="section-title">콘텐츠 현황</h2>
          <div class="stat-row">
            <div class="stat-box"><span class="sv">{{ ov?.texts_approved ?? '-' }}</span><span class="sl">승인 지문</span></div>
            <div class="stat-box"><span class="sv">{{ ov?.questions_approved ?? '-' }}</span><span class="sl">승인 문항</span></div>
            <div class="stat-box"><span class="sv">{{ ov?.students ?? '-' }}</span><span class="sl">학생</span></div>
            <div class="stat-box"><span class="sv">{{ ov?.diagnosis_completed ?? '-' }}</span><span class="sl">완료 진단</span></div>
          </div>
        </div>

        <!-- 배포 구성 -->
        <div class="section">
          <h2 class="section-title">배포 구성</h2>
          <div class="infra-grid">
            <div class="infra-card" v-for="r in infra" :key="r.name">
              <div class="infra-icon">{{ r.icon }}</div>
              <div class="infra-info">
                <div class="infra-name">{{ r.name }}</div>
                <div class="infra-value">{{ r.value }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/admin/AdminLayout.vue'
import { api } from '@/api'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const sys = ref<any>(null)
const ov = ref<any>(null)

const services = computed(() => {
  if (!sys.value) return []
  const s = sys.value
  return [
    { icon: '⚡', name: 'FastAPI 서버', status: 'ok',
      detail: `가동 중 · 환경 ${s.app.env}` },
    { icon: '🗄️', name: 'PostgreSQL', status: s.database.ok ? 'ok' : 'warn',
      detail: s.database.ok
        ? `${s.database.version || 'PostgreSQL'} · 마이그레이션 ${s.database.migration || '-'}`
        : '연결 실패' },
    { icon: '🌐', name: 'HTTPS (Caddy)', status: isHttps ? 'ok' : 'warn',
      detail: isHttps
        ? `${currentHost} · Let's Encrypt 자동 갱신`
        : `${currentHost} · 로컬 개발(HTTP) — 배포 환경에서만 TLS 적용` },
    { icon: '🤖', name: 'Claude API', status: s.app.llm_configured ? 'ok' : 'off',
      detail: s.app.llm_configured ? `연결됨 · ${s.app.llm_model}` : '미설정 (리포트는 템플릿으로 동작)' },
    { icon: '🎤', name: 'Clova STT', status: s.app.stt_configured ? 'ok' : 'off',
      detail: s.app.stt_configured ? '연결됨' : '미설정 (음독 진단 MVP1 범위 밖)' },
    { icon: '💾', name: 'DB 백업', status: 'ok', detail: s.deployment.backup },
  ]
})

const currentHost = typeof window !== 'undefined' ? window.location.host : ''
const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:'

const infra = computed(() => {
  if (!sys.value) return []
  const d = sys.value.deployment
  return [
    { icon: '🖥️', name: '플랫폼', value: d.platform },
    { icon: '🐳', name: '런타임', value: d.runtime },
    { icon: '🔒', name: 'TLS', value: d.tls },
    { icon: '🔄', name: 'CI/CD', value: d.cicd },
    { icon: '🌏', name: '접속 주소', value: currentHost },
  ]
})

async function load() {
  try {
    const [s, o] = await Promise.all([
      api.get('/api/admin/system'),
      api.get('/api/admin/overview'),
    ])
    sys.value = s.data
    ov.value = o.data
  } catch (e: any) {
    error.value = e?.response?.status === 403
      ? '관리자 권한이 필요합니다.'
      : '시스템 정보를 불러오지 못했습니다.'
  } finally { loading.value = false }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
/* 관리자 포털 다크 테마에 맞춤 (#0f1117 배경 / #1a1d27 카드 / #2a2d3e 테두리) */
.system-page { display: flex; flex-direction: column; gap: 2rem; }
.loading, .err-box {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 2.5rem; text-align: center; color: #666; font-weight: 700;
}
.err-box { color: #FF6B6B; }
.section { display: flex; flex-direction: column; gap: 1rem; }
.section-title { font-size: 0.95rem; font-weight: 800; color: #fff; }

.service-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
.service-card {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 1.3rem; display: flex; flex-direction: column; gap: 0.5rem;
}
.svc-header { display: flex; align-items: center; gap: 0.6rem; }
.svc-icon { font-size: 1.2rem; }
.svc-name { font-weight: 800; color: #fff; flex: 1; font-size: 0.92rem; }
.svc-status { font-size: 0.75rem; font-weight: 800; }
.svc-status.ok { color: #4ECDC4; }
.svc-status.warn { color: #FFE66D; }
.svc-status.off { color: #555; }
.svc-detail { font-size: 0.82rem; color: #888; font-weight: 600; line-height: 1.5; }

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.stat-box {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 1.3rem; display: flex; flex-direction: column; align-items: center; gap: 0.3rem;
}
.sv { font-size: 1.8rem; font-weight: 900; color: #4ECDC4; }
.sl { font-size: 0.8rem; font-weight: 700; color: #666; }

.infra-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.infra-card {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 1.2rem; display: flex; align-items: flex-start; gap: 0.9rem;
}
.infra-icon { font-size: 1.3rem; }
.infra-name { font-size: 0.75rem; font-weight: 800; color: #555; margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.04em; }
.infra-value { font-size: 0.86rem; font-weight: 700; color: #ccc; word-break: break-all; line-height: 1.5; }

@media (max-width: 720px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
</style>
