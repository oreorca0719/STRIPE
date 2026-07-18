<template>
  <AdminLayout @logout="handleLogout">
    <template #title>진단 통계</template>

    <div class="stats-page">
      <!-- 요약 수치 -->
      <div class="stat-row">
        <div class="mini-stat" v-for="s in summaryStats" :key="s.label">
          <span class="mini-icon">{{ s.icon }}</span>
          <div>
            <div class="mini-value">{{ s.value }}</div>
            <div class="mini-label">{{ s.label }}</div>
          </div>
        </div>
      </div>

      <div v-if="!hasJudgments" class="empty-panel">
        <span>📊</span>
        <div>
          <strong>아직 완료된 진단이 없습니다</strong>
          <p>학생이 진단을 완주하면 판정 등급 분포와 평균 정답률이 집계됩니다.</p>
        </div>
      </div>

      <div class="charts-grid">
        <!-- 판정 등급 분포 -->
        <div class="chart-panel">
          <h2 class="panel-title">판정 등급 분포</h2>
          <p class="panel-sub">유창성 × 독해 매트릭스 판정 결과 (label_5)</p>
          <div class="bar-chart">
            <div class="bar-row" v-for="l in labelRows" :key="l.key">
              <span class="bar-label">{{ l.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: l.pct + '%', background: l.color }"></div>
              </div>
              <span class="bar-pct">{{ l.count }}명</span>
            </div>
          </div>
          <p class="note">※ 판정 경계값은 파일럿 전 잠정값입니다</p>
        </div>

        <!-- 텍스트 풀 분포 -->
        <div class="chart-panel">
          <h2 class="panel-title">텍스트 풀 분포</h2>
          <p class="panel-sub">승인된 지문의 장르 × 난도 구성</p>
          <div class="bar-chart">
            <div class="bar-row" v-for="t in textRows" :key="t.key">
              <span class="bar-label">{{ t.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: t.pct + '%', background: t.color }"></div>
              </div>
              <span class="bar-pct">{{ t.count }}편</span>
            </div>
          </div>
          <p v-if="!textRows.length" class="note">적재된 지문이 없습니다</p>
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
const stats = ref<any>(null)
const ov = ref<any>(null)

const hasJudgments = computed(() => (stats.value?.judgments_total ?? 0) > 0)

const summaryStats = computed(() => [
  { icon: '🎯', label: '완료 판정', value: stats.value?.judgments_total ?? '-' },
  { icon: '📈', label: '평균 정답률',
    value: stats.value?.avg_accuracy != null ? Math.round(stats.value.avg_accuracy * 100) + '%' : '-' },
  { icon: '📝', label: '진단 세션', value: ov.value?.diagnosis_sessions ?? '-' },
  { icon: '📚', label: '승인 지문', value: ov.value?.texts_approved ?? '-' },
])

const LABELS: Record<string, { name: string; color: string }> = {
  excellent: { name: '아주 잘함', color: '#4ECDC4' },
  observe:   { name: '잘함',     color: '#7ed6c4' },
  caution:   { name: '보통',     color: '#FFE66D' },
  risk:      { name: '조금 부족', color: '#ffab6b' },
  urgent:    { name: '도움 필요', color: '#FF6B6B' },
}

const labelRows = computed(() => {
  const dist = stats.value?.label_distribution || {}
  const total = stats.value?.judgments_total || 0
  return Object.keys(LABELS).map(k => ({
    key: k, name: LABELS[k].name, color: LABELS[k].color,
    count: dist[k] || 0,
    pct: total ? Math.round(((dist[k] || 0) / total) * 100) : 0,
  }))
})

const GENRE_KO: Record<string, string> = { narrative: '이야기글', expository: '설명글' }
const DIFF_KO: Record<string, string> = { easy: '쉬움', normal: '보통', hard: '어려움' }
const DIFF_COLOR: Record<string, string> = { easy: '#4ECDC4', normal: '#FFE66D', hard: '#FF6B6B' }

const textRows = computed(() => {
  const dist = stats.value?.text_distribution || []
  const max = Math.max(1, ...dist.map((d: any) => d.count))
  return dist.map((d: any) => ({
    key: `${d.genre}-${d.difficulty}`,
    name: `${GENRE_KO[d.genre] || d.genre} · ${DIFF_KO[d.difficulty] || d.difficulty}`,
    count: d.count, pct: Math.round((d.count / max) * 100),
    color: DIFF_COLOR[d.difficulty] || '#4ECDC4',
  }))
})

async function load() {
  try {
    const [s, o] = await Promise.all([
      api.get('/api/admin/stats'),
      api.get('/api/admin/overview'),
    ])
    stats.value = s.data; ov.value = o.data
  } catch { /* 권한 없음/오류 시 기본값 */ }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.stats-page { display: flex; flex-direction: column; gap: 1.2rem; }

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.mini-stat {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 1.2rem 1.4rem; display: flex; align-items: center; gap: 0.9rem;
}
.mini-icon { font-size: 1.5rem; }
.mini-value { font-size: 1.5rem; font-weight: 900; color: #fff; line-height: 1.2; }
.mini-label { font-size: 0.78rem; color: #666; font-weight: 700; }

.empty-panel {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  padding: 1.5rem; display: flex; align-items: center; gap: 1rem;
}
.empty-panel > span { font-size: 1.6rem; }
.empty-panel strong { color: #fff; font-size: 0.95rem; }
.empty-panel p { color: #666; font-size: 0.85rem; margin-top: 0.2rem; }

.charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.chart-panel {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1.5rem;
}
.panel-title { font-size: 0.95rem; font-weight: 800; color: #fff; }
.panel-sub { font-size: 0.78rem; color: #555; margin: 0.25rem 0 1.1rem; }

.bar-chart { display: flex; flex-direction: column; gap: 0.7rem; }
.bar-row { display: flex; align-items: center; gap: 0.8rem; }
.bar-label { font-size: 0.82rem; color: #aaa; font-weight: 700; width: 7rem; flex-shrink: 0; }
.bar-track { flex: 1; height: 10px; background: #252836; border-radius: 99px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 99px; transition: width 0.5s ease; }
.bar-pct { font-size: 0.78rem; color: #888; font-weight: 800; width: 3rem; text-align: right; flex-shrink: 0; }

.note { margin-top: 1rem; font-size: 0.75rem; color: #555; }

@media (max-width: 900px) {
  .charts-grid { grid-template-columns: 1fr; }
  .stat-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
