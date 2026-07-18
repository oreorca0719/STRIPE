<template>
  <AdminLayout @logout="handleLogout">
    <template #title>텍스트 풀 관리</template>

    <div class="texts-page">
      <!-- 필터 + 추가 버튼 -->
      <div class="toolbar">
        <div class="filters">
          <select v-model="filterGrade">
            <option value="">전체 학년</option>
            <option v-for="g in gradeOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
          </select>
          <select v-model="filterGenre">
            <option value="">전체 장르</option>
            <option value="narrative">이야기글 (서사)</option>
            <option value="expository">설명글 (정보)</option>
          </select>
          <select v-model="filterLevel">
            <option value="">전체 난도</option>
            <option value="easy">쉬움</option>
            <option value="normal">보통</option>
            <option value="hard">어려움</option>
          </select>
        </div>
        <span class="pool-count">총 {{ filtered.length }}편</span>
      </div>

      <!-- 원칙 안내 -->
      <div class="principle-banner">
        <span>📋</span>
        <div>
          <strong>이은주(2026) 텍스트 선정 7원칙 적용 필요</strong>
          <span> — 배경지식 통제 · 문화 편향 배제 · 장르 2종 이상 · 학년별 어휘 수준 · 적정 길이 · 독립성 · 중립성</span>
        </div>
      </div>

      <!-- 테이블 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>코드</th>
              <th>제목</th>
              <th>학년군</th>
              <th>장르</th>
              <th>난도</th>
              <th>음절 수</th>
              <th>문항</th>
              <th>주제</th>
              <th>승인</th>
              <th>출처</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="10"><div class="empty-state"><span>⏳</span><span>불러오는 중…</span></div></td></tr>
            <tr v-else-if="!filtered.length"><td colspan="10">
              <div class="empty-state"><span>🔍</span><span>조건에 맞는 텍스트가 없습니다</span></div>
            </td></tr>
            <tr v-else v-for="t in filtered" :key="t.id">
              <td class="mono">{{ t.text_code }}</td>
              <td class="title-cell">{{ t.title }}</td>
              <td>{{ t.grade_group === 'G4_G6' ? '초4~6' : '중1' }}</td>
              <td>{{ t.genre === 'narrative' ? '이야기글' : '설명글' }}</td>
              <td><span class="lv-chip" :class="t.difficulty">{{ diffKo(t.difficulty) }}</span></td>
              <td>{{ t.syllable_count }}</td>
              <td>{{ t.question_count }}개</td>
              <td>{{ (t.topic_tags || []).join(', ') }}</td>
              <td><span class="ok-chip" v-if="t.review_status === 'approved'">승인</span>
                  <span class="warn-chip" v-else>{{ t.review_status }}</span></td>
              <td>{{ t.created_by_role === 'ai' ? 'AI 생성' : (t.created_by_role || '-') }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 구성 현황 -->
      <div class="coverage-panel">
        <h2 class="panel-title">텍스트 풀 구성 현황</h2>
        <p class="coverage-desc">
          학년군 × 장르 × 난도 조합별 승인 지문 수. 적응형 진단이 막히지 않으려면 각 칸에 최소 1편 이상 필요합니다.
        </p>
        <div class="coverage-grid">
          <div class="coverage-header">
            <span></span>
            <span>이야기글 (쉬움)</span>
            <span>이야기글 (보통)</span>
            <span>이야기글 (어려움)</span>
            <span>설명글 (쉬움)</span>
            <span>설명글 (보통)</span>
            <span>설명글 (어려움)</span>
          </div>
          <div class="coverage-row" v-for="g in gradeOptions" :key="g.value">
            <span class="grade-name">{{ g.label }}</span>
            <span v-for="c in coverageCells(g.value)" :key="c.key"
                  class="cell" :class="c.n > 0 ? 'filled' : 'empty'">{{ c.n || '-' }}</span>
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
const filterGrade = ref('')
const filterGenre = ref('')
const filterLevel = ref('')

const texts = ref<any[]>([])
const loading = ref(true)

// 실제 스키마의 학년군(G4_G6 / G7) 기준
const gradeOptions = [
  { value: 'G4_G6', label: '초4~초6' },
  { value: 'G7', label: '중1' },
]

function diffKo(d: string) {
  return ({ easy: '쉬움', normal: '보통', hard: '어려움' } as any)[d] || d
}

const filtered = computed(() => texts.value.filter(t =>
  (!filterGrade.value || t.grade_group === filterGrade.value) &&
  (!filterGenre.value || t.genre === filterGenre.value) &&
  (!filterLevel.value || t.difficulty === filterLevel.value)
))

// 학년군별 (장르 × 난도) 6칸 커버리지
function coverageCells(gradeGroup: string) {
  const combos = [
    ['narrative', 'easy'], ['narrative', 'normal'], ['narrative', 'hard'],
    ['expository', 'easy'], ['expository', 'normal'], ['expository', 'hard'],
  ]
  return combos.map(([genre, diff]) => ({
    key: `${gradeGroup}-${genre}-${diff}`,
    n: texts.value.filter(t =>
      t.grade_group === gradeGroup && t.genre === genre &&
      t.difficulty === diff && t.review_status === 'approved').length,
  }))
}

async function load() {
  try {
    const r = await api.get('/api/admin/texts')
    texts.value = r.data
  } catch { texts.value = [] } finally { loading.value = false }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.texts-page { display: flex; flex-direction: column; gap: 1.2rem; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1rem 1.5rem;
}
.filters { display: flex; gap: 0.6rem; }
select {
  background: #252836; border: 1px solid #2a2d3e; color: #aaa;
  padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;
  font-family: 'Nunito', sans-serif; outline: none; cursor: pointer;
}
select:focus { border-color: #4ECDC4; }

.add-btn {
  background: #4ECDC4; color: #0f1117; border: none;
  padding: 0.6rem 1.5rem; border-radius: 8px;
  font-size: 0.9rem; font-weight: 800; cursor: pointer; transition: all 0.2s;
}
.add-btn:hover { background: #38b2ab; }

.principle-banner {
  background: rgba(78,205,196,0.08); border: 1px solid rgba(78,205,196,0.2);
  border-radius: 12px; padding: 1rem 1.5rem;
  display: flex; align-items: flex-start; gap: 0.8rem;
  font-size: 0.85rem; color: #888;
}
.principle-banner span:first-child { font-size: 1.2rem; flex-shrink: 0; }
.principle-banner strong { color: #4ECDC4; }

.table-wrap {
  background: #1a1d27; border: 1px solid #2a2d3e;
  border-radius: 16px; overflow: hidden;
}
.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  text-align: left; padding: 1rem 1.2rem;
  font-size: 0.72rem; font-weight: 800; color: #555;
  text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid #2a2d3e;
}
.data-table td { padding: 1rem 1.2rem; border-bottom: 1px solid #1e2130; }
.empty-state {
  display: flex; align-items: center; gap: 0.7rem; justify-content: center;
  padding: 2.5rem; color: #555; font-size: 0.9rem;
}

.coverage-panel {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1.5rem;
}
.panel-title { font-size: 0.95rem; font-weight: 800; color: #fff; margin-bottom: 0.4rem; }
.coverage-desc { font-size: 0.8rem; color: #555; margin-bottom: 1.2rem; }
.coverage-grid { display: flex; flex-direction: column; gap: 0.4rem; overflow-x: auto; }
.coverage-header, .coverage-row {
  display: grid; grid-template-columns: 100px repeat(6, 1fr);
  gap: 0.4rem; align-items: center;
}
.coverage-header span {
  font-size: 0.7rem; font-weight: 700; color: #555;
  text-align: center; padding: 0.4rem;
}
.grade-name { font-size: 0.8rem; color: #888; font-weight: 700; }
.cell {
  background: #252836; border-radius: 6px; padding: 0.5rem;
  text-align: center; font-size: 0.8rem; color: #444; font-weight: 700;
}
.cell.filled { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.cell.empty { background: rgba(255,107,107,0.08); color: #7a4a4a; }

/* 다크 테마 대응 */
.table-wrap { overflow-x: auto; }
.data-table { min-width: 900px; }
.data-table th, .data-table td { white-space: nowrap; }
.data-table td { color: #aaa; font-size: 0.87rem; }
.data-table td.title-cell { white-space: normal; min-width: 12rem; }
.data-table tbody tr:hover td { background: #1e2130; }
.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.75rem; color: #555; }
.title-cell { font-weight: 800; color: #fff; }
.lv-chip { padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.74rem; font-weight: 800; }
.lv-chip.easy { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.lv-chip.normal { background: rgba(255,230,109,0.15); color: #FFE66D; }
.lv-chip.hard { background: rgba(255,107,107,0.15); color: #FF6B6B; }
.ok-chip { background: rgba(78,205,196,0.15); color: #4ECDC4; padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.74rem; font-weight: 800; }
.warn-chip { background: #252836; color: #666; padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.74rem; font-weight: 800; }
.pool-count { font-weight: 800; color: #4ECDC4; font-size: 0.9rem; }
</style>
