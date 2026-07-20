<template>
  <AdminLayout @logout="handleLogout">
    <template #title>사용자 관리</template>

    <div class="users-page">
      <!-- 탭 + 검색 -->
      <div class="toolbar">
        <div class="tabs">
          <button
            v-for="tab in tabs" :key="tab.value"
            class="tab" :class="{ active: activeTab === tab.value }"
            @click="activeTab = tab.value; loadUsers()"
          >
            {{ tab.icon }} {{ tab.label }}
            <span class="tab-count">{{ counts[tab.value] ?? 0 }}</span>
          </button>
        </div>
        <div class="search-bar">
          <input v-model="search" placeholder="이름 또는 아이디 검색..." />
          <button class="ghost-btn sm" @click="openBulk">파일럿 일괄 발급</button>
          <button class="issue-btn" @click="openIssue">+ 계정 발급</button>
        </div>
      </div>

      <!-- 테이블 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>아이디</th>
              <th>이름</th>
              <th v-if="activeTab === 'student'">학년</th>
              <th>상태</th>
              <th class="th-actions">관리</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td :colspan="colCount">
                <div class="empty-state"><span>⏳</span><span>불러오는 중...</span></div>
              </td>
            </tr>
            <tr v-else-if="filteredUsers.length === 0">
              <td :colspan="colCount">
                <div class="empty-state"><span>👤</span><span>사용자가 없습니다</span></div>
              </td>
            </tr>
            <tr v-for="user in filteredUsers" :key="user.id" class="data-row">
              <td class="td-id">{{ user.id }}</td>
              <td class="td-username">{{ user.username }}</td>
              <td class="td-name">{{ user.name }}</td>
              <td v-if="activeTab === 'student'" class="td-grade">{{ gradeLabel(user.grade) }}</td>
              <td>
                <span class="status-badge" :class="user.is_active ? 'active' : 'inactive'">
                  {{ user.is_active ? '활성' : '비활성' }}
                </span>
                <span v-if="user.must_change_password" class="status-badge pending">변경대기</span>
              </td>
              <td class="td-actions">
                <button class="row-btn" :disabled="busyId === user.id"
                        @click="resetPassword(user)">비밀번호 초기화</button>
                <button class="row-btn" :class="{ danger: user.is_active }"
                        :disabled="busyId === user.id" @click="toggleActive(user)">
                  {{ user.is_active ? '비활성화' : '활성화' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 계정 발급 -->
      <div v-if="issueOpen" class="modal-backdrop" @click.self="closeIssue">
        <div class="modal">
          <div class="modal-head">
            <div>
              <h2 class="m-title">계정 발급</h2>
              <p class="m-sub">비밀번호는 서버가 임시값으로 만들어 발급 직후 한 번만 보여준다.</p>
            </div>
            <button class="close-btn" @click="closeIssue">✕</button>
          </div>

          <div class="form">
            <label class="field">
              <span class="f-label">역할</span>
              <select v-model="form.role">
                <option value="student">학생</option>
                <option value="parent">학부모</option>
                <option value="teacher">교사</option>
              </select>
            </label>

            <label class="field">
              <span class="f-label">아이디 <span class="dim">(4자 이상)</span></span>
              <input v-model.trim="form.username" placeholder="elem5-017" autocomplete="off" />
            </label>

            <label class="field">
              <span class="f-label">
                이름
                <span v-if="form.role === 'student'" class="dim">(파일럿은 실명 대신 식별코드)</span>
              </span>
              <input v-model.trim="form.name" placeholder="elem5-017" autocomplete="off" />
            </label>

            <label v-if="form.role === 'student'" class="field">
              <span class="f-label">학년</span>
              <select v-model="form.grade">
                <option value="elem4">초등 4학년</option>
                <option value="elem5">초등 5학년</option>
                <option value="elem6">초등 6학년</option>
                <option value="mid1">중등 1학년</option>
              </select>
            </label>

            <label class="check">
              <input type="checkbox" v-model="form.must_change_password" />
              <span>
                최초 로그인 시 아이디·비밀번호 변경 요구
                <span class="dim">— 파일럿 학생 계정은 해제 권장(변경 화면에서 이탈 방지)</span>
              </span>
            </label>

            <p v-if="issueError" class="err">{{ issueError }}</p>

            <div class="form-actions">
              <button class="ghost-btn" @click="closeIssue">취소</button>
              <button class="primary-btn" :disabled="issuing" @click="submitIssue">
                {{ issuing ? '발급 중…' : '발급' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 파일럿 일괄 발급 (STR-90) -->
      <div v-if="bulkOpen" class="modal-backdrop" @click.self="bulkOpen = false">
        <div class="modal">
          <div class="modal-head">
            <div>
              <h2 class="m-title">파일럿 학생 계정 일괄 발급</h2>
              <p class="m-sub">
                학생 1명당 계정 1개. 계정을 공유하면 응시 기록이 한 계정에 섞여
                개인별 분포를 낼 수 없다.
              </p>
            </div>
            <button class="close-btn" @click="bulkOpen = false">✕</button>
          </div>

          <div class="form">
            <label class="field">
              <span class="f-label">학년</span>
              <select v-model="bulk.grade">
                <option value="elem4">초등 4학년</option>
                <option value="elem5">초등 5학년</option>
                <option value="elem6">초등 6학년</option>
                <option value="mid1">중등 1학년</option>
              </select>
            </label>

            <div class="row2">
              <label class="field">
                <span class="f-label">시작 번호</span>
                <input v-model.number="bulk.start" type="number" min="1" max="999" />
              </label>
              <label class="field">
                <span class="f-label">발급 수 <span class="dim">(최대 200)</span></span>
                <input v-model.number="bulk.count" type="number" min="1" max="200" />
              </label>
            </div>

            <div class="preview-box">
              <span class="f-label">생성될 아이디</span>
              <p class="preview-ids">{{ bulkPreview }}</p>
            </div>

            <label class="check">
              <input type="checkbox" v-model="bulk.must_change_password" />
              <span>
                최초 로그인 시 변경 요구
                <span class="dim">— 파일럿은 해제 권장(아동이 변경 화면에서 이탈)</span>
              </span>
            </label>

            <p v-if="bulkError" class="err">{{ bulkError }}</p>

            <div class="form-actions">
              <button class="ghost-btn" @click="bulkOpen = false">취소</button>
              <button class="primary-btn" :disabled="bulkIssuing" @click="submitBulk">
                {{ bulkIssuing ? '발급 중…' : `${bulk.count || 0}개 발급` }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 일괄 발급 결과 — CSV 저장 -->
      <div v-if="bulkResult" class="modal-backdrop" @click.self="confirmCloseBulkResult">
        <div class="modal">
          <div class="modal-head">
            <div>
              <h2 class="m-title">{{ bulkResult.count }}개 계정이 발급되었습니다</h2>
              <p class="m-sub warn">
                임시 비밀번호는 지금만 확인할 수 있다. <strong>CSV로 먼저 저장할 것.</strong>
                화면을 닫으면 다시 볼 수 없다.
              </p>
            </div>
            <button class="close-btn" @click="confirmCloseBulkResult">✕</button>
          </div>

          <div class="bulk-table-wrap">
            <table class="bulk-table">
              <thead><tr><th>아이디</th><th>임시 비밀번호</th></tr></thead>
              <tbody>
                <tr v-for="c in bulkResult.credentials" :key="c.user.id">
                  <td>{{ c.user.username }}</td>
                  <td class="mono">{{ c.temp_password }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="m-sub">
            식별코드↔학생 매핑표는 이 시스템 밖에서 따로 보관할 것. 그 표가 유일한 식별 경로다.
          </p>

          <div class="form-actions">
            <button class="primary-btn" @click="downloadBulkCsv">
              {{ csvSaved ? 'CSV 저장됨 ✓' : 'CSV 저장' }}
            </button>
            <button class="ghost-btn" @click="confirmCloseBulkResult">닫기</button>
          </div>
        </div>
      </div>

      <!-- 임시 비밀번호 1회 표시 -->
      <div v-if="credential" class="modal-backdrop" @click.self="credential = null">
        <div class="modal narrow">
          <div class="modal-head">
            <div>
              <h2 class="m-title">{{ credential.title }}</h2>
              <p class="m-sub">이 화면을 닫으면 다시 확인할 수 없다. 지금 옮겨 적을 것.</p>
            </div>
            <button class="close-btn" @click="credential = null">✕</button>
          </div>

          <div class="cred-row"><span class="c-key">아이디</span><span class="c-val">{{ credential.username }}</span></div>
          <div class="cred-row"><span class="c-key">임시 비밀번호</span><span class="c-val mono">{{ credential.password }}</span></div>

          <div class="form-actions">
            <button class="ghost-btn" @click="copyCredential">{{ copied ? '복사됨' : '복사' }}</button>
            <button class="primary-btn" @click="credential = null">확인</button>
          </div>
        </div>
      </div>

      <!-- 페이지네이션 -->
      <div class="pagination">
        <span class="page-info">전체 {{ filteredUsers.length }}명</span>
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

const activeTab = ref('student')
const search = ref('')
const users = ref<any[]>([])
const counts = ref<Record<string, number>>({})
const loading = ref(false)

const tabs = [
  { value: 'student', label: '학생', icon: '👨‍🎓' },
  { value: 'parent', label: '학부모', icon: '👨‍👩‍👧' },
  { value: 'teacher', label: '교사', icon: '👩‍🏫' },
]

const gradeMap: Record<string, string> = {
  elem1: '초등 1학년', elem2: '초등 2학년', elem3: '초등 3학년',
  elem4: '초등 4학년', elem5: '초등 5학년', elem6: '초등 6학년',
  mid1: '중등 1학년',
}

function gradeLabel(grade: string | null) {
  return grade ? gradeMap[grade] ?? grade : '-'
}

const filteredUsers = computed(() => {
  if (!search.value) return users.value
  const q = search.value.toLowerCase()
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) || u.name.toLowerCase().includes(q)
  )
})

// ID·아이디·이름·상태·관리 + 학생 탭일 때 학년
const colCount = computed(() => (activeTab.value === 'student' ? 6 : 5))

// ── 계정 발급 ─────────────────────────────────────────────────────────
const issueOpen = ref(false)
const issuing = ref(false)
const issueError = ref('')
const busyId = ref<number | null>(null)

// 임시 비밀번호는 서버가 발급 응답으로 한 번만 내려준다. 저장하지 않고 화면에만 띄운다.
const credential = ref<{ title: string; username: string; password: string } | null>(null)
const copied = ref(false)

function emptyForm() {
  return { username: '', name: '', role: 'student', grade: 'elem5', must_change_password: true }
}
const form = ref(emptyForm())

function openIssue() {
  form.value = emptyForm()
  form.value.role = activeTab.value          // 보고 있던 탭의 역할로 기본값
  issueError.value = ''
  issueOpen.value = true
}

function closeIssue() {
  issueOpen.value = false
}

function apiError(e: any, fallback: string) {
  return e?.response?.data?.detail || fallback
}

async function submitIssue() {
  issueError.value = ''
  if (form.value.username.length < 4) {
    issueError.value = '아이디는 4자 이상이어야 합니다.'
    return
  }
  if (!form.value.name) {
    issueError.value = '이름을 입력하세요.'
    return
  }

  issuing.value = true
  try {
    const payload: Record<string, any> = {
      username: form.value.username,
      name: form.value.name,
      role: form.value.role,
      must_change_password: form.value.must_change_password,
    }
    if (form.value.role === 'student') payload.grade = form.value.grade

    const res = await api.post('/api/auth/admin/users', payload)
    issueOpen.value = false
    credential.value = {
      title: '계정이 발급되었습니다',
      username: res.data.user.username,
      password: res.data.temp_password,
    }
    copied.value = false
    activeTab.value = form.value.role
    await Promise.all([loadUsers(), loadCounts()])
  } catch (e: any) {
    issueError.value = apiError(e, '계정 발급에 실패했습니다.')
  } finally {
    issuing.value = false
  }
}

// ── 파일럿 일괄 발급 (STR-90) ─────────────────────────────────────────
const bulkOpen = ref(false)
const bulkIssuing = ref(false)
const bulkError = ref('')
const csvSaved = ref(false)
const bulkResult = ref<{ grade: string; count: number; credentials: any[] } | null>(null)

const bulk = ref({ grade: 'elem5', start: 1, count: 30, must_change_password: false })

const bulkPreview = computed(() => {
  const { grade, start, count } = bulk.value
  if (!count || count < 1 || !start || start < 1) return '—'
  const pad = (n: number) => `${grade}-${String(n).padStart(3, '0')}`
  const last = start + count - 1
  if (count === 1) return pad(start)
  if (count === 2) return `${pad(start)}, ${pad(last)}`
  return `${pad(start)}, ${pad(start + 1)} … ${pad(last)}`
})

function openBulk() {
  bulkError.value = ''
  bulkOpen.value = true
}

async function submitBulk() {
  bulkError.value = ''
  bulkIssuing.value = true
  try {
    const res = await api.post('/api/auth/admin/users/bulk', {
      grade: bulk.value.grade,
      start: bulk.value.start,
      count: bulk.value.count,
      must_change_password: bulk.value.must_change_password,
    })
    bulkOpen.value = false
    bulkResult.value = res.data
    csvSaved.value = false
    activeTab.value = 'student'
    await Promise.all([loadUsers(), loadCounts()])
  } catch (e: any) {
    bulkError.value = apiError(e, '일괄 발급에 실패했습니다.')
  } finally {
    bulkIssuing.value = false
  }
}

function downloadBulkCsv() {
  if (!bulkResult.value) return
  const rows = [
    ['username', 'name', 'grade', 'temp_password'],
    ...bulkResult.value.credentials.map((c: any) => [
      c.user.username, c.user.name, c.user.grade, c.temp_password,
    ]),
  ]
  // Excel이 UTF-8로 열도록 BOM을 붙인다
  const csv = '﻿' + rows.map(r => r.join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `pilot_${bulkResult.value.grade}_${bulkResult.value.count}.csv`
  a.click()
  URL.revokeObjectURL(url)
  csvSaved.value = true
}

function confirmCloseBulkResult() {
  if (!csvSaved.value) {
    const ok = confirm(
      'CSV를 아직 저장하지 않았습니다.\n' +
      '임시 비밀번호는 이 화면을 닫으면 다시 확인할 수 없습니다.\n\n그래도 닫을까요?'
    )
    if (!ok) return
  }
  bulkResult.value = null
}

// ── 행 액션 ───────────────────────────────────────────────────────────
async function resetPassword(user: any) {
  if (!confirm(`${user.username} 계정의 비밀번호를 초기화합니다.\n기존 비밀번호는 즉시 사용할 수 없습니다.`)) return
  busyId.value = user.id
  try {
    const res = await api.post(`/api/auth/admin/users/${user.id}/reset-password`)
    credential.value = {
      title: '비밀번호가 초기화되었습니다',
      username: res.data.user.username,
      password: res.data.temp_password,
    }
    copied.value = false
    await loadUsers()
  } catch (e: any) {
    alert(apiError(e, '비밀번호 초기화에 실패했습니다.'))
  } finally {
    busyId.value = null
  }
}

async function toggleActive(user: any) {
  const next = !user.is_active
  const msg = next
    ? `${user.username} 계정을 다시 활성화합니다.`
    : `${user.username} 계정을 비활성화합니다.\n로그인이 차단되며, 진단 기록은 그대로 보존됩니다.`
  if (!confirm(msg)) return

  busyId.value = user.id
  try {
    await api.patch(`/api/auth/admin/users/${user.id}/active`, { is_active: next })
    await loadUsers()
  } catch (e: any) {
    alert(apiError(e, '상태 변경에 실패했습니다.'))
  } finally {
    busyId.value = null
  }
}

async function copyCredential() {
  if (!credential.value) return
  const text = `아이디: ${credential.value.username}\n임시 비밀번호: ${credential.value.password}`
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
  } catch {
    copied.value = false
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.get(`/api/admin/users`, {
      params: { role: activeTab.value }
    })
    users.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadCounts() {
  try {
    const res = await api.get(`/api/admin/users/count`)
    counts.value = res.data
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadUsers()
  loadCounts()
})

function handleLogout() { router.push('/login') }
</script>

<style scoped>
.users-page { display: flex; flex-direction: column; gap: 1.2rem; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1rem 1.5rem;
}
.tabs { display: flex; gap: 0.4rem; }
.tab {
  background: none; border: 1px solid #2a2d3e; color: #666;
  padding: 0.5rem 1.2rem; border-radius: 8px;
  font-size: 0.85rem; font-weight: 700; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 0.5rem;
}
.tab.active { background: rgba(78,205,196,0.15); border-color: #4ECDC4; color: #4ECDC4; }
.tab:hover:not(.active) { border-color: #444; color: #aaa; }
.tab-count {
  background: rgba(255,255,255,0.1); border-radius: 99px;
  padding: 0.1rem 0.5rem; font-size: 0.75rem;
}

.search-bar { display: flex; align-items: center; gap: 0.7rem; }
.search-bar input {
  background: #252836; border: 1px solid #2a2d3e; color: #fff;
  padding: 0.6rem 1.2rem; border-radius: 8px; font-size: 0.9rem;
  width: 280px; outline: none; font-family: 'Nunito', sans-serif;
}
.search-bar input:focus { border-color: #4ECDC4; }
.search-bar input::placeholder { color: #555; }

.issue-btn {
  background: #4ECDC4; border: none; color: #12141c;
  padding: 0.6rem 1.1rem; border-radius: 8px;
  font-size: 0.85rem; font-weight: 800; cursor: pointer; white-space: nowrap;
  font-family: 'Nunito', sans-serif;
}
.issue-btn:hover { filter: brightness(1.08); }

.table-wrap {
  background: #1a1d27; border: 1px solid #2a2d3e;
  border-radius: 16px; overflow: hidden;
}
.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  text-align: left; padding: 1rem 1.5rem;
  font-size: 0.75rem; font-weight: 800; color: #555;
  text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid #2a2d3e;
}
.data-row td { padding: 0.9rem 1.5rem; border-bottom: 1px solid #1e2130; color: #aaa; font-size: 0.9rem; }
.data-row:hover td { background: #1e2130; }
.data-row:last-child td { border-bottom: none; }
.td-id { color: #555; font-size: 0.8rem; }
.td-username { color: #4ECDC4; font-weight: 700; }
.td-name { color: #fff; font-weight: 600; }
.td-grade { color: #888; font-size: 0.85rem; }

.status-badge {
  font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.7rem; border-radius: 99px;
}
.active { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.inactive { background: rgba(255,107,107,0.15); color: #FF6B6B; }
.pending { background: rgba(255,193,94,0.15); color: #FFC15E; margin-left: 0.4rem; }

.th-actions, .td-actions { text-align: right; white-space: nowrap; }
.row-btn {
  background: #252836; border: 1px solid #2a2d3e; color: #aaa;
  padding: 0.35rem 0.8rem; border-radius: 7px; margin-left: 0.4rem;
  font-size: 0.78rem; font-weight: 700; cursor: pointer;
  font-family: 'Nunito', sans-serif;
}
.row-btn:hover:not(:disabled) { border-color: #4ECDC4; color: #4ECDC4; }
.row-btn.danger:hover:not(:disabled) { border-color: #FF6B6B; color: #FF6B6B; }
.row-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 계정 발급 · 임시 비밀번호 모달 */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; padding: 2rem; z-index: 50;
}
.modal {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
  width: 100%; max-width: 480px; max-height: 85vh; overflow-y: auto; padding: 1.8rem;
}
.modal.narrow { max-width: 400px; }
.modal-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.5rem; }
.m-title { font-size: 1.15rem; font-weight: 900; color: #fff; }
.m-sub { font-size: 0.8rem; color: #666; margin-top: 0.35rem; line-height: 1.5; }
.close-btn {
  background: #252836; border: 1px solid #2a2d3e; color: #888;
  width: 32px; height: 32px; border-radius: 8px; font-weight: 900;
  flex-shrink: 0; cursor: pointer;
}
.close-btn:hover { border-color: #FF6B6B; color: #FF6B6B; }
.dim { color: #555; font-weight: 600; }

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

.check {
  display: flex; align-items: flex-start; gap: 0.6rem;
  font-size: 0.82rem; color: #aaa; line-height: 1.5; cursor: pointer;
}
.check input { margin-top: 0.15rem; accent-color: #4ECDC4; flex-shrink: 0; }

.err {
  background: rgba(255,107,107,0.1); border: 1px solid rgba(255,107,107,0.3);
  color: #FF6B6B; border-radius: 8px; padding: 0.6rem 0.9rem;
  font-size: 0.82rem; font-weight: 700;
}

.form-actions { display: flex; justify-content: flex-end; gap: 0.6rem; margin-top: 0.5rem; }
.primary-btn {
  background: #4ECDC4; border: none; color: #12141c;
  padding: 0.6rem 1.4rem; border-radius: 8px;
  font-size: 0.87rem; font-weight: 800; cursor: pointer; font-family: 'Nunito', sans-serif;
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn {
  background: none; border: 1px solid #2a2d3e; color: #888;
  padding: 0.6rem 1.2rem; border-radius: 8px;
  font-size: 0.87rem; font-weight: 700; cursor: pointer; font-family: 'Nunito', sans-serif;
}
.ghost-btn:hover { border-color: #444; color: #aaa; }

.ghost-btn.sm { padding: 0.55rem 0.9rem; font-size: 0.82rem; white-space: nowrap; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }

.preview-box {
  background: #252836; border-radius: 8px; padding: 0.8rem 1rem;
  display: flex; flex-direction: column; gap: 0.35rem;
}
.preview-ids {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 0.88rem; color: #4ECDC4; letter-spacing: 0.03em;
}

.m-sub.warn { color: #FFC15E; }
.m-sub.warn strong { color: #FFC15E; font-weight: 900; }

.bulk-table-wrap {
  max-height: 320px; overflow-y: auto;
  background: #252836; border-radius: 8px; margin-bottom: 1rem;
}
.bulk-table { width: 100%; border-collapse: collapse; }
.bulk-table th {
  position: sticky; top: 0; background: #252836;
  text-align: left; padding: 0.6rem 1rem;
  font-size: 0.72rem; font-weight: 800; color: #666;
  text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid #2a2d3e;
}
.bulk-table td {
  padding: 0.5rem 1rem; font-size: 0.85rem; color: #ddd;
  border-bottom: 1px solid #1e2130;
}
.bulk-table tr:last-child td { border-bottom: none; }

.cred-row {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: #252836; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.6rem;
}
.c-key { font-size: 0.78rem; font-weight: 800; color: #888; }
.c-val { font-size: 0.95rem; font-weight: 800; color: #fff; }
.mono { font-family: 'SFMono-Regular', Consolas, monospace; color: #4ECDC4; letter-spacing: 0.05em; }

.empty-state {
  display: flex; align-items: center; gap: 0.7rem; justify-content: center;
  padding: 3rem; color: #555; font-size: 0.9rem;
}

.pagination {
  display: flex; align-items: center; justify-content: center;
}
.page-info { color: #555; font-size: 0.85rem; font-weight: 700; }
</style>
