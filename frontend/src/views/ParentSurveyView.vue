<template>
  <div class="parent-page">
    <header class="head">
      <div class="head-inner">
        <span class="logo">📚 STRIPE</span>
        <button class="logout" @click="handleLogout">로그아웃</button>
      </div>
    </header>

    <main class="main">
      <div class="intro">
        <div class="illust">👨‍👩‍👧</div>
        <h1>보호자 설문</h1>
        <p class="lead">
          자녀의 읽기 진단 결과에 가정에서의 독서 환경을 함께 반영하기 위한 설문입니다.
        </p>
        <div class="notice">
          <strong>모든 문항은 선택 사항입니다.</strong>
          응답하지 않으셔도 자녀의 진단과 결과는 그대로 제공되며,
          가정 독서 환경에 대한 안내만 제공되지 않습니다.
          일부 문항만 응답하셔도 됩니다.
        </div>
      </div>

      <p v-if="loadError" class="msg msg--error">
        설문을 불러오지 못했습니다.
        <button class="retry" @click="load">다시 시도</button>
      </p>

      <p v-else-if="noProfile" class="msg">
        자녀의 진단 기록이 아직 없습니다. 자녀가 검사를 마친 뒤에 응답해 주세요.
      </p>

      <template v-else-if="questions.length">
        <p v-if="submitted" class="msg msg--done">
          응답이 저장되었습니다. 참여해 주셔서 감사합니다.
          <button class="retry" @click="submitted = false">다시 수정하기</button>
        </p>

        <template v-else>
          <p v-if="previous" class="msg">
            이전에 응답하신 내용이 있어 함께 불러왔습니다. 고쳐서 다시 제출하실 수 있습니다.
          </p>

          <section class="card">
            <SurveyQuestion
              v-for="q in questions" :key="q.code"
              :q="q"
              :model-value="answers[q.storage_field]"
              @update:model-value="setAnswer(q, $event)"
            />
          </section>

          <p v-if="submitError" class="msg msg--error">{{ submitError }}</p>

          <div class="actions">
            <span class="progress">{{ answeredCount }} / {{ questions.length }} 문항 응답</span>
            <button class="btn-submit" :disabled="busy" @click="submit">
              {{ busy ? '저장 중…' : '제출하기' }}
            </button>
          </div>
        </template>
      </template>

      <p v-else class="msg">불러오는 중…</p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import SurveyQuestion from '@/components/SurveyQuestion.vue'

/**
 * 보호자 설문 (STR-119). §5-4 환경 조정의 유일한 입력이다.
 *
 * 문항은 서버 정의에서 온다. 전 문항 선택 사항이므로 필수 검증을 걸지 않는다 —
 * 보호자가 중간에 그만두어도 학생 진단은 정상 완료되어야 한다.
 */
const router = useRouter()
const auth = useAuthStore()

const questions = ref<any[]>([])
const answers = reactive<Record<string, any>>({})
const previous = ref(false)
const noProfile = ref(false)
const loadError = ref(false)
const submitError = ref('')
const submitted = ref(false)
const busy = ref(false)

const answeredCount = computed(() =>
  questions.value.filter(q => {
    const v = answers[q.storage_field]
    return v !== null && v !== undefined && v !== ''
  }).length)

async function load() {
  loadError.value = false
  noProfile.value = false
  try {
    const [defRes, latestRes] = await Promise.all([
      api.get('/api/parent/survey/definition'),
      api.get('/api/parent/survey/latest'),
    ])
    questions.value = defRes.data.questions
    for (const q of questions.value) {
      if (!(q.storage_field in answers)) answers[q.storage_field] = null
    }
    // 이전 응답이 있으면 채워 넣는다. 처음부터 다시 쓰게 하면 고치려는
    // 보호자가 오히려 응답을 빠뜨린다.
    const prev = latestRes.data
    if (prev) {
      previous.value = true
      for (const q of questions.value) {
        if (prev[q.storage_field] !== undefined) answers[q.storage_field] = prev[q.storage_field]
      }
    }
  } catch (e: any) {
    if (e?.response?.status === 404) noProfile.value = true
    else loadError.value = true
  }
}

function setAnswer(q: any, v: any) {
  answers[q.storage_field] = v
  submitError.value = ''
}

async function submit() {
  busy.value = true; submitError.value = ''
  try {
    const payload: Record<string, any> = {}
    for (const q of questions.value) payload[q.storage_field] = answers[q.storage_field]
    await api.post('/api/parent/survey', payload)
    submitted.value = true
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e: any) {
    submitError.value = e?.response?.data?.detail || '저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  } finally { busy.value = false }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<style scoped>
.parent-page { min-height: 100vh; background: var(--bg, #f7f9fb); font-family: 'Nunito', sans-serif; }

.head { background: #fff; border-bottom: 1px solid var(--gray-light); }
.head-inner {
  max-width: 720px; margin: 0 auto; padding: 1rem 1.2rem;
  display: flex; align-items: center; justify-content: space-between;
}
.logo { font-weight: 900; color: var(--navy); }
.logout {
  border: 1px solid var(--gray-light); background: #fff; color: var(--gray);
  padding: 0.4rem 0.9rem; border-radius: 8px; font-size: 0.85rem;
  font-weight: 700; cursor: pointer;
}

.main { max-width: 720px; margin: 0 auto; padding: 2rem 1.2rem 4rem; }

.intro { text-align: center; margin-bottom: 2rem; }
.illust { font-size: 3rem; }
.intro h1 { font-size: 1.5rem; font-weight: 900; color: var(--navy); margin: 0.6rem 0; }
.lead { color: var(--gray); font-size: 0.95rem; line-height: 1.6; }

/* 선택 사항이라는 점을 눈에 띄게 — 보호자가 답을 강제로 느끼면 안 된다 */
.notice {
  margin-top: 1.2rem; padding: 1rem 1.2rem; text-align: left;
  background: rgba(78, 205, 196, 0.1); border: 1px solid rgba(78, 205, 196, 0.3);
  border-radius: 12px; font-size: 0.88rem; color: var(--navy); line-height: 1.7;
}

.card {
  background: #fff; border: 1px solid var(--gray-light);
  border-radius: 16px; padding: 1.8rem 1.5rem;
}

.msg {
  margin: 1rem 0; padding: 0.9rem 1.1rem; border-radius: 10px;
  background: #fff; border: 1px solid var(--gray-light);
  color: var(--gray); font-size: 0.9rem; line-height: 1.6;
}
.msg--error { border-color: var(--coral); color: var(--coral); font-weight: 700; }
.msg--done { border-color: var(--mint); color: var(--navy); font-weight: 700; }
.retry {
  margin-left: 0.5rem; background: none; border: none; text-decoration: underline;
  color: inherit; font-weight: 800; cursor: pointer; font-size: 0.88rem;
}

.actions {
  margin-top: 1.4rem; display: flex; align-items: center;
  justify-content: space-between; gap: 1rem; flex-wrap: wrap;
}
.progress { font-size: 0.85rem; color: var(--gray); font-weight: 700; }
.btn-submit {
  border: none; background: var(--mint); color: #fff;
  padding: 0.85rem 2rem; border-radius: 12px;
  font-size: 1rem; font-weight: 800; cursor: pointer;
}
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
