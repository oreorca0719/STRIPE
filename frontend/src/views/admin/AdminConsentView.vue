<template>
  <AdminLayout @logout="handleLogout">
    <template #title>보호자 동의</template>

    <div class="consent-page">
      <p class="page-note">
        파일럿 동의는 <strong>서면</strong>으로 받는다. 종이로 받더라도 회수 여부를 여기에
        기록해야 나중에 증명할 수 있고, 미동의 학생의 응시를 막을 수 있다.
      </p>

      <div v-if="loading" class="empty-state"><span>⏳</span><span>불러오는 중…</span></div>

      <div v-else-if="error" class="empty-state">
        <span>😵</span><span>{{ error }}</span>
        <button class="ghost-btn" @click="load">다시 시도</button>
      </div>

      <template v-else>
        <!-- 요약 -->
        <div class="summary-row">
          <div class="sum"><span class="sum-k">전체 학생</span><span class="sum-v">{{ summary.total_students }}</span></div>
          <div class="sum ok"><span class="sum-k">회수 완료</span><span class="sum-v">{{ summary.collected }}</span></div>
          <div class="sum warn"><span class="sum-k">미회수</span><span class="sum-v">{{ summary.missing }}</span></div>
          <div class="sum bad"><span class="sum-k">철회</span><span class="sum-v">{{ summary.revoked }}</span></div>
          <div v-if="summary.refused" class="sum bad"><span class="sum-k">동의 거부</span><span class="sum-v">{{ summary.refused }}</span></div>
        </div>

        <!-- 강제 여부 -->
        <div class="enforce" :class="summary.enforcement_on ? 'on' : 'off'">
          <strong>{{ summary.enforcement_on ? '응시 차단 켜짐' : '응시 차단 꺼짐' }}</strong>
          <span v-if="summary.enforcement_on">
            동의가 확인되지 않은 학생은 설문·진단을 시작할 수 없다.
          </span>
          <span v-else>
            지금은 <b>기록만</b> 하고 응시는 막지 않는다. 파일럿 시작 시 서버의
            <code>REQUIRE_PILOT_CONSENT=true</code> 로 켤 것 — 미리 켜면 동의 기록이 없는
            검수용 계정까지 전부 막힌다.
          </span>
        </div>

        <!-- 목록 -->
        <div class="toolbar">
          <label class="check">
            <input type="checkbox" v-model="missingOnly" @change="load" />
            <span>응시 불가만 보기 <span class="dim">(미회수·철회·거부)</span></span>
          </label>
          <input v-model="search" class="search" placeholder="아이디 검색..." />
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>학생</th><th>학년</th><th>상태</th><th>확인 방법</th>
                <th>선택 동의</th><th>원본 보관 위치</th><th>동의 일시</th><th class="right">관리</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!filtered.length">
                <td colspan="8"><div class="empty-inline">해당하는 학생이 없다.</div></td>
              </tr>
              <tr v-for="r in filtered" :key="r.user_id">
                <td class="mono">{{ r.username }}</td>
                <td class="dim">{{ gradeKo(r.grade) }}</td>
                <td>
                  <span class="badge" :class="statusOf(r).cls">{{ statusOf(r).ko }}</span>
                </td>
                <td class="dim">{{ r.has_record ? methodKo(r.confirm_method) : '—' }}</td>
                <td class="dim">{{ r.has_record ? (r.consent_optional ? '동의' : '미동의') : '—' }}</td>
                <td class="dim">{{ r.document_location || '—' }}</td>
                <td class="dim small">{{ fmt(r.consented_at) }}</td>
                <td class="right nowrap">
                  <button class="row-btn" @click="openForm(r)">
                    {{ r.has_record ? '수정' : '회수 기록' }}
                  </button>
                  <button v-if="r.has_record && !r.revoked" class="row-btn danger"
                          @click="revoke(r)">철회</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <!-- 회수 기록 입력 -->
      <div v-if="form" class="modal-backdrop" @click.self="form = null">
        <div class="modal">
          <div class="modal-head">
            <div>
              <h2 class="m-title">보호자 동의 회수 기록</h2>
              <p class="m-sub">
                <span class="mono">{{ form.username }}</span> —
                종이 동의서를 회수한 뒤 여기에 기록한다.
              </p>
            </div>
            <button class="close-btn" @click="form = null">✕</button>
          </div>

          <div class="form">
            <label class="field">
              <span class="f-label">확인 방법</span>
              <select v-model="form.confirm_method">
                <option value="written">서면 (파일럿)</option>
                <option value="phone_verification">휴대전화 본인인증 (정식 오픈)</option>
              </select>
            </label>

            <label class="check">
              <input type="checkbox" v-model="form.consent_required" />
              <span><b>필수 동의</b> — 진단 서비스 제공
                <span class="dim">. 해제하면 응시가 차단된다(동의 거부로 기록)</span>
              </span>
            </label>

            <label class="check">
              <input type="checkbox" v-model="form.consent_optional" />
              <span><b>선택 동의</b> — 연구·도구 개선 목적
                <span class="dim">. 없어도 진단은 가능하다</span>
              </span>
            </label>

            <label class="field">
              <span class="f-label">동의서 원본 보관 위치</span>
              <input v-model.trim="form.document_location" placeholder="예: 5학년 3반 캐비닛 A" />
              <span class="hint">
                종이 원본은 학생 실명·보호자 서명을 담은 개인정보 문서다. 어디 있는지
                적어두지 않으면 파기 시점에 회수할 수 없다.
              </span>
            </label>

            <label class="field">
              <span class="f-label">비고 <span class="dim">(선택)</span></span>
              <input v-model.trim="form.note" placeholder="특이사항" />
            </label>

            <p v-if="formError" class="err">{{ formError }}</p>

            <div class="form-actions">
              <button class="ghost-btn" @click="form = null">취소</button>
              <button class="primary-btn" :disabled="saving" @click="save">
                {{ saving ? '저장 중…' : '저장' }}
              </button>
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
import { api } from '@/api'
import AdminLayout from '@/components/admin/AdminLayout.vue'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const formError = ref('')
const missingOnly = ref(false)
const search = ref('')

const summary = ref<any>({})
const items = ref<any[]>([])
const form = ref<any>(null)

const filtered = computed(() => {
  if (!search.value) return items.value
  const q = search.value.toLowerCase()
  return items.value.filter(r => r.username.toLowerCase().includes(q))
})

function gradeKo(g: string | null) {
  return g ? ({ elem4: '초4', elem5: '초5', elem6: '초6', mid1: '중1' } as any)[g] || g : '—'
}
function methodKo(m: string) {
  return m === 'written' ? '서면' : m === 'phone_verification' ? '휴대전화 인증' : m
}
function fmt(v: string | null) {
  return v ? new Date(v).toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

function statusOf(r: any) {
  if (!r.has_record) return { ko: '미회수', cls: 'warn' }
  if (r.revoked) return { ko: '철회', cls: 'bad' }
  if (!r.consent_required) return { ko: '동의 거부', cls: 'bad' }
  return { ko: '회수 완료', cls: 'ok' }
}

function openForm(r: any) {
  formError.value = ''
  form.value = {
    user_id: r.user_id,
    username: r.username,
    confirm_method: r.confirm_method || 'written',
    consent_required: r.has_record ? r.consent_required : true,
    consent_optional: r.has_record ? r.consent_optional : false,
    document_location: r.document_location || '',
    note: r.note || '',
  }
}

async function save() {
  saving.value = true; formError.value = ''
  try {
    await api.post('/api/admin/consents', {
      user_id: form.value.user_id,
      confirm_method: form.value.confirm_method,
      consent_required: form.value.consent_required,
      consent_optional: form.value.consent_optional,
      document_location: form.value.document_location || null,
      note: form.value.note || null,
    })
    form.value = null
    await load()
  } catch (e: any) {
    formError.value = e?.response?.data?.detail || '저장에 실패했습니다.'
  } finally {
    saving.value = false
  }
}

async function revoke(r: any) {
  const note = prompt(
    `${r.username} 의 보호자 동의를 철회 처리합니다.\n` +
    `철회하면 응시가 차단됩니다. 기록은 지워지지 않습니다.\n\n사유(선택):`
  )
  if (note === null) return
  try {
    await api.post(`/api/admin/consents/${r.user_id}/revoke`, { note: note || null })
    await load()
  } catch (e: any) {
    alert(e?.response?.data?.detail || '철회 처리에 실패했습니다.')
  }
}

async function load() {
  loading.value = true; error.value = ''
  try {
    const res = await api.get('/api/admin/consents', {
      params: { missing_only: missingOnly.value },
    })
    summary.value = res.data.summary
    items.value = res.data.items
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '동의 현황을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
function handleLogout() { router.push('/login') }
</script>

<style scoped>
.consent-page { display: flex; flex-direction: column; gap: 1.2rem; }
.page-note {
  background: rgba(255,193,94,0.1); border: 1px solid rgba(255,193,94,0.3);
  border-radius: 12px; padding: 0.8rem 1.2rem; color: #C99A4E; font-size: 0.85rem; line-height: 1.6;
}
.page-note strong { color: #FFC15E; font-weight: 900; }

.summary-row { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.sum {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px;
  padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.25rem; min-width: 100px;
}
.sum-k { font-size: 0.72rem; font-weight: 800; color: #666; }
.sum-v { font-size: 1.35rem; font-weight: 900; color: #fff; }
.sum.ok .sum-v { color: #4ECDC4; }
.sum.warn .sum-v { color: #FFC15E; }
.sum.bad .sum-v { color: #FF6B6B; }

.enforce {
  border-radius: 12px; padding: 0.8rem 1.2rem; font-size: 0.85rem; line-height: 1.7;
  display: flex; flex-direction: column; gap: 0.2rem;
}
.enforce.on { background: rgba(78,205,196,0.1); border: 1px solid rgba(78,205,196,0.3); color: #7FD9D2; }
.enforce.on strong { color: #4ECDC4; }
.enforce.off { background: #1a1d27; border: 1px solid #2a2d3e; color: #888; }
.enforce.off strong { color: #aaa; }
.enforce code {
  background: #252836; padding: 0.1rem 0.4rem; border-radius: 4px;
  font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.8rem; color: #4ECDC4;
}
.enforce b { color: #ddd; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 0.9rem 1.3rem;
}
.search {
  background: #252836; border: 1px solid #2a2d3e; color: #fff;
  padding: 0.55rem 1rem; border-radius: 8px; font-size: 0.88rem;
  width: 220px; outline: none; font-family: 'Nunito', sans-serif;
}
.search:focus { border-color: #4ECDC4; }
.search::placeholder { color: #555; }

.check { display: flex; align-items: flex-start; gap: 0.6rem; font-size: 0.85rem; color: #aaa; line-height: 1.6; cursor: pointer; }
.check input { margin-top: 0.22rem; accent-color: #4ECDC4; flex-shrink: 0; }
.check b { color: #ddd; font-weight: 800; }
.dim { color: #555; font-weight: 600; }

.table-wrap { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 860px; }
.data-table th {
  text-align: left; padding: 0.9rem 1.2rem; font-size: 0.72rem; font-weight: 800;
  color: #555; text-transform: uppercase; border-bottom: 1px solid #2a2d3e; white-space: nowrap;
}
.data-table td { padding: 0.8rem 1.2rem; font-size: 0.87rem; color: #aaa; border-bottom: 1px solid #1e2130; }
.data-table tr:last-child td { border-bottom: none; }
.right { text-align: right; }
.nowrap { white-space: nowrap; }
.small { font-size: 0.78rem; }
.mono { font-family: 'SFMono-Regular', Consolas, monospace; color: #4ECDC4; font-weight: 700; }

.badge { font-size: 0.75rem; font-weight: 800; padding: 0.25rem 0.7rem; border-radius: 99px; white-space: nowrap; }
.badge.ok { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.badge.warn { background: rgba(255,193,94,0.15); color: #FFC15E; }
.badge.bad { background: rgba(255,107,107,0.15); color: #FF6B6B; }

.row-btn {
  background: #252836; border: 1px solid #2a2d3e; color: #aaa;
  padding: 0.35rem 0.8rem; border-radius: 7px; margin-left: 0.4rem;
  font-size: 0.78rem; font-weight: 700; cursor: pointer; font-family: 'Nunito', sans-serif;
}
.row-btn:hover { border-color: #4ECDC4; color: #4ECDC4; }
.row-btn.danger:hover { border-color: #FF6B6B; color: #FF6B6B; }

.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; padding: 2rem; z-index: 50;
}
.modal {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  width: 100%; max-width: 480px; max-height: 85vh; overflow-y: auto; padding: 1.8rem;
}
.modal-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.4rem; }
.m-title { font-size: 1.1rem; font-weight: 900; color: #fff; }
.m-sub { font-size: 0.8rem; color: #666; margin-top: 0.35rem; line-height: 1.6; }
.close-btn {
  background: #252836; border: 1px solid #2a2d3e; color: #888;
  width: 32px; height: 32px; border-radius: 8px; font-weight: 900; flex-shrink: 0; cursor: pointer;
}
.close-btn:hover { border-color: #FF6B6B; color: #FF6B6B; }

.form { display: flex; flex-direction: column; gap: 1rem; }
.field { display: flex; flex-direction: column; gap: 0.4rem; }
.f-label { font-size: 0.78rem; font-weight: 800; color: #888; }
.field input, .field select {
  background: #252836; border: 1px solid #2a2d3e; color: #fff;
  padding: 0.6rem 0.9rem; border-radius: 8px; font-size: 0.9rem;
  outline: none; font-family: 'Nunito', sans-serif; width: 100%;
}
.field input:focus, .field select:focus { border-color: #4ECDC4; }
.field input::placeholder { color: #555; }
.hint { font-size: 0.75rem; color: #555; line-height: 1.6; }

.err {
  background: rgba(255,107,107,0.1); border: 1px solid rgba(255,107,107,0.3);
  color: #FF6B6B; border-radius: 8px; padding: 0.6rem 0.9rem; font-size: 0.82rem; font-weight: 700;
}
.form-actions { display: flex; justify-content: flex-end; gap: 0.6rem; margin-top: 0.4rem; }
.primary-btn {
  background: #4ECDC4; border: none; color: #12141c; padding: 0.6rem 1.4rem;
  border-radius: 8px; font-size: 0.87rem; font-weight: 800; cursor: pointer; font-family: 'Nunito', sans-serif;
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn {
  background: none; border: 1px solid #2a2d3e; color: #888; padding: 0.6rem 1.2rem;
  border-radius: 8px; font-size: 0.87rem; font-weight: 700; cursor: pointer; font-family: 'Nunito', sans-serif;
}
.ghost-btn:hover { border-color: #4ECDC4; color: #4ECDC4; }

.empty-state {
  display: flex; align-items: center; gap: 0.7rem; justify-content: center;
  padding: 3rem; color: #555; font-size: 0.9rem;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
}
.empty-inline { color: #555; font-size: 0.87rem; padding: 2rem; text-align: center; }
</style>
