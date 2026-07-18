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

        <div class="card card-books">
          <div class="card-icon">📖</div>
          <h2>추천 도서</h2>
          <p>나에게 딱 맞는 책을 찾아봐요</p>
          <div class="card-badge card-badge--yellow">준비 중 🔧</div>
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
          현황을 불러오지 못했어요. 잠시 뒤 새로고침해 주세요.
        </p>
        <p v-else-if="!loading && completedCount === 0" class="status-hint">
          진단을 완료하면 나의 읽기 수준을 알 수 있어요!
        </p>
        <p v-else-if="!loading" class="status-hint">
          진단 기준은 아직 다듬는 중이에요. 결과는 참고용으로 봐주세요.
        </p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { LABEL_5_KO, formatDateKo } from '@/utils/diagnosis'

const router = useRouter()
const auth = useAuthStore()

const studentName = computed(() => auth.user?.name || '학생')

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

onMounted(load)
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
</style>
