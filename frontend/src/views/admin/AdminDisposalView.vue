<template>
  <AdminLayout @logout="handleLogout">
    <template #title>개인정보 파기</template>

    <div class="disposal-page">
      <p class="page-note">
        개인정보 처리방침 §6 이 약속한 파기 절차다.
        <strong>되돌릴 수 없다</strong> — 학생을 파기하면 프로필·진단 기록·리포트·동의 기록이
        함께 사라진다. 백업본에는 최대 30일간 남는다.
      </p>

      <!-- 파기 실행 -->
      <section class="panel">
        <div class="panel-head">
          <h2>파기 실행</h2>
          <p class="sub">대상을 고르면 무엇이 지워지는지 먼저 보여준다.</p>
        </div>

        <div class="pick-row">
          <select v-model.number="picked" :disabled="loadingUsers">
            <option :value="null">— 대상 선택 —</option>
            <option v-for="u in students" :key="u.id" :value="u.id">
              {{ u.username }} ({{ u.grade || '학년 없음' }}{{ u.is_active ? '' : ' · 비활성' }})
            </option>
          </select>
          <button class="ghost-btn" :disabled="!picked || previewing" @click="loadPreview">
            {{ previewing ? '확인 중…' : '지워질 내용 보기' }}
          </button>
        </div>

        <p v-if="error" class="warn-line">{{ error }}</p>

        <!-- 미리보기 -->
        <div v-if="preview" class="preview">
          <div class="pv-head">
            <span class="mono strong">{{ preview.code }}</span>
            <span class="dim">{{ preview.grade || '학년 없음' }}</span>
          </div>

          <div class="count-grid">
            <div v-for="(v, k) in preview.counts" :key="k" class="count-cell"
                 :class="{ zero: !v }">
              <span class="c-k">{{ countKo(k) }}</span>
              <span class="c-v">{{ v }}</span>
            </div>
          </div>

          <p v-if="preview.consent" class="consent-line">
            동의 기록 있음 — {{ preview.consent.confirm_method === 'written' ? '서면' : preview.consent.confirm_method }},
            원본 보관 {{ preview.consent.document_location || '위치 미기재' }}.
            <strong>이 사실은 파기 기록에 스냅샷으로 보존된다.</strong>
          </p>
          <p v-else class="consent-line dim">동의 기록 없음.</p>

          <p class="danger-line">⚠ {{ preview.warning }}</p>

          <div class="form-row">
            <label>
              <span class="f-label">사유</span>
              <select v-model="reason">
                <option v-for="r in reasons" :key="r.code" :value="r.code">{{ r.label }}</option>
              </select>
            </label>
            <label class="grow">
              <span class="f-label">비고 (선택)</span>
              <input v-model="note" type="text" placeholder="예: 보호자 철회 요청 접수" />
            </label>
          </div>

          <div class="form-row">
            <label class="grow">
              <span class="f-label">
                확인 — 대상 아이디 <span class="mono strong">{{ preview.code }}</span> 를 그대로 입력
              </span>
              <input v-model="confirmCode" type="text" :placeholder="preview.code" />
            </label>
            <button class="danger-btn"
                    :disabled="confirmCode.trim() !== preview.code || disposing"
                    @click="execute">
              {{ disposing ? '파기 중…' : '파기 실행' }}
            </button>
          </div>
        </div>
      </section>

      <!-- 기록 -->
      <section class="panel">
        <div class="panel-head">
          <h2>파기 기록 <span class="count-chip">{{ logs.length }}</span></h2>
          <p class="sub">언제·누구를·왜 지웠는지. 증명이 필요할 때 이 목록이 근거다.</p>
        </div>

        <div v-if="!logs.length" class="empty-inline">파기 기록이 없다.</div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>일시</th><th>대상</th><th>학년</th><th>사유</th>
                <th>수행자</th><th>지운 내용</th><th>동의</th><th>비고</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in logs" :key="l.id">
                <td>{{ fmtDate(l.disposed_at) }}</td>
                <td class="mono">{{ l.subject_code }}</td>
                <td>{{ l.subject_grade || '—' }}</td>
                <td>{{ l.reason_label }}</td>
                <td class="mono dim">{{ l.disposed_by_code || '—' }}</td>
                <td class="dim">{{ summarize(l.deleted_counts) }}</td>
                <td>
                  <span v-if="l.consent_snapshot" class="ok-chip">보존</span>
                  <span v-else class="dim">—</span>
                </td>
                <td class="dim">{{ l.note || '—' }}</td>
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

const students = ref<any[]>([])
const loadingUsers = ref(true)
const picked = ref<number | null>(null)
const preview = ref<any>(null)
const previewing = ref(false)
const reasons = ref<any[]>([])
const reason = ref('retention_expired')
const note = ref('')
const confirmCode = ref('')
const disposing = ref(false)
const logs = ref<any[]>([])
const error = ref('')

const COUNT_KO: Record<string, string> = {
  student_profiles: '설문 프로필',
  diagnosis_sessions: '진단 세션',
  diagnosis_rounds: '회차',
  question_responses: '문항 응답',
  comprehension_results: '채점 결과',
  fluency_results: '읽기 측정',
  judgment_results: '판정',
  reports: '리포트',
  consent_records: '동의 기록',
}
function countKo(k: string | number) { return COUNT_KO[String(k)] || String(k) }

function summarize(c: Record<string, number>) {
  const parts = Object.entries(c || {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${countKo(k)} ${v}`)
  return parts.length ? parts.join(' · ') : '없음'
}

function fmtDate(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('ko-KR')
}

async function loadPreview() {
  if (!picked.value) return
  previewing.value = true; error.value = ''; preview.value = null; confirmCode.value = ''
  try {
    const r = await api.get(`/api/admin/disposals/preview/${picked.value}`)
    preview.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '대상 정보를 불러오지 못했습니다.'
  } finally { previewing.value = false }
}

async function execute() {
  if (!preview.value) return
  disposing.value = true; error.value = ''
  try {
    await api.post('/api/admin/disposals', {
      user_id: preview.value.user_id,
      reason: reason.value,
      confirm_code: confirmCode.value.trim(),
      note: note.value || null,
    })
    preview.value = null; picked.value = null; confirmCode.value = ''; note.value = ''
    await Promise.all([loadUsers(), loadLogs()])
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '파기에 실패했습니다.'
  } finally { disposing.value = false }
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const r = await api.get('/api/admin/users')
    // 관리자는 이 경로로 파기할 수 없다(서버에서도 차단). 목록에서 아예 뺀다.
    students.value = r.data.filter((u: any) => u.role !== 'admin')
  } finally { loadingUsers.value = false }
}

async function loadLogs() {
  const r = await api.get('/api/admin/disposals')
  logs.value = r.data
}

function handleLogout() { router.push('/login') }

onMounted(async () => {
  const [, , rs] = await Promise.all([
    loadUsers(), loadLogs(), api.get('/api/admin/disposals/reasons'),
  ])
  reasons.value = rs.data
})
</script>

<style scoped>
.disposal-page { display: flex; flex-direction: column; gap: 1.2rem; }
.page-note { color: #8b90a5; font-size: 0.9rem; line-height: 1.6; }
.page-note strong { color: #FF6B6B; }

.panel { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 1.4rem; }
.panel-head { margin-bottom: 1rem; }
.panel-head h2 { font-size: 1.05rem; font-weight: 800; color: #e8eaf2; }
.sub { font-size: 0.84rem; color: #8b90a5; margin-top: 0.25rem; }
.count-chip {
  background: #2a2d3e; color: #8b90a5; font-size: 0.75rem;
  padding: 0.1rem 0.5rem; border-radius: 99px; margin-left: 0.4rem;
}

.pick-row { display: flex; gap: 0.6rem; flex-wrap: wrap; }
select, input[type="text"] {
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 8px;
  color: #e8eaf2; padding: 0.55rem 0.8rem; font-size: 0.88rem; min-height: 40px;
}
select { min-width: 260px; }

.ghost-btn, .danger-btn {
  border-radius: 8px; padding: 0.55rem 1.1rem; font-weight: 800;
  font-size: 0.88rem; cursor: pointer; min-height: 40px;
}
.ghost-btn { background: transparent; border: 1px solid #2a2d3e; color: #e8eaf2; }
.ghost-btn:hover:not(:disabled) { border-color: #4ECDC4; color: #4ECDC4; }
.danger-btn { background: #FF6B6B; border: none; color: #0f1117; }
.danger-btn:hover:not(:disabled) { opacity: 0.9; }
.ghost-btn:disabled, .danger-btn:disabled { opacity: 0.4; cursor: default; }

.preview {
  margin-top: 1.2rem; padding: 1.1rem;
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 10px;
}
.pv-head { display: flex; gap: 0.7rem; align-items: baseline; margin-bottom: 0.9rem; }

.count-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.5rem; margin-bottom: 0.9rem;
}
.count-cell {
  display: flex; justify-content: space-between; align-items: center;
  background: #1a1d27; border-radius: 6px; padding: 0.5rem 0.7rem;
}
.count-cell.zero { opacity: 0.4; }
.c-k { font-size: 0.78rem; color: #8b90a5; }
.c-v { font-size: 0.95rem; font-weight: 800; color: #e8eaf2; }

.consent-line { font-size: 0.84rem; color: #8b90a5; margin-bottom: 0.6rem; line-height: 1.5; }
.consent-line strong { color: #4ECDC4; }
.danger-line {
  font-size: 0.86rem; font-weight: 700; color: #FF6B6B;
  background: rgba(255,107,107,0.1); border-radius: 6px;
  padding: 0.6rem 0.8rem; margin-bottom: 1rem;
}

.form-row { display: flex; gap: 0.8rem; align-items: flex-end; margin-bottom: 0.8rem; flex-wrap: wrap; }
.form-row label { display: flex; flex-direction: column; gap: 0.3rem; }
.form-row .grow { flex: 1; min-width: 220px; }
.form-row .grow input { width: 100%; }
.f-label { font-size: 0.78rem; color: #8b90a5; font-weight: 700; }

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.data-table th, .data-table td {
  padding: 0.6rem; text-align: left; border-bottom: 1px solid #2a2d3e; white-space: nowrap;
}
.data-table th { color: #8b90a5; font-weight: 700; font-size: 0.78rem; }
.data-table td { color: #d7dae8; }

.mono { font-family: ui-monospace, monospace; }
.strong { font-weight: 800; color: #e8eaf2; }
.dim { color: #6b7085; }
.ok-chip {
  background: rgba(78,205,196,0.15); color: #4ECDC4; font-size: 0.74rem;
  font-weight: 800; padding: 0.15rem 0.5rem; border-radius: 99px;
}
.warn-line { color: #FF6B6B; font-size: 0.86rem; margin-top: 0.7rem; }
.empty-inline { color: #6b7085; font-size: 0.85rem; padding: 0.6rem 0; }
</style>
