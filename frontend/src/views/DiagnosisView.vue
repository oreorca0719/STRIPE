<template>
  <div class="diagnosis-page">
    <NavBar @logout="handleLogout" />
    <main class="main">
      <div class="page-header">
        <h1>📝 읽기 진단</h1>
        <p>차근차근 따라오면 금방 끝나요! 할 수 있어요 💪</p>
      </div>

      <!-- 진행 단계 -->
      <div class="steps-bar">
        <div v-for="(s, i) in stepLabels" :key="i" class="step"
             :class="{ active: stepIndex === i, done: stepIndex > i }">
          <div class="step-dot">{{ stepIndex > i ? '✓' : i + 1 }}</div>
          <span class="step-label">{{ s }}</span>
        </div>
      </div>

      <div class="diagnosis-card">
        <!-- 오류 -->
        <div v-if="error" class="step-content">
          <div class="illust">😵</div>
          <h2>문제가 생겼어요</h2>
          <p class="err">{{ error }}</p>
          <button class="btn-primary" @click="resetAll">처음부터 다시</button>
        </div>

        <!-- 설문 -->
        <div v-else-if="phase === 'survey'" class="step-content survey">
          <div class="illust">🙋</div>
          <h2>먼저 몇 가지만 알려줘!</h2>

          <div class="q-block">
            <label class="q-label">몇 학년이야?</label>
            <div class="chips">
              <button v-for="g in [4,5,6]" :key="g" class="chip"
                      :class="{ sel: survey.grade === g }" @click="survey.grade = g">
                {{ g }}학년
              </button>
            </div>
          </div>

          <div class="q-block">
            <label class="q-label">책을 얼마나 자주 읽어?</label>
            <div class="chips">
              <button v-for="o in freqOpts" :key="o.v" class="chip"
                      :class="{ sel: survey.reading_freq === o.v }" @click="survey.reading_freq = o.v">
                {{ o.t }}
              </button>
            </div>
          </div>

          <div class="q-block">
            <label class="q-label">책 읽는 걸 얼마나 좋아해?</label>
            <div class="chips">
              <button v-for="o in attOpts" :key="o.v" class="chip"
                      :class="{ sel: survey.reading_attitude === o.v }" @click="survey.reading_attitude = o.v">
                {{ o.t }}
              </button>
            </div>
          </div>

          <div class="q-block">
            <label class="q-label">어떤 이야기를 좋아해? <span class="muted">(여러 개 골라도 돼)</span></label>
            <div class="chips wrap">
              <button v-for="t in topicOpts" :key="t.v" class="chip"
                      :class="{ sel: survey.interest_topics.includes(t.v) }" @click="toggleTopic(t.v)">
                {{ t.t }}
              </button>
            </div>
          </div>

          <div class="q-block">
            <label class="q-label">문제를 몇 개나 맞힐 것 같아? <span class="muted">(0~10개)</span></label>
            <div class="slider-row">
              <input type="range" min="0" max="10" v-model.number="survey.predicted_correct" />
              <span class="slider-val">{{ survey.predicted_correct }}개</span>
            </div>
          </div>

          <button class="btn-primary" :disabled="!surveyValid || busy" @click="submitSurvey">
            {{ busy ? '준비 중…' : '시작하기 🚀' }}
          </button>
        </div>

        <!-- 묵독 읽기 -->
        <div v-else-if="phase === 'reading'" class="step-content">
          <div class="illust">👁️</div>
          <h2>{{ round.title }}</h2>
          <p>속으로(소리 내지 말고) 읽고, 다 읽으면 버튼을 눌러줘!</p>
          <div class="round-badge">{{ roundNumber }}번째 글 · {{ genreKo(round.genre) }}</div>
          <div class="text-box">
            <p class="reading-text">{{ round.content }}</p>
          </div>
          <div class="timer-area">
            <div class="timer">⏱ {{ timerDisplay }}</div>
            <button v-if="!timerRunning" class="btn-primary" @click="startReading">읽기 시작</button>
            <button v-else class="btn-stop" @click="stopReading" :disabled="busy">
              {{ busy ? '저장 중…' : '다 읽었어요! ✋' }}
            </button>
          </div>
        </div>

        <!-- 독해 문항 -->
        <div v-else-if="phase === 'questions'" class="step-content questions">
          <div class="illust">🧠</div>
          <h2>이제 문제를 풀어볼까?</h2>
          <p>방금 읽은 글을 생각하며 답을 골라줘!</p>
          <div v-for="(q, qi) in round.questions" :key="q.id" class="question-card">
            <div class="q-top">
              <span class="q-num">문제 {{ qi + 1 }}</span>
              <span class="area-chip">{{ areaKo(q.target_area) }}</span>
            </div>
            <p class="question-text">{{ q.question_text }}</p>
            <div class="options-col">
              <label v-for="(c, ci) in q.choices" :key="ci" class="option"
                     :class="{ sel: answers[q.id] === ci + 1 }">
                <input type="radio" :name="'q' + q.id" :value="ci + 1" v-model.number="answers[q.id]" />
                <span class="opt-num">{{ ci + 1 }}</span><span>{{ c }}</span>
              </label>
            </div>
          </div>
          <button class="btn-primary" :disabled="!allAnswered || busy" @click="submitAnswers">
            {{ busy ? '채점 중…' : '제출하기 📨' }}
          </button>
          <p v-if="!allAnswered" class="muted">모든 문제에 답하면 제출할 수 있어요</p>
        </div>

        <!-- 처리 중 -->
        <div v-else-if="phase === 'processing'" class="step-content">
          <div class="illust illust-big">🎉</div>
          <h2>진단 완료!</h2>
          <p>결과를 분석하고 있어요…</p>
          <div class="done-badge">처리 중 ⏳</div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api'

const router = useRouter()
const auth = useAuthStore()
const studentId = computed(() => auth.user?.id)

const stepLabels = ['설문', '읽기', '문제', '완료']
const phase = ref<'survey' | 'reading' | 'questions' | 'processing'>('survey')
const stepIndex = computed(() => ({ survey: 0, reading: 1, questions: 2, processing: 3 }[phase.value]))

const busy = ref(false)
const error = ref('')

const freqOpts = [ { t: '거의 안 읽어', v: 1 }, { t: '가끔 읽어', v: 3 }, { t: '거의 매일', v: 5 } ]
const attOpts = [ { t: '별로…', v: 1 }, { t: '그저 그래', v: 3 }, { t: '정말 좋아!', v: 5 } ]
const topicOpts = [
  { t: '🐾 동물', v: 'ANIMAL' }, { t: '🤝 우정', v: 'FRIENDSHIP' }, { t: '🗺 모험', v: 'ADVENTURE' },
  { t: '👨‍👩‍👧 가족', v: 'FAMILY' }, { t: '🦄 판타지', v: 'FANTASY' }, { t: '🔬 과학', v: 'SCIENCE' },
  { t: '🌱 자연', v: 'NATURE' }, { t: '🚀 우주', v: 'SPACE' }, { t: '🏛 역사', v: 'HISTORY' }, { t: '🏠 일상', v: 'DAILY' },
]

const survey = reactive<{
  grade: number | null; reading_freq: number | null; reading_attitude: number | null;
  interest_topics: string[]; predicted_correct: number
}>({ grade: null, reading_freq: null, reading_attitude: null, interest_topics: [], predicted_correct: 5 })

const surveyValid = computed(() =>
  survey.grade !== null && survey.reading_freq !== null && survey.reading_attitude !== null)

function toggleTopic(v: string) {
  const i = survey.interest_topics.indexOf(v)
  if (i >= 0) survey.interest_topics.splice(i, 1)
  else survey.interest_topics.push(v)
}

// 진단 상태
const sessionId = ref<number | null>(null)
const roundNumber = ref(1)
const round = reactive<{ roundId: number | null; title: string; content: string; genre: string; questions: any[] }>(
  { roundId: null, title: '', content: '', genre: '', questions: [] })
const answers = reactive<Record<number, number>>({})
const silentSeconds = ref(0)

const allAnswered = computed(() => round.questions.length > 0 && round.questions.every(q => answers[q.id]))

// 타이머
const timerRunning = ref(false)
const timerSeconds = ref(0)
let timerInterval: ReturnType<typeof setInterval> | null = null
const timerDisplay = computed(() => {
  const m = String(Math.floor(timerSeconds.value / 60)).padStart(2, '0')
  const s = String(timerSeconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

function areaKo(a: string) { return ({ A5: '사실', A6: '추론', A7: '비판' } as any)[a] || a }
function genreKo(g: string) { return g === 'narrative' ? '이야기글' : '설명글' }

async function submitSurvey() {
  if (!studentId.value) { error.value = '로그인 정보가 없어요. 다시 로그인해줘.'; return }
  busy.value = true; error.value = ''
  try {
    const prof = await api.post(`/api/diagnosis/profile?student_id=${studentId.value}`, {
      grade: survey.grade, reading_freq: survey.reading_freq, reading_attitude: survey.reading_attitude,
      interest_topics: survey.interest_topics, predicted_correct: survey.predicted_correct,
    })
    const sess = await api.post(`/api/diagnosis/session?student_id=${studentId.value}`, {
      profile_id: prof.data.id, silent_mode: true,
    })
    sessionId.value = sess.data.id
    const r = await api.post(`/api/diagnosis/session/${sessionId.value}/start`)
    await loadRound(r.data.id)
  } catch (e: any) {
    error.value = errMsg(e)
  } finally { busy.value = false }
}

async function loadRound(roundId: number) {
  const r = await api.get(`/api/diagnosis/round/${roundId}/content`)
  round.roundId = r.data.round_id
  round.title = r.data.title
  round.content = r.data.content
  round.genre = r.data.genre
  round.questions = r.data.questions
  for (const k of Object.keys(answers)) delete answers[Number(k)]
  timerSeconds.value = 0; timerRunning.value = false; silentSeconds.value = 0
  phase.value = 'reading'
}

function startReading() {
  timerRunning.value = true; timerSeconds.value = 0
  timerInterval = setInterval(() => timerSeconds.value++, 1000)
}

async function stopReading() {
  if (timerInterval) clearInterval(timerInterval)
  timerRunning.value = false
  silentSeconds.value = Math.max(1, timerSeconds.value)
  busy.value = true; error.value = ''
  try {
    await api.post('/api/diagnosis/fluency/silent', {
      session_id: sessionId.value, silent_reading_time: silentSeconds.value, round_id: round.roundId,
    })
    phase.value = 'questions'
  } catch (e: any) { error.value = errMsg(e) } finally { busy.value = false }
}

async function submitAnswers() {
  busy.value = true; error.value = ''
  try {
    for (const q of round.questions) {
      await api.post('/api/diagnosis/comprehension', {
        round_id: round.roundId, question_id: q.id, student_answer: answers[q.id],
      })
    }
    const res = await api.post(`/api/diagnosis/round/${round.roundId}/complete`)
    const body = res.data
    if (body.decision.action === 'continue' && body.next_round) {
      roundNumber.value++
      await loadRound(body.next_round.id)
    } else {
      await finalize()
    }
  } catch (e: any) { error.value = errMsg(e) } finally { busy.value = false }
}

async function finalize() {
  phase.value = 'processing'
  await api.post(`/api/diagnosis/session/${sessionId.value}/finalize`)
  await api.post(`/api/diagnosis/session/${sessionId.value}/report`)
  router.push({ name: 'result', query: { session: String(sessionId.value) } })
}

function errMsg(e: any): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x: any) => x.msg).join(', ')
  return e?.message || '알 수 없는 오류가 발생했어요.'
}

function resetAll() {
  error.value = ''; phase.value = 'survey'; sessionId.value = null; roundNumber.value = 1
}
function handleLogout() { router.push('/login') }
</script>

<style scoped>
.diagnosis-page { min-height: 100vh; background: var(--gray-light); }
.main { max-width: 800px; margin: 0 auto; padding: 2rem; }
.page-header { margin-bottom: 2rem; }
.page-header h1 { font-size: 1.8rem; font-weight: 900; }
.page-header p { color: var(--gray); margin-top: 0.3rem; }

.steps-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--white); border-radius: var(--radius);
  padding: 1.2rem 2rem; margin-bottom: 1.5rem; box-shadow: var(--shadow);
}
.step { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex: 1; }
.step-dot {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--gray-light); color: var(--gray);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 0.9rem; transition: all 0.3s;
}
.step.active .step-dot { background: var(--mint); color: white; }
.step.done .step-dot { background: var(--mint-dark); color: white; }
.step-label { font-size: 0.75rem; font-weight: 700; color: var(--gray); }
.step.active .step-label { color: var(--mint-dark); }

.diagnosis-card {
  background: var(--white); border-radius: var(--radius);
  padding: 2.5rem; box-shadow: var(--shadow); min-height: 400px;
}
.step-content { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 1.2rem; }
.illust { font-size: 4rem; }
.illust-big { font-size: 5rem; }
h2 { font-size: 1.5rem; font-weight: 900; color: var(--navy); }
p { color: var(--gray); line-height: 1.6; }
.err { color: var(--coral); font-weight: 700; }
.muted { color: var(--gray); font-size: 0.85rem; font-weight: 600; }

/* 설문 */
.survey { align-items: stretch; text-align: left; }
.survey > .illust, .survey > h2 { align-self: center; }
.q-block { display: flex; flex-direction: column; gap: 0.6rem; width: 100%; }
.q-label { font-weight: 800; color: var(--navy); font-size: 1.02rem; }
.chips { display: flex; gap: 0.6rem; }
.chips.wrap { flex-wrap: wrap; }
.chip {
  background: var(--gray-light); border: 2px solid transparent; color: var(--navy);
  border-radius: 99px; padding: 0.6rem 1.2rem; font-weight: 800; font-size: 0.95rem; transition: all 0.15s;
}
.chip:hover { border-color: var(--mint); }
.chip.sel { background: var(--mint-light); border-color: var(--mint); color: var(--mint-dark); }
.slider-row { display: flex; align-items: center; gap: 1rem; }
.slider-row input[type=range] { flex: 1; accent-color: var(--mint); }
.slider-val { font-weight: 900; color: var(--mint-dark); min-width: 3rem; }

/* 읽기 */
.round-badge { background: var(--yellow); color: var(--navy); font-weight: 800; font-size: 0.85rem; padding: 0.4rem 1rem; border-radius: 99px; }
.text-box {
  background: var(--gray-light); border-radius: var(--radius-sm);
  padding: 1.8rem 2rem; width: 100%; border-left: 5px solid var(--mint); text-align: left;
}
.reading-text { font-size: 1.15rem; line-height: 2.0; color: var(--navy); white-space: pre-wrap; }
.timer-area { display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.timer { font-size: 2.5rem; font-weight: 900; color: var(--mint-dark); }

/* 문항 */
.questions { align-items: stretch; }
.questions > .illust, .questions > h2, .questions > p { align-self: center; }
.question-card { background: var(--gray-light); border-radius: var(--radius-sm); padding: 1.5rem; width: 100%; text-align: left; }
.q-top { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.6rem; }
.q-num { font-size: 0.85rem; font-weight: 800; color: var(--mint-dark); }
.area-chip { font-size: 0.72rem; font-weight: 800; color: var(--gray); background: var(--white); padding: 0.15rem 0.6rem; border-radius: 99px; }
.question-text { font-size: 1.08rem; font-weight: 800; color: var(--navy); margin-bottom: 1rem; line-height: 1.5; }
.options-col { display: flex; flex-direction: column; gap: 0.6rem; }
.option {
  display: flex; align-items: center; gap: 0.7rem; background: white;
  border-radius: var(--radius-sm); padding: 0.8rem 1rem; cursor: pointer;
  font-weight: 700; color: var(--navy); border: 2px solid #e8ecf0; transition: all 0.15s;
}
.option:hover { border-color: var(--mint); }
.option.sel { border-color: var(--mint); background: var(--mint-light); color: var(--mint-dark); }
.option input { display: none; }
.opt-num {
  width: 24px; height: 24px; flex-shrink: 0; border-radius: 50%;
  background: var(--white); border: 2px solid #dfe6ee; color: var(--gray);
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem;
}
.option.sel .opt-num { background: var(--mint); color: white; border-color: var(--mint); }

.done-badge { background: var(--mint-light); color: var(--mint-dark); font-weight: 800; padding: 0.8rem 2rem; border-radius: 99px; }

.btn-primary {
  background: var(--mint); color: white; border: none; padding: 0.9rem 2.5rem;
  border-radius: 99px; font-size: 1rem; font-weight: 800; transition: all 0.2s; align-self: center;
}
.btn-primary:hover:not(:disabled) { background: var(--mint-dark); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-stop { background: var(--coral); color: white; border: none; padding: 0.9rem 2.5rem; border-radius: 99px; font-size: 1rem; font-weight: 800; }
.btn-stop:disabled { opacity: 0.6; }
</style>
