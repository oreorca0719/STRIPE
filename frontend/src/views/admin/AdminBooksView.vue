<template>
  <AdminLayout @logout="handleLogout">
    <template #title>도서 카탈로그</template>

    <div class="books-page">
      <p class="page-note">
        학생에게 추천할 실제 도서다. 진단 지문(텍스트 풀)과 다른 자산이며,
        <strong>승인된 책만</strong> 추천에 나간다.
        데이터 확보 방안은 결정 대기 중이다(STR-108).
      </p>

      <!-- 커버리지 — 어느 칸을 채워야 하는지가 곧 확보 목표다 -->
      <section class="panel">
        <div class="panel-head">
          <h2>구성 현황</h2>
          <p class="sub">
            학년군 × 장르 × 난도 조합별 승인 도서 수. 진단 결과가 어느 칸으로 떨어져도
            추천할 책이 있으려면 모든 칸에 최소 1권이 필요하다.
          </p>
        </div>

        <div v-if="!data" class="empty-inline">불러오는 중…</div>
        <div v-else class="cov">
          <div class="cov-row cov-head">
            <span></span>
            <span v-for="c in COMBOS" :key="c.key">{{ c.label }}</span>
          </div>
          <div v-for="g in GRADES" :key="g.key" class="cov-row">
            <span class="cov-grade">{{ g.label }}</span>
            <span v-for="c in COMBOS" :key="c.key"
                  class="cell" :class="cellClass(g.key, c.key)">
              {{ data.coverage[g.key][c.key] || '-' }}
            </span>
          </div>
        </div>
      </section>

      <!-- 목록 -->
      <section class="panel">
        <div class="panel-head">
          <h2>
            도서 목록
            <span class="count-chip">{{ data?.total ?? 0 }}권</span>
            <span class="count-chip ok">승인 {{ data?.approved ?? 0 }}</span>
          </h2>
        </div>

        <div v-if="!data?.books?.length" class="empty-box">
          <div class="empty-icon">📚</div>
          <h3>아직 등록된 도서가 없습니다</h3>
          <p>
            데이터 확보 방안(STR-108)이 정해지면 아래 경로로 넣습니다.<br />
            스키마와 적재 경로는 이미 준비돼 있어 <strong>목록만 채우면 바로 동작</strong>합니다.
          </p>
          <pre class="cmd">python scripts/load_books.py --template   # 예시 파일 생성
python scripts/load_books.py --file scripts/generated/books.json</pre>
        </div>

        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>제목</th><th>저자</th><th>학년군</th><th>장르</th>
                <th>난도</th><th title="난도를 무엇을 근거로 매겼는가">난도 근거</th>
                <th>쪽수</th><th>주제</th><th>승인</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in data.books" :key="b.id" :class="{ inactive: !b.is_active }">
                <td class="title-cell">{{ b.title }}</td>
                <td>{{ b.author || '—' }}</td>
                <td>{{ b.grade_group === 'G4_G6' ? '초4~6' : '중1' }}</td>
                <td>{{ b.genre === 'narrative' ? '이야기책' : '지식책' }}</td>
                <td><span class="lv-chip" :class="b.difficulty">{{ diffKo(b.difficulty) }}</span></td>
                <td class="dim">{{ srcKo(b.difficulty_source) }}</td>
                <td>{{ b.page_count ?? '—' }}</td>
                <td class="dim">{{ (b.topic_tags || []).join(', ') || '—' }}</td>
                <td>
                  <span v-if="b.review_status === 'approved'" class="ok-chip">승인</span>
                  <span v-else class="warn-chip">{{ b.review_status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/admin/AdminLayout.vue'
import { api } from '@/api'

const router = useRouter()
const data = ref<any>(null)

const GRADES = [
  { key: 'G4_G6', label: '초4~초6' },
  { key: 'G7', label: '중1' },
]
const COMBOS = [
  { key: 'narrative_easy', label: '이야기 · 쉬움' },
  { key: 'narrative_normal', label: '이야기 · 보통' },
  { key: 'narrative_hard', label: '이야기 · 어려움' },
  { key: 'expository_easy', label: '지식 · 쉬움' },
  { key: 'expository_normal', label: '지식 · 보통' },
  { key: 'expository_hard', label: '지식 · 어려움' },
]

function diffKo(d: string) {
  return ({ easy: '쉬움', normal: '보통', hard: '어려움' } as any)[d] || d
}
// 난도를 어디서 가져왔는지 — 추천이 어긋났을 때 어느 출처가 부정확했는지 추적한다
function srcKo(s: string | null) {
  return ({ publisher: '출판사 표기', curriculum_list: '권장도서 목록',
            manual: '직접 판단', readability: '자체 산출' } as any)[s || ''] || (s || '—')
}
function cellClass(gg: string, combo: string) {
  return (data.value?.coverage?.[gg]?.[combo] || 0) > 0 ? 'filled' : 'empty'
}

function handleLogout() { router.push('/login') }

onMounted(async () => {
  try { data.value = (await api.get('/api/admin/books')).data }
  catch { data.value = null }
})
</script>

<style scoped>
.books-page { display: flex; flex-direction: column; gap: 1.2rem; }
.page-note { color: #8b90a5; font-size: 0.9rem; line-height: 1.6; }
.page-note strong { color: #e8eaf2; }

.panel { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 1.4rem; }
.panel-head { margin-bottom: 1rem; }
.panel-head h2 { font-size: 1.05rem; font-weight: 800; color: #e8eaf2; }
.sub { font-size: 0.84rem; color: #8b90a5; margin-top: 0.25rem; line-height: 1.6; }
.count-chip {
  background: #2a2d3e; color: #8b90a5; font-size: 0.75rem;
  padding: 0.1rem 0.5rem; border-radius: 99px; margin-left: 0.4rem;
}
.count-chip.ok { background: rgba(78,205,196,0.15); color: #4ECDC4; }

.cov { display: flex; flex-direction: column; gap: 0.4rem; overflow-x: auto; }
.cov-row {
  display: grid; grid-template-columns: 90px repeat(6, minmax(88px, 1fr)); gap: 0.4rem;
}
.cov-head span { font-size: 0.72rem; color: #8b90a5; text-align: center; font-weight: 700; }
.cov-grade { font-size: 0.82rem; color: #d7dae8; font-weight: 700; display: flex; align-items: center; }
.cell {
  text-align: center; padding: 0.5rem; border-radius: 6px;
  font-weight: 800; font-size: 0.9rem;
}
.cell.filled { background: rgba(78,205,196,0.14); color: #4ECDC4; }
.cell.empty { background: rgba(255,107,107,0.12); color: #FF6B6B; }

.empty-box { text-align: center; padding: 2.5rem 1rem; }
.empty-icon { font-size: 2.6rem; margin-bottom: 0.8rem; }
.empty-box h3 { font-size: 1rem; font-weight: 800; color: #e8eaf2; margin-bottom: 0.5rem; }
.empty-box p { color: #8b90a5; font-size: 0.88rem; line-height: 1.7; margin-bottom: 1rem; }
.empty-box strong { color: #4ECDC4; }
.cmd {
  display: inline-block; text-align: left; background: #0f1117;
  border: 1px solid #2a2d3e; border-radius: 8px; padding: 0.8rem 1rem;
  color: #8b90a5; font-size: 0.78rem; font-family: ui-monospace, monospace;
  white-space: pre; overflow-x: auto; max-width: 100%;
}

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.data-table th, .data-table td {
  padding: 0.6rem; text-align: left; border-bottom: 1px solid #2a2d3e; white-space: nowrap;
}
.data-table th { color: #8b90a5; font-weight: 700; font-size: 0.78rem; }
.data-table td { color: #d7dae8; }
.data-table tr.inactive { opacity: 0.45; }
.title-cell { max-width: 260px; overflow: hidden; text-overflow: ellipsis; }

.lv-chip { padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.74rem; font-weight: 800; }
.lv-chip.easy { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.lv-chip.normal { background: rgba(255,230,109,0.15); color: #FFE66D; }
.lv-chip.hard { background: rgba(255,107,107,0.15); color: #FF6B6B; }
.ok-chip { background: rgba(78,205,196,0.15); color: #4ECDC4; font-size: 0.74rem; font-weight: 800; padding: 0.15rem 0.5rem; border-radius: 99px; }
.warn-chip { background: rgba(255,230,109,0.15); color: #FFE66D; font-size: 0.74rem; font-weight: 800; padding: 0.15rem 0.5rem; border-radius: 99px; }
.dim { color: #6b7085; }
.empty-inline { color: #6b7085; font-size: 0.85rem; padding: 0.6rem 0; }
</style>
