<template>
  <div class="history">
    <NavBar @logout="handleLogout" />

    <main class="main">
      <div class="head">
        <button class="back-btn" @click="router.push('/student')">← 홈으로</button>
        <h1>내 진단 이력</h1>
      </div>

      <p v-if="loading" class="msg">불러오는 중이에요…</p>

      <p v-else-if="error" class="msg msg--error">
        이력을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.
      </p>

      <div v-else-if="items.length === 0" class="empty">
        <div class="empty-icon">📭</div>
        <h2>아직 진단 기록이 없어요</h2>
        <p>첫 진단을 해보면 여기에 기록이 쌓여요.</p>
        <button class="cta" @click="router.push('/student/diagnosis')">진단 시작하기</button>
      </div>

      <div v-else class="list">
        <button
          v-for="(it, i) in items"
          :key="it.session_id"
          class="row"
          :class="{ 'row--pending': !it.label_5 }"
          @click="open(it)"
        >
          <div class="row-date">
            <span class="row-date-main">{{ formatDateShort(it.completed_at || it.started_at) }}</span>
            <span class="row-date-sub">{{ i === 0 ? '가장 최근' : `${items.length - i}번째` }}</span>
          </div>

          <div class="row-body">
            <template v-if="it.label_5">
              <div class="row-title">
                <span class="row-emoji">{{ labelInfo(it.label_5).emoji }}</span>
                <span class="row-label">{{ labelInfo(it.label_5).ko }}</span>
                <span v-if="changeOf(i)" class="chip" :class="`chip--${changeOf(i)!.dir}`">
                  {{ changeOf(i)!.text }}
                </span>
              </div>
              <div class="row-meta">
                <span>글 이해 {{ LEVEL_3_KO[it.comprehension_level] ?? '-' }}</span>
                <span class="dot">·</span>
                <span>
                  읽기 속도
                  {{ it.fluency_valid ? (LEVEL_3_KO[it.fluency_level] ?? '-') : '측정 안 됨' }}
                </span>
                <span v-if="it.overall_accuracy != null" class="dot">·</span>
                <span v-if="it.overall_accuracy != null">
                  정답률 {{ Math.round(it.overall_accuracy * 100) }}%
                </span>
              </div>
              <p v-if="RELIABILITY_KO[it.reliability_flag]" class="row-note">
                {{ RELIABILITY_KO[it.reliability_flag] }}
              </p>
            </template>

            <template v-else>
              <div class="row-title">
                <span class="row-emoji">⏸️</span>
                <span class="row-label row-label--muted">
                  {{ SESSION_STATUS_KO[it.status] ?? it.status }}
                </span>
              </div>
              <div class="row-meta">결과가 나오기 전에 멈춘 진단이에요.</div>
            </template>
          </div>

          <div class="row-go">{{ it.label_5 ? '›' : '' }}</div>
        </button>
      </div>

      <p v-if="!loading && !error && items.length > 0" class="foot-note">
        진단 기준은 아직 다듬는 중이라 결과는 참고용이에요.
      </p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { api } from '@/api'
import {
  labelInfo, LEVEL_3_KO, SESSION_STATUS_KO, RELIABILITY_KO, formatDateShort,
} from '@/utils/diagnosis'

const router = useRouter()
const items = ref<any[]>([])
const loading = ref(true)
const error = ref(false)

/**
 * 직전 판정 대비 변화. 목록은 최신순이라 다음 인덱스가 이전 진단이다.
 * 등급 단계(lv) 비교만 한다 — 표본이 적어 통계적 해석은 하지 않는다(STR-15 확정 전).
 */
function changeOf(i: number) {
  const cur = items.value[i]
  const prev = items.value.slice(i + 1).find((x) => x.label_5)
  if (!cur?.label_5 || !prev) return null
  const d = labelInfo(cur.label_5).lv - labelInfo(prev.label_5).lv
  if (d > 0) return { dir: 'up', text: '올랐어요' }
  if (d < 0) return { dir: 'down', text: '내렸어요' }
  return { dir: 'same', text: '그대로' }
}

function open(it: any) {
  if (!it.label_5) return          // 판정 없는 세션은 볼 결과가 없다
  router.push({ path: '/student/result', query: { session: it.session_id } })
}

async function load() {
  try {
    const res = await api.get('/api/diagnosis/my/sessions')
    items.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.history { min-height: 100vh; background: var(--gray-light); }
.main { max-width: 760px; margin: 0 auto; padding: 2rem; }

.head { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
.head h1 { font-size: 1.5rem; font-weight: 900; color: var(--navy); }
.back-btn {
  background: var(--white); border: none; border-radius: 99px;
  padding: 0.5rem 1rem; font-weight: 700; color: var(--gray);
  cursor: pointer; box-shadow: var(--shadow);
}
.back-btn:hover { color: var(--navy); }

.msg { text-align: center; color: var(--gray); padding: 3rem 1rem; }
.msg--error { color: var(--coral); }

.empty {
  background: var(--white); border-radius: var(--radius);
  padding: 3rem 2rem; text-align: center; box-shadow: var(--shadow);
}
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }
.empty h2 { font-size: 1.2rem; font-weight: 800; color: var(--navy); margin-bottom: 0.4rem; }
.empty p { color: var(--gray); margin-bottom: 1.5rem; }
.cta {
  background: var(--mint); color: white; border: none; border-radius: 99px;
  padding: 0.8rem 2rem; font-weight: 800; font-size: 1rem; cursor: pointer;
}
.cta:hover { background: var(--mint-dark); }

.list { display: flex; flex-direction: column; gap: 0.8rem; }
.row {
  display: flex; align-items: center; gap: 1.2rem; width: 100%;
  background: var(--white); border: none; border-radius: var(--radius-sm);
  padding: 1.2rem 1.4rem; box-shadow: var(--shadow);
  cursor: pointer; text-align: left; transition: transform 0.15s, box-shadow 0.15s;
  min-height: 56px;                        /* 아동 터치 목표 크기 */
}
.row:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.row--pending { cursor: default; opacity: 0.75; }
.row--pending:hover { transform: none; box-shadow: var(--shadow); }

.row-date { display: flex; flex-direction: column; min-width: 74px; }
.row-date-main { font-weight: 800; color: var(--navy); }
.row-date-sub { font-size: 0.75rem; color: var(--gray); }

.row-body { flex: 1; min-width: 0; }
.row-title { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; flex-wrap: wrap; }
.row-emoji { font-size: 1.3rem; }
.row-label { font-weight: 800; color: var(--navy); }
.row-label--muted { color: var(--gray); font-weight: 700; }

.chip {
  font-size: 0.72rem; font-weight: 800; padding: 0.15rem 0.55rem; border-radius: 99px;
}
.chip--up { background: #E6F7F5; color: #0F9B8E; }
.chip--down { background: #FFECEC; color: #D9534F; }
.chip--same { background: var(--gray-light); color: var(--gray); }

.row-meta { font-size: 0.85rem; color: var(--gray); }
.row-meta .dot { margin: 0 0.35rem; }
.row-note { font-size: 0.78rem; color: var(--coral); margin-top: 0.3rem; }

.row-go { font-size: 1.5rem; color: var(--gray); font-weight: 800; }

.foot-note { text-align: center; color: var(--gray); font-size: 0.85rem; padding: 1.5rem 0 0; }

@media (max-width: 560px) {
  .main { padding: 1rem; }
  .row { gap: 0.8rem; padding: 1rem; }
  .row-date { min-width: 58px; }
}
</style>
