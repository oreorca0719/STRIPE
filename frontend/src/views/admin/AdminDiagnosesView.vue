<template>
  <AdminLayout @logout="handleLogout">
    <template #title>진단 결과</template>

    <div class="diag-page">
      <!-- 목록 -->
      <div v-if="!selected" class="list-wrap">
        <div class="toolbar">
          <div class="filters">
            <select v-model="filterStatus">
              <option value="">전체 상태</option>
              <option value="completed">완료</option>
              <option value="in_progress">진행 중</option>
            </select>
            <input v-model.trim="search" type="text" placeholder="학생 이름·아이디 검색" />
          </div>
          <span class="count">총 {{ filtered.length }}건</span>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th><th>학생</th><th>상태</th><th>회차</th>
                <th>판정</th><th>처방군</th><th>유창성</th><th>독해</th>
                <th>정답률</th><th>응시일</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading"><td colspan="11"><div class="empty">⏳ 불러오는 중…</div></td></tr>
              <tr v-else-if="!filtered.length"><td colspan="11"><div class="empty">📊 조건에 맞는 진단 기록이 없습니다</div></td></tr>
              <tr v-else v-for="d in filtered" :key="d.session_id" class="row" @click="open(d.session_id)">
                <td class="dim">{{ d.session_id }}</td>
                <td class="strong">{{ d.student_name }} <span class="dim">({{ d.username }})</span></td>
                <td>
                  <span class="chip" :class="d.status === 'completed' ? 'ok' : 'wait'">
                    {{ d.status === 'completed' ? '완료' : d.status === 'in_progress' ? '진행중' : d.status }}
                  </span>
                </td>
                <td>{{ d.total_rounds }}회</td>
                <td><span v-if="d.label_5" class="chip lab" :class="d.label_5">{{ labelKo(d.label_5) }}</span><span v-else class="dim">-</span></td>
                <td>{{ d.prescription_group || '-' }}</td>
                <td>{{ levelKo(d.fluency_level) }}</td>
                <td>{{ levelKo(d.comprehension_level) }}</td>
                <td>
                  <span v-if="d.overall_accuracy != null">
                    {{ Math.round(d.overall_accuracy * 100) }}%
                    <span class="dim">({{ d.total_correct }}/{{ d.total_questions }})</span>
                  </span><span v-else class="dim">-</span>
                </td>
                <td class="dim">{{ fmtDate(d.completed_at || d.started_at) }}</td>
                <td class="dim">›</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 상세 -->
      <div v-else class="detail-wrap">
        <button class="back-btn" @click="selected = null">← 목록으로</button>

        <div v-if="detailLoading" class="panel"><div class="empty">⏳ 불러오는 중…</div></div>

        <template v-else-if="detail">
          <div class="panel head-panel">
            <div>
              <h2 class="dt-title">{{ detail.student?.name }} <span class="dim">({{ detail.student?.username }})</span></h2>
              <p class="dt-sub">
                세션 #{{ detail.session.id }} · {{ detail.session.total_rounds }}회차 ·
                {{ fmtDate(detail.session.completed_at || detail.session.started_at) }}
                <span v-if="detail.session.reliability_flag !== 'normal'" class="warn">
                  · 신뢰도 {{ detail.session.reliability_flag }}
                </span>
              </p>
            </div>
            <div v-if="detail.judgment" class="head-judg">
              <span class="chip lab big" :class="detail.judgment.label_5">{{ labelKo(detail.judgment.label_5) }}</span>
              <span class="dim">처방군 {{ detail.judgment.prescription_group }}</span>
            </div>
          </div>

          <!-- 판정 요약 -->
          <div v-if="detail.judgment" class="panel">
            <h3 class="p-title">판정 요약</h3>
            <div class="kv-grid">
              <div class="kv"><span>유창성</span><b>{{ levelKo(detail.judgment.fluency_level) }}
                <span v-if="detail.judgment.fluency_value" class="dim">
                  ({{ detail.judgment.fluency_value }} {{ detail.judgment.fluency_unit }})</span></b></div>
              <div class="kv"><span>독해</span><b>{{ levelKo(detail.judgment.comprehension_level) }}</b></div>
              <div class="kv"><span>정답률</span><b>{{ Math.round((detail.judgment.overall_accuracy || 0) * 100) }}%
                <span class="dim">({{ detail.judgment.total_correct }}/{{ detail.judgment.total_questions }})</span></b></div>
              <div class="kv"><span>매트릭스</span><b>{{ detail.judgment.matrix_position }}</b></div>
              <div class="kv"><span>메타인지</span><b>{{ metaKo(detail.judgment.metacognition) }}</b></div>
              <div class="kv"><span>신뢰도</span><b>{{ detail.judgment.reliability_flag }}</b></div>
            </div>
            <p class="note">※ 판정 경계값은 파일럿 전 잠정값입니다</p>
          </div>

          <!-- 영역별 약점 (12셀) -->
          <div v-if="weaknessCells.length" class="panel">
            <h3 class="p-title">영역 × 장르 정답률</h3>
            <div class="cell-grid">
              <div v-for="c in weaknessCells" :key="c.key" class="wcell"
                   :class="c.acc == null ? 'na' : c.acc >= 0.8 ? 'good' : c.acc >= 0.5 ? 'mid' : 'bad'">
                <span class="wc-name">{{ c.label }}</span>
                <span class="wc-val">{{ c.acc == null ? '-' : Math.round(c.acc * 100) + '%' }}</span>
              </div>
            </div>
          </div>

          <!-- 회차별 상세 -->
          <div class="panel">
            <h3 class="p-title">회차별 응답</h3>
            <div v-for="r in detail.rounds" :key="r.round_number" class="round-block">
              <div class="round-head">
                <span class="rh-no">{{ r.round_number }}회차</span>
                <span class="rh-text">{{ r.text?.title || '-' }}</span>
                <span class="dim">{{ genreKo(r.genre) }} · {{ diffKo(r.difficulty) }}</span>
                <span class="rh-metrics">
                  <span v-if="r.betts_level" class="chip small">{{ bettsKo(r.betts_level) }}</span>
                  <span v-if="r.round_accuracy != null">{{ Math.round(r.round_accuracy * 100) }}%
                    ({{ r.correct_count }}/{{ r.total_questions }})</span>
                  <span v-if="r.silent_reading_time" class="dim">읽기 {{ Math.round(r.silent_reading_time) }}초
                    <template v-if="r.a4_syllable_per_sec">· {{ r.a4_syllable_per_sec }}음절/초</template>
                  </span>
                </span>
              </div>
              <div class="resp-list">
                <div v-for="(q, i) in r.responses" :key="i" class="resp" :class="q.is_correct ? 'ok' : 'no'">
                  <span class="r-mark">{{ q.is_correct ? '○' : '✗' }}</span>
                  <span class="r-area">{{ areaKo(q.target_area) }}</span>
                  <span class="r-q">{{ q.question_text }}</span>
                  <span class="r-ans">
                    학생 {{ q.student_answer }}번<template v-if="!q.is_correct"> · 정답 {{ q.answer_index }}번</template>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- 처방 · 리포트 -->
          <div class="two-col">
            <div v-if="detail.prescription" class="panel">
              <h3 class="p-title">처방</h3>
              <div class="kv"><span>유형</span><b>{{ detail.prescription.prescription_type }}</b></div>
              <div class="kv"><span>톤</span><b>{{ detail.prescription.type_tone }}</b></div>
              <div class="rec-list">
                <div v-for="(t, i) in (detail.prescription.recommended_texts || [])" :key="i" class="rec">
                  📖 {{ typeof t === 'string' ? t : (t.title || t.text_code || t.id) }}
                </div>
              </div>
            </div>
            <div v-if="detail.report" class="panel">
              <h3 class="p-title">학생 리포트
                <span class="dim">{{ detail.report.llm_polished ? '(LLM 다듬기 적용)' : '(템플릿)' }}</span>
              </h3>
              <p class="rep-label">{{ detail.report.report_content?.layer1?.label }}</p>
              <p class="rep-msg">{{ detail.report.report_content?.layer1?.encouragement }}</p>
              <div class="tag-row">
                <span v-for="(s, i) in (detail.report.report_content?.layer1?.strengths || [])" :key="i" class="chip small ok">{{ s }}</span>
              </div>
            </div>
          </div>
        </template>
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
const list = ref<any[]>([])
const loading = ref(true)
const selected = ref<number | null>(null)
const detail = ref<any>(null)
const detailLoading = ref(false)
const filterStatus = ref('')
const search = ref('')

const filtered = computed(() => list.value.filter(d =>
  (!filterStatus.value || d.status === filterStatus.value) &&
  (!search.value ||
    (d.student_name || '').includes(search.value) ||
    (d.username || '').includes(search.value))
))

const AREA_KO: Record<string, string> = { A5: '사실', A6: '추론', A7: '비판' }
const LABEL_KO: Record<string, string> = {
  excellent: '아주 잘함', observe: '잘함', caution: '보통', risk: '조금 부족', urgent: '도움 필요',
}
function labelKo(l: string) { return LABEL_KO[l] || l || '-' }
function levelKo(l: string) { return ({ low: '낮음', mid: '보통', high: '높음' } as any)[l] || '-' }
function areaKo(a: string) { return AREA_KO[a] || a }
function genreKo(g: string) { return g === 'narrative' ? '이야기글' : '설명글' }
function diffKo(d: string) { return ({ easy: '쉬움', normal: '보통', hard: '어려움' } as any)[d] || d }
function bettsKo(b: string) {
  return ({ independent: '독립', instructional: '교수', frustration: '좌절' } as any)[b] || b
}
function metaKo(m: string | null) {
  return ({ accurate: '정확', overestimate: '과대평가', underestimate: '과소평가' } as any)[m || ''] || '-'
}
function fmtDate(s: string | null) {
  if (!s) return '-'
  const d = new Date(s)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const weaknessCells = computed(() => {
  const wp = detail.value?.judgment?.weakness_profile_12
  if (!wp) return []
  return Object.entries(wp).map(([k, v]) => {
    const [area, genre] = k.split('_')
    return {
      key: k,
      label: `${genreKo(genre)} · ${areaKo(area)}`,
      acc: v as number | null,
    }
  })
})

async function load() {
  try { list.value = (await api.get('/api/admin/diagnoses')).data }
  catch { list.value = [] } finally { loading.value = false }
}

async function open(sessionId: number) {
  selected.value = sessionId
  detailLoading.value = true; detail.value = null
  try { detail.value = (await api.get(`/api/admin/diagnoses/${sessionId}`)).data }
  catch { detail.value = null } finally { detailLoading.value = false }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.diag-page { display: flex; flex-direction: column; gap: 1.2rem; }
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1rem 1.5rem;
}
.filters { display: flex; gap: 0.6rem; }
select, input[type=text] {
  background: #252836; border: 1px solid #2a2d3e; color: #ccc;
  padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;
  font-family: 'Nunito', sans-serif; outline: none;
}
select:focus, input:focus { border-color: #4ECDC4; }
input::placeholder { color: #555; }
.count { font-weight: 800; color: #4ECDC4; font-size: 0.9rem; }

.table-wrap { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 950px; }
.data-table th {
  text-align: left; padding: 0.9rem 1rem; font-size: 0.7rem; font-weight: 800;
  color: #555; text-transform: uppercase; border-bottom: 1px solid #2a2d3e; white-space: nowrap;
}
.data-table td { padding: 0.9rem 1rem; border-bottom: 1px solid #1e2130; color: #aaa; font-size: 0.86rem; white-space: nowrap; }
.row { cursor: pointer; }
.row:hover td { background: #1e2130; }
.strong { color: #fff; font-weight: 800; }
.dim { color: #555; }
.empty { padding: 2.5rem; text-align: center; color: #555; }

.chip { padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.74rem; font-weight: 800; }
.chip.ok { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.chip.wait { background: rgba(255,230,109,0.15); color: #FFE66D; }
.chip.small { font-size: 0.7rem; }
.chip.big { font-size: 0.9rem; padding: 0.35rem 0.9rem; }
.chip.lab.excellent, .chip.lab.observe { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.chip.lab.caution { background: rgba(255,230,109,0.15); color: #FFE66D; }
.chip.lab.risk, .chip.lab.urgent { background: rgba(255,107,107,0.15); color: #FF6B6B; }

/* 상세 */
.detail-wrap { display: flex; flex-direction: column; gap: 1rem; }
.back-btn {
  align-self: flex-start; background: #252836; border: 1px solid #2a2d3e; color: #aaa;
  padding: 0.5rem 1.1rem; border-radius: 8px; font-weight: 800; font-size: 0.85rem;
}
.back-btn:hover { border-color: #4ECDC4; color: #4ECDC4; }
.panel { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1.5rem; }
.head-panel { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.dt-title { font-size: 1.1rem; font-weight: 900; color: #fff; }
.dt-sub { font-size: 0.82rem; color: #666; margin-top: 0.3rem; }
.warn { color: #FFE66D; }
.head-judg { display: flex; align-items: center; gap: 0.7rem; font-size: 0.82rem; }
.p-title { font-size: 0.92rem; font-weight: 800; color: #fff; margin-bottom: 1rem; }

.kv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }
.kv { display: flex; flex-direction: column; gap: 0.2rem; }
.kv span { font-size: 0.75rem; color: #555; font-weight: 700; }
.kv b { font-size: 0.9rem; color: #ccc; font-weight: 800; }
.note { margin-top: 1rem; font-size: 0.74rem; color: #555; }

.cell-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.6rem; }
.wcell { border-radius: 8px; padding: 0.7rem; display: flex; flex-direction: column; gap: 0.2rem; }
.wcell.good { background: rgba(78,205,196,0.12); }
.wcell.mid  { background: rgba(255,230,109,0.12); }
.wcell.bad  { background: rgba(255,107,107,0.12); }
.wcell.na   { background: #252836; }
.wc-name { font-size: 0.72rem; color: #888; font-weight: 700; }
.wc-val { font-size: 1rem; font-weight: 900; color: #fff; }

.round-block { border-top: 1px solid #2a2d3e; padding-top: 1rem; margin-top: 1rem; }
.round-block:first-of-type { border-top: none; padding-top: 0; margin-top: 0; }
.round-head { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 0.8rem; font-size: 0.82rem; color: #888; }
.rh-no { font-weight: 900; color: #4ECDC4; }
.rh-text { font-weight: 800; color: #fff; }
.rh-metrics { margin-left: auto; display: flex; align-items: center; gap: 0.7rem; }
.resp-list { display: flex; flex-direction: column; gap: 0.4rem; }
.resp {
  display: flex; align-items: center; gap: 0.7rem; padding: 0.6rem 0.8rem;
  border-radius: 8px; background: #252836; font-size: 0.82rem; color: #aaa;
}
.resp.ok .r-mark { color: #4ECDC4; }
.resp.no { background: rgba(255,107,107,0.08); }
.resp.no .r-mark { color: #FF6B6B; }
.r-mark { font-weight: 900; }
.r-area { font-size: 0.7rem; font-weight: 800; color: #666; flex-shrink: 0; }
.r-q { flex: 1; color: #ccc; }
.r-ans { font-size: 0.76rem; color: #666; white-space: nowrap; }

.two-col { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.rec-list { margin-top: 0.8rem; display: flex; flex-direction: column; gap: 0.4rem; }
.rec { background: #252836; border-radius: 8px; padding: 0.6rem 0.9rem; font-size: 0.84rem; color: #ccc; }
.rep-label { font-size: 1rem; font-weight: 900; color: #4ECDC4; }
.rep-msg { font-size: 0.86rem; color: #aaa; margin-top: 0.4rem; line-height: 1.6; }
.tag-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.8rem; }

@media (max-width: 900px) {
  .kv-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
</style>
