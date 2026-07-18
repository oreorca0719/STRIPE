<template>
  <AdminLayout @logout="handleLogout">
    <template #title>대시보드</template>

    <div class="dashboard">
      <!-- 요약 카드 -->
      <div class="stat-grid">
        <div class="stat-card" v-for="stat in stats" :key="stat.label">
          <div class="stat-icon">{{ stat.icon }}</div>
          <div class="stat-info">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
          <div class="stat-badge" :class="stat.color">{{ stat.change }}</div>
        </div>
      </div>

      <!-- 최근 활동 + 시스템 상태 -->
      <div class="bottom-grid">
        <div class="panel">
          <h2 class="panel-title">진단 판정 분포</h2>
          <div class="activity-list">
            <div v-if="!statsData || statsData.judgments_total === 0" class="activity-item coming-soon-item">
              <span>📊</span>
              <span>아직 완료된 진단이 없어요</span>
            </div>
            <template v-else>
              <div v-for="(cnt, label) in statsData.label_distribution" :key="label" class="dist-row">
                <span class="dist-name">{{ labelKo(label) }}</span>
                <div class="dist-bar">
                  <div class="dist-fill" :style="{ width: pct(cnt) + '%' }"></div>
                </div>
                <span class="dist-cnt">{{ cnt }}명</span>
              </div>
              <div class="dist-foot">
                총 {{ statsData.judgments_total }}건
                <span v-if="statsData.avg_accuracy != null">
                  · 평균 정답률 {{ Math.round(statsData.avg_accuracy * 100) }}%
                </span>
              </div>
            </template>
          </div>
        </div>

        <div class="panel">
          <h2 class="panel-title">시스템 상태</h2>
          <div class="system-list">
            <div class="system-item" v-for="s in systemStatus" :key="s.name">
              <span class="system-name">{{ s.name }}</span>
              <span class="system-dot" :class="s.status === 'ok' ? 'dot-ok' : 'dot-warn'"></span>
              <span class="system-status" :class="s.status === 'ok' ? 'text-ok' : 'text-warn'">
                {{ s.status === 'ok' ? '정상' : s.status === 'off' ? '미사용' : '확인 필요' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/admin/AdminLayout.vue'
import { api } from '@/api'

const router = useRouter()
const ov = ref<any>(null)
const sys = ref<any>(null)
const statsData = ref<any>(null)

const stats = computed(() => [
  { icon: '👨‍🎓', label: '학생', value: ov.value?.students ?? '-',
    change: `교사 ${ov.value?.teachers ?? 0}명`, color: 'badge-mint' },
  { icon: '📝', label: '진단 세션', value: ov.value?.diagnosis_sessions ?? '-',
    change: `완료 ${ov.value?.diagnosis_completed ?? 0}건`, color: 'badge-yellow' },
  { icon: '📚', label: '승인 지문', value: ov.value?.texts_approved ?? '-',
    change: `문항 ${ov.value?.questions_approved ?? 0}개`, color: 'badge-coral' },
  { icon: '🎯', label: '판정 완료', value: statsData.value?.judgments_total ?? '-',
    change: statsData.value?.avg_accuracy != null
      ? `평균 ${Math.round(statsData.value.avg_accuracy * 100)}%` : '집계 없음',
    color: 'badge-mint' },
])

const systemStatus = computed(() => {
  if (!sys.value) return []
  return [
    { name: 'FastAPI 서버', status: 'ok' },
    { name: 'PostgreSQL', status: sys.value.database.ok ? 'ok' : 'warn' },
    { name: 'HTTPS (Caddy)', status: 'ok' },
    { name: 'Claude API', status: sys.value.app.llm_configured ? 'ok' : 'off' },
    { name: 'DB 백업 (S3)', status: 'ok' },
  ]
})

const LABEL_KO: Record<string, string> = {
  excellent: '아주 잘함', observe: '잘함', caution: '보통', risk: '조금 부족', urgent: '도움 필요',
}
function labelKo(l: string | number) { return LABEL_KO[String(l)] || String(l) }
function pct(cnt: number) {
  const total = statsData.value?.judgments_total || 0
  return total ? Math.round((cnt / total) * 100) : 0
}

async function load() {
  try {
    const [o, s, st] = await Promise.all([
      api.get('/api/admin/overview'),
      api.get('/api/admin/system'),
      api.get('/api/admin/stats'),
    ])
    ov.value = o.data; sys.value = s.data; statsData.value = st.data
  } catch { /* 권한 없음/오류 시 기본값 표시 */ }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 1.5rem; }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.stat-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.stat-icon { font-size: 2rem; }
.stat-info { flex: 1; }
.stat-value { font-size: 1.8rem; font-weight: 900; color: #fff; }
.stat-label { font-size: 0.8rem; color: #666; font-weight: 600; margin-top: 0.1rem; }
.stat-badge {
  font-size: 0.75rem; font-weight: 700;
  padding: 0.3rem 0.7rem; border-radius: 99px;
}
.badge-mint { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.badge-yellow { background: rgba(255,230,109,0.15); color: #f5d800; }
.badge-coral { background: rgba(255,107,107,0.15); color: #FF6B6B; }

.bottom-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.panel {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 16px;
  padding: 1.5rem;
}
.panel-title { font-size: 0.95rem; font-weight: 800; color: #fff; margin-bottom: 1.2rem; }

.coming-soon-item {
  display: flex; align-items: center; gap: 0.7rem;
  color: #555; font-size: 0.9rem; padding: 1rem;
  background: #252836; border-radius: 10px;
}

.system-list { display: flex; flex-direction: column; gap: 0.8rem; }
.system-item {
  display: flex; align-items: center; gap: 0.7rem;
  padding: 0.7rem 1rem; background: #252836; border-radius: 10px;
}
.system-name { flex: 1; color: #aaa; font-size: 0.9rem; font-weight: 700; }
.system-dot { width: 8px; height: 8px; border-radius: 50%; }
.dot-ok { background: #4ECDC4; }
.dot-warn { background: #FFE66D; }
.text-ok { font-size: 0.8rem; font-weight: 700; color: #4ECDC4; }
.text-warn { font-size: 0.8rem; font-weight: 700; color: #FFE66D; }

/* 판정 분포 */
.dist-row { display: flex; align-items: center; gap: 0.8rem; padding: 0.45rem 0; }
.dist-name { font-size: 0.85rem; font-weight: 800; color: var(--navy); width: 5.2rem; flex-shrink: 0; }
.dist-bar { flex: 1; height: 10px; background: var(--gray-light); border-radius: 99px; overflow: hidden; }
.dist-fill { height: 100%; background: var(--mint); border-radius: 99px; transition: width 0.5s ease; }
.dist-cnt { font-size: 0.8rem; font-weight: 800; color: var(--gray); width: 3rem; text-align: right; flex-shrink: 0; }
.dist-foot { margin-top: 0.7rem; font-size: 0.82rem; font-weight: 700; color: var(--gray); text-align: right; }
</style>
