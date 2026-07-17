<template>
  <div class="result-page">
    <NavBar @logout="handleLogout" />
    <main class="main">
      <div class="page-header">
        <h1>📊 내 결과</h1>
        <p>나의 읽기 능력을 확인해봐요!</p>
      </div>

      <!-- 로딩 -->
      <div v-if="loading" class="empty-state">
        <div class="empty-illust">⏳</div>
        <h2>결과를 불러오는 중…</h2>
      </div>

      <!-- 결과 없음 -->
      <div v-else-if="!judgment" class="empty-state">
        <div class="empty-illust">🔍</div>
        <h2>아직 진단 결과가 없어요</h2>
        <p>{{ error || '진단을 완료하면 나의 읽기 수준을 알 수 있어요!' }}</p>
        <button class="btn-primary" @click="router.push('/student/diagnosis')">지금 진단하러 가기 🚀</button>
      </div>

      <!-- 결과 -->
      <div v-else class="result-content">
        <div class="level-card">
          <div class="level-badge">Lv. {{ levelInfo.lv }}</div>
          <h2>읽기 수준: <span class="highlight">{{ studentLabel }}</span></h2>
          <p>{{ report?.report_content?.layer1?.encouragement || levelInfo.msg }}</p>
          <span class="provisional">※ 판정 기준은 파일럿 전 잠정값이에요</span>
        </div>

        <div class="chart-grid">
          <div class="chart-card">
            <h3>👁️ 묵독 유창성</h3>
            <div class="bar-wrap"><div class="bar" :style="{ width: levelPct(judgment.fluency_level) + '%' }"></div></div>
            <span class="score">{{ levelKo(judgment.fluency_level) }}</span>
            <p v-if="judgment.fluency_value" class="sub">{{ judgment.fluency_value }} {{ unitKo(judgment.fluency_value_unit) }}</p>
          </div>
          <div class="chart-card">
            <h3>🧠 독해 이해</h3>
            <div class="bar-wrap"><div class="bar bar--yellow" :style="{ width: levelPct(judgment.comprehension_level) + '%' }"></div></div>
            <span class="score">{{ levelKo(judgment.comprehension_level) }}</span>
            <p v-if="judgment.overall_accuracy != null" class="sub">정답률 {{ Math.round(judgment.overall_accuracy * 100) }}%</p>
          </div>
          <div class="chart-card">
            <h3>🎯 종합</h3>
            <div class="bar-wrap"><div class="bar bar--coral" :style="{ width: levelInfo.lv * 20 + '%' }"></div></div>
            <span class="score">{{ studentLabel }}</span>
            <p class="sub">처방군 {{ judgment.prescription_group }}</p>
          </div>
        </div>

        <!-- 강점 -->
        <div v-if="strengths.length" class="info-card">
          <h3>💪 이런 걸 잘해요</h3>
          <div class="tag-row"><span v-for="(s, i) in strengths" :key="i" class="tag tag--good">{{ s }}</span></div>
        </div>

        <!-- 약점 훈련 -->
        <div v-if="weaknessCells.length" class="info-card">
          <h3>📈 이런 걸 연습하면 좋아요</h3>
          <div class="tag-row"><span v-for="(w, i) in weaknessCells" :key="i" class="tag tag--warn">{{ cellKo(w) }}</span></div>
        </div>

        <!-- 메타인지 -->
        <div v-if="judgment.metacognition" class="info-card">
          <h3>🪞 나를 얼마나 알까?</h3>
          <p class="meta-line">{{ metacogKo(judgment.metacognition) }}</p>
        </div>

        <!-- 추천 도서/텍스트 -->
        <div class="prescription-card">
          <h3>📚 너에게 맞는 다음 읽을거리</h3>
          <ul v-if="recommended.length" class="rec-list">
            <li v-for="(t, i) in recommended" :key="i">📖 {{ recTitle(t) }}</li>
          </ul>
          <p v-else class="sub">추천 텍스트를 준비하고 있어요.</p>
        </div>

        <button class="btn-back" @click="router.push('/student')">← 홈으로</button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { api } from '@/api'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const error = ref('')
const judgment = ref<any>(null)
const prescription = ref<any>(null)
const report = ref<any>(null)

const LABELS: Record<string, { lv: number; ko: string; msg: string }> = {
  excellent: { lv: 5, ko: '아주 잘함', msg: '정말 훌륭해요! 더 넓은 책의 세계로 나아가 볼까요?' },
  observe:   { lv: 4, ko: '잘함',     msg: '잘하고 있어요! 조금만 더 하면 최고 수준이에요.' },
  caution:   { lv: 3, ko: '보통',     msg: '또래와 비슷해요. 꾸준히 읽으면 쑥쑥 늘어요 💪' },
  risk:      { lv: 2, ko: '조금 부족', msg: '이 부분을 함께 연습해봐요. 할 수 있어요!' },
  urgent:    { lv: 1, ko: '도움 필요', msg: '천천히 하나씩 같이 해봐요. 괜찮아요!' },
}

const levelInfo = computed(() => LABELS[judgment.value?.label_5] || { lv: 3, ko: '보통', msg: '' })
const studentLabel = computed(() => report.value?.report_content?.layer1?.label || levelInfo.value.ko)
const strengths = computed<string[]>(() => report.value?.report_content?.layer1?.strengths || [])
const weaknessCells = computed<string[]>(() => report.value?.report_content?.layer2?.weakness_training || [])
const recommended = computed<any[]>(() =>
  prescription.value?.recommended_texts || report.value?.report_content?.layer1?.recommended_preview || [])

function levelKo(l: string) { return ({ low: '낮음', mid: '보통', high: '높음' } as any)[l] || l }
function levelPct(l: string) { return ({ low: 33, mid: 66, high: 100 } as any)[l] || 50 }
function unitKo(u: string) { return u === 'SPS' ? '음절/초' : u === 'CWPM' ? '어절/분' : '' }
function metacogKo(m: string) {
  return ({ accurate: '내 실력을 정확하게 알고 있어요! 👍',
            overestimate: '실제보다 조금 높게 봤어요. 겸손하게 한 번 더 확인해봐요.',
            underestimate: '생각보다 훨씬 잘했어요! 자신감을 가져도 좋아요 ✨' } as any)[m] || m
}
function cellKo(cell: any) {
  const area = typeof cell === 'string' ? cell.split('_')[0] : cell?.area
  const genre = typeof cell === 'string' ? cell.split('_')[1] : cell?.genre
  const a = ({ A5: '사실 찾기', A6: '추론하기', A7: '비판적으로 읽기' } as any)[area] || area
  const g = ({ narrative: '이야기글', expository: '설명글' } as any)[genre] || genre
  return genre ? `${g} · ${a}` : a
}
function recTitle(t: any) {
  if (typeof t === 'string') return t
  return t?.title || t?.text_code || t?.id || '추천 글'
}

async function load() {
  const sid = route.query.session
  if (!sid) { loading.value = false; return }
  try {
    const j = await api.get(`/api/diagnosis/session/${sid}/judgment`)
    judgment.value = j.data.judgment
    prescription.value = j.data.prescription
    try {
      const r = await api.get(`/api/diagnosis/session/${sid}/report`)
      report.value = r.data
    } catch { /* 리포트 없으면 판정만 표시 */ }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '결과를 불러오지 못했어요.'
  } finally { loading.value = false }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.result-page { min-height: 100vh; background: var(--gray-light); }
.main { max-width: 900px; margin: 0 auto; padding: 2rem; }
.page-header { margin-bottom: 2rem; }
.page-header h1 { font-size: 1.8rem; font-weight: 900; }
.page-header p { color: var(--gray); margin-top: 0.3rem; }

.empty-state {
  background: var(--white); border-radius: var(--radius); padding: 4rem 2rem;
  text-align: center; box-shadow: var(--shadow);
  display: flex; flex-direction: column; align-items: center; gap: 1rem;
}
.empty-illust { font-size: 5rem; }
.empty-state h2 { font-size: 1.4rem; font-weight: 900; }
.empty-state p { color: var(--gray); }

.result-content { display: flex; flex-direction: column; gap: 1.5rem; }

.level-card {
  background: linear-gradient(135deg, var(--mint) 0%, var(--mint-dark) 100%);
  border-radius: var(--radius); padding: 2.5rem; color: white;
  display: flex; flex-direction: column; gap: 0.7rem;
}
.level-badge { background: rgba(255,255,255,0.2); display: inline-block; padding: 0.4rem 1rem; border-radius: 99px; font-weight: 900; font-size: 0.9rem; width: fit-content; }
.level-card h2 { font-size: 1.5rem; font-weight: 900; }
.highlight { color: var(--yellow); }
.level-card p { opacity: 0.95; line-height: 1.6; }
.provisional { font-size: 0.78rem; opacity: 0.8; margin-top: 0.3rem; }

.chart-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
.chart-card { background: var(--white); border-radius: var(--radius); padding: 1.5rem; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 0.7rem; }
.chart-card h3 { font-size: 1rem; font-weight: 800; }
.bar-wrap { background: var(--gray-light); border-radius: 99px; height: 12px; overflow: hidden; }
.bar { background: var(--mint); height: 100%; border-radius: 99px; transition: width 1s ease; }
.bar--yellow { background: var(--yellow-dark); }
.bar--coral { background: var(--coral); }
.score { font-size: 1.4rem; font-weight: 900; color: var(--navy); }
.sub { font-size: 0.85rem; color: var(--gray); font-weight: 700; }

.info-card { background: var(--white); border-radius: var(--radius); padding: 1.5rem 2rem; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 0.9rem; }
.info-card h3 { font-size: 1.05rem; font-weight: 800; }
.tag-row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.tag { padding: 0.4rem 1rem; border-radius: 99px; font-weight: 800; font-size: 0.9rem; }
.tag--good { background: var(--mint-light); color: var(--mint-dark); }
.tag--warn { background: #FFF3E0; color: #E67E22; }
.meta-line { color: var(--navy); font-weight: 700; }

.prescription-card { background: var(--white); border-radius: var(--radius); padding: 2rem; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 1rem; }
.prescription-card h3 { font-size: 1.1rem; font-weight: 800; }
.rec-list { list-style: none; display: flex; flex-direction: column; gap: 0.6rem; }
.rec-list li { background: var(--gray-light); border-radius: var(--radius-sm); padding: 0.8rem 1.2rem; font-weight: 700; color: var(--navy); }

.btn-primary { background: var(--mint); color: white; border: none; padding: 0.9rem 2.5rem; border-radius: 99px; font-size: 1rem; font-weight: 800; transition: all 0.2s; }
.btn-primary:hover { background: var(--mint-dark); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.btn-back { align-self: flex-start; background: var(--gray-light); color: var(--gray); border: none; padding: 0.8rem 1.8rem; border-radius: 99px; font-size: 0.95rem; font-weight: 800; }
.btn-back:hover { background: #e0e5ec; }
</style>
