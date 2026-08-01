<template>
  <div class="student-home">
    <NavBar @logout="handleLogout" />

    <main class="main">
      <div class="welcome-section">
        <div class="welcome-text">
          <h1>안녕하세요, <span class="name">{{ studentName }}</span>님! 👋</h1>
          <p>오늘도 책과 함께 즐거운 시간 보내봐요!</p>
        </div>
        <div class="welcome-illust">📚</div>
      </div>

      <div class="cards-grid">
        <div class="card card-diagnosis" @click="router.push('/student/diagnosis')">
          <div class="card-icon">🔍</div>
          <h2>읽기 진단</h2>
          <p>나의 읽기 능력을 확인해봐요</p>
          <div class="card-badge">시작하기 →</div>
        </div>

        <div class="card card-result" :class="{ 'card--disabled': !latest }" @click="goResult">
          <div class="card-icon">📊</div>
          <h2>내 결과</h2>
          <p>{{ latest ? '가장 최근 진단 결과를 확인해봐요' : '아직 진단 결과가 없어요' }}</p>
          <div class="card-badge" :class="latest ? 'card-badge--gray' : 'card-badge--muted'">
            {{ latest ? '결과 보기 →' : '진단 먼저 하기' }}
          </div>
        </div>

        <div class="card card-books" @click="router.push('/student/books')">
          <div class="card-icon">📖</div>
          <h2>추천 도서</h2>
          <p>나에게 딱 맞는 책을 찾아봐요</p>
          <div class="card-badge card-badge--yellow">책 보러 가기 →</div>
        </div>
      </div>

      <div v-if="resumeId" class="resume-banner">
        <span class="resume-icon">⏸️</span>
        <div class="resume-text">
          <strong>진행하던 진단이 있어요</strong>
          <span>이어서 하거나 새로 시작할 수 있어요.</span>
        </div>
        <button class="resume-btn" @click="router.push('/student/diagnosis')">이어서 하기</button>
      </div>

      <div class="status-section">
        <div class="status-head">
          <h2>내 학습 현황</h2>
          <button v-if="completedCount > 0" class="link-btn" @click="router.push('/student/history')">
            전체 이력 보기 →
          </button>
        </div>

        <div class="status-cards">
          <div class="status-card">
            <div class="status-icon">🏆</div>
            <div class="status-info">
              <span class="status-value">{{ loading ? '…' : completedCount }}</span>
              <span class="status-label">진단 횟수</span>
            </div>
          </div>
          <div class="status-card">
            <div class="status-icon">⭐</div>
            <div class="status-info">
              <span class="status-value">{{ loading ? '…' : levelText }}</span>
              <span class="status-label">읽기 수준</span>
            </div>
          </div>
          <div class="status-card">
            <div class="status-icon">📅</div>
            <div class="status-info">
              <span class="status-value">{{ loading ? '…' : lastDateText }}</span>
              <span class="status-label">마지막 진단</span>
            </div>
          </div>
        </div>

        <p v-if="error" class="status-hint status-hint--error">
          현황을 불러오지 못했어요.
          <button class="retry-link" :disabled="loading" @click="load">
            {{ loading ? '불러오는 중…' : '다시 시도' }}
          </button>
        </p>
        <p v-else-if="!loading && completedCount === 0" class="status-hint">
          진단을 완료하면 나의 읽기 수준을 알 수 있어요!
        </p>
        <p v-else-if="!loading" class="status-hint">
          진단 기준은 아직 다듬는 중이에요. 결과는 참고용으로 봐주세요.
        </p>
      </div>

      <!-- 내 정보 지우기 (STR-115).
           방침 §9 에 적은 '삭제 요구' 권리의 실행 경로다. 즉시 지우지 않고
           요청으로 받는다 — 아이의 오조작으로 되돌릴 수 없는 삭제가 일어나면
           안 되고, 아동의 권리는 법정대리인이 행사하는 것이 원칙이다. -->
      <section class="privacy-section">
        <h2>내 정보 지우기</h2>

        <p v-if="del.pending" class="privacy-status privacy-status--pending">
          삭제 요청이 접수되었어요. 확인 후 처리해 드릴게요.
          <button class="link-btn" :disabled="del.busy" @click="cancelDeletion">요청 취소</button>
        </p>
        <p v-else-if="del.lastResolved" class="privacy-status">
          지난 요청은 <strong>{{ DEL_STATUS_KO[del.lastResolved.status] }}</strong> 상태예요.
          <span v-if="del.lastResolved.resolution_note">— {{ del.lastResolved.resolution_note }}</span>
        </p>

        <template v-if="!del.pending">
          <p class="privacy-desc">
            그만두고 싶으면 내 진단 기록과 계정을 지워달라고 요청할 수 있어요.
            바로 지워지지는 않고, 확인한 뒤에 처리해요.
          </p>
          <div v-if="del.open" class="privacy-form">
            <label class="privacy-label">왜 지우고 싶어?</label>
            <div class="chips wrap">
              <button v-for="o in del.reasons" :key="o.code" class="chip"
                      :class="{ sel: del.reason === o.code }" @click="del.reason = o.code">
                {{ o.label }}
              </button>
            </div>
            <p class="privacy-notice">{{ del.backupNotice }}</p>
            <div class="privacy-actions">
              <button class="btn-ghost" @click="del.open = false">그만두기</button>
              <button class="btn-danger" :disabled="!del.reason || del.busy" @click="requestDeletion">
                {{ del.busy ? '보내는 중…' : '삭제 요청 보내기' }}
              </button>
            </div>
          </div>
          <button v-else class="btn-ghost" @click="openDeletion">내 정보 지우기 요청</button>
        </template>

        <p v-if="del.error" class="status-hint status-hint--error">{{ del.error }}</p>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { LABEL_5_KO, formatDateKo } from '@/utils/diagnosis'

const router = useRouter()
const auth = useAuthStore()

const studentName = computed(() => auth.user?.name || '학생')

// ── 삭제 요청 (STR-115) ───────────────────────────────────────────────────
const DEL_STATUS_KO: Record<string, string> = {
  pending: '처리 대기', completed: '처리 완료',
  rejected: '반려', cancelled: '취소함',
}

const del = reactive<{
  open: boolean; busy: boolean; error: string
  reason: string; reasons: { code: string; label: string }[]
  backupNotice: string
  pending: any | null; lastResolved: any | null
}>({
  open: false, busy: false, error: '',
  reason: '', reasons: [], backupNotice: '',
  pending: null, lastResolved: null,
})

async function loadDeletion() {
  try {
    const r = await api.get('/api/account/deletion-request')
    const items = r.data.items || []
    del.pending = items.find((i: any) => i.status === 'pending') ?? null
    del.lastResolved = items.find((i: any) => i.status !== 'pending') ?? null
    del.backupNotice = r.data.backup_notice || ''
  } catch {
    // 삭제 요청 상태를 못 불러와도 홈 화면 나머지는 그대로 쓸 수 있어야 한다.
    del.pending = null
  }
}

async function openDeletion() {
  del.error = ''
  if (!del.reasons.length) {
    try {
      const r = await api.get('/api/account/deletion-request/reasons')
      del.reasons = r.data.reasons
      del.backupNotice = r.data.backup_notice
    } catch {
      del.error = '잠시 후 다시 시도해줘.'
      return
    }
  }
  del.open = true
}

async function requestDeletion() {
  del.busy = true; del.error = ''
  try {
    await api.post('/api/account/deletion-request', { reason: del.reason })
    del.open = false; del.reason = ''
    await loadDeletion()
  } catch (e: any) {
    del.error = e?.response?.data?.detail || '요청을 보내지 못했어요.'
  } finally { del.busy = false }
}

async function cancelDeletion() {
  if (!del.pending) return
  del.busy = true; del.error = ''
  try {
    await api.post(`/api/account/deletion-request/${del.pending.id}/cancel`)
    await loadDeletion()
  } catch (e: any) {
    del.error = e?.response?.data?.detail || '취소하지 못했어요.'
  } finally { del.busy = false }
}

const loading = ref(true)
const error = ref(false)
const completedCount = ref(0)
const latest = ref<any | null>(null)
const resumeId = ref<number | null>(null)

// 판정 등급은 아동에게 그대로 보여주지 않고 친화 표현으로 바꾼다(§2 SCR-13).
const levelText = computed(() =>
  latest.value?.label_5 ? LABEL_5_KO[latest.value.label_5] ?? '-' : '-',
)
const lastDateText = computed(() =>
  latest.value ? formatDateKo(latest.value.completed_at || latest.value.started_at) : '-',
)

function goResult() {
  if (!latest.value) {
    router.push('/student/diagnosis')
    return
  }
  router.push({ path: '/student/result', query: { session: latest.value.session_id } })
}

async function load() {
  loading.value = true; error.value = false      // 재시도 시 이전 오류를 지운다
  try {
    const res = await api.get('/api/diagnosis/my/summary')
    completedCount.value = res.data.completed_count
    latest.value = res.data.latest
    resumeId.value = res.data.in_progress_session_id
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function handleLogout() {
  router.push('/login')
}

onMounted(() => { load(); loadDeletion() })
</script>

<style scoped>
.student-home { min-height: 100vh; background: var(--gray-light); }
.main { max-width: 1100px; margin: 0 auto; padding: 2rem; }

.welcome-section {
  background: linear-gradient(135deg, var(--mint) 0%, var(--mint-dark) 100%);
  border-radius: var(--radius);
  padding: 2.5rem;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
}
.welcome-text h1 { font-size: 1.8rem; font-weight: 900; margin-bottom: 0.5rem; }
.welcome-text .name { color: var(--yellow); }
.welcome-text p { font-size: 1rem; opacity: 0.9; }
.welcome-illust { font-size: 5rem; }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.2rem;
  margin-bottom: 2rem;
}
.card {
  background: var(--white);
  border-radius: var(--radius);
  padding: 2rem;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: var(--shadow);
}
.card:hover { transform: translateY(-4px); box-shadow: var(--shadow-hover); }
.card-icon { font-size: 2.5rem; margin-bottom: 1rem; }
.card h2 { font-size: 1.2rem; font-weight: 800; margin-bottom: 0.4rem; color: var(--navy); }
.card p { font-size: 0.9rem; color: var(--gray); margin-bottom: 1.2rem; }

.card-badge {
  display: inline-block;
  background: var(--mint);
  color: white;
  font-weight: 800;
  font-size: 0.85rem;
  padding: 0.4rem 1rem;
  border-radius: 99px;
}
.card-badge--gray { background: var(--gray-light); color: var(--gray); }
.card-badge--yellow { background: var(--yellow); color: var(--navy); }

.card--disabled { opacity: 0.8; }
.card-badge--muted { background: var(--gray-light); color: var(--gray); }

.resume-banner {
  display: flex; align-items: center; gap: 1rem;
  background: #FFF8E1; border: 2px solid var(--yellow);
  border-radius: var(--radius-sm); padding: 1rem 1.2rem; margin-bottom: 2rem;
}
.resume-icon { font-size: 1.6rem; }
.resume-text { display: flex; flex-direction: column; flex: 1; }
.resume-text strong { color: var(--navy); font-weight: 800; }
.resume-text span { font-size: 0.85rem; color: var(--gray); }
.resume-btn {
  background: var(--navy); color: white; border: none; border-radius: 99px;
  padding: 0.6rem 1.3rem; font-weight: 800; cursor: pointer; min-height: 44px;
}
.resume-btn:hover { opacity: 0.9; }

.status-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;
}
.link-btn {
  background: none; border: none; color: var(--mint-dark);
  font-weight: 800; font-size: 0.9rem; cursor: pointer; padding: 0.4rem;
}
.link-btn:hover { text-decoration: underline; }

.status-section h2 { font-size: 1.2rem; font-weight: 800; }
.status-hint--error { color: var(--coral); }
.retry-link {
  background: none; border: none; padding: 0; margin-left: 0.4rem;
  color: var(--coral); font-weight: 800; font-size: inherit;
  font-family: inherit; text-decoration: underline; cursor: pointer;
}
.retry-link:disabled { opacity: 0.5; cursor: default; text-decoration: none; }

@media (max-width: 720px) {
  .cards-grid, .status-cards { grid-template-columns: 1fr; }
  .resume-banner { flex-wrap: wrap; }
}
.status-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}
.status-card {
  background: var(--white);
  border-radius: var(--radius-sm);
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: var(--shadow);
}
.status-icon { font-size: 2rem; }
.status-info { display: flex; flex-direction: column; }
.status-value { font-size: 1.5rem; font-weight: 900; color: var(--navy); }
.status-label { font-size: 0.8rem; color: var(--gray); font-weight: 600; }
.status-hint { color: var(--gray); font-size: 0.9rem; text-align: center; padding: 0.5rem; }

/* 내 정보 지우기 (STR-115) — 눈에 띄되 유도하지는 않는다.
   되돌릴 수 없는 작업이라 다른 카드처럼 화려하게 두면 잘못 누른다. */
.privacy-section {
  margin-top: 2.5rem;
  padding: 1.5rem;
  border: 1px solid var(--gray-light);
  border-radius: 16px;
  background: #fff;
}
.privacy-section h2 {
  font-size: 1rem; font-weight: 800; color: var(--gray); margin-bottom: 0.8rem;
}
.privacy-desc { font-size: 0.9rem; color: var(--gray); margin-bottom: 1rem; line-height: 1.6; }
.privacy-label { display: block; font-size: 0.9rem; font-weight: 700; color: var(--navy); margin-bottom: 0.6rem; }
.privacy-form { margin-top: 0.5rem; }
.privacy-notice {
  margin: 1rem 0; padding: 0.8rem 1rem; border-radius: 10px;
  background: var(--gray-light); color: var(--gray);
  font-size: 0.85rem; line-height: 1.6;
}
.privacy-status {
  font-size: 0.9rem; color: var(--gray); margin-bottom: 1rem;
  display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
}
.privacy-status--pending { color: var(--navy); font-weight: 700; }
.privacy-actions { display: flex; gap: 0.6rem; justify-content: flex-end; }

.chips { display: flex; gap: 0.5rem; }
.chips.wrap { flex-wrap: wrap; }
.chip {
  border: 2px solid var(--gray-light); background: #fff; color: var(--gray);
  padding: 0.5rem 0.9rem; border-radius: 99px; font-size: 0.85rem;
  font-weight: 700; cursor: pointer; transition: all 0.15s;
}
.chip:hover { border-color: var(--mint); }
.chip.sel { border-color: var(--mint); background: var(--mint); color: #fff; }

.btn-ghost {
  border: 2px solid var(--gray-light); background: #fff; color: var(--gray);
  padding: 0.6rem 1.1rem; border-radius: 10px; font-size: 0.9rem;
  font-weight: 700; cursor: pointer; transition: all 0.15s;
}
.btn-ghost:hover { border-color: var(--gray); color: var(--navy); }
.btn-danger {
  border: none; background: var(--coral); color: #fff;
  padding: 0.6rem 1.1rem; border-radius: 10px; font-size: 0.9rem;
  font-weight: 800; cursor: pointer;
}
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
