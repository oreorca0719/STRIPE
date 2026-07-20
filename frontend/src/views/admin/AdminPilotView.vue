<template>
  <AdminLayout @logout="handleLogout">
    <template #title>파일럿 분석</template>

    <div class="pilot-page">
      <p class="page-note">
        판정 경계값(P33/P67)과 A4 타당성 범위는 모두 <strong>잠정값</strong>이다.
        확정(STR-15)에 쓸 분포를 여기서 본다.
      </p>

      <div v-if="loading" class="empty-state"><span>⏳</span><span>불러오는 중…</span></div>

      <div v-else-if="error" class="empty-state">
        <span>😵</span><span>{{ error }}</span>
        <button class="ghost-btn" @click="loadAll">다시 시도</button>
      </div>

      <template v-else>
        <!-- 내보내기 -->
        <section class="panel">
          <div class="panel-head">
            <h2>CSV 내보내기</h2>
            <p class="sub">임계값 산출은 외부 도구에서 한다. 이 파일이 STR-15 의 입력물이다.</p>
          </div>
          <div class="export-row">
            <label class="check">
              <input type="checkbox" v-model="anonymize" />
              <span>
                아이디를 익명 라벨로 치환
                <span class="dim">— 식별코드는 시스템 밖 매핑표와 결합하면 개인을 특정한다</span>
              </span>
            </label>
            <div class="export-btns">
              <button class="primary-btn" :disabled="downloading" @click="download('session')">
                세션별 CSV
              </button>
              <button class="ghost-btn" :disabled="downloading" @click="download('round')">
                회차별 CSV
              </button>
            </div>
          </div>
        </section>

        <!-- A4 분포 -->
        <section class="panel">
          <div class="panel-head">
            <h2>묵독 자동성 A4 분포 <span class="unit">음절/초</span></h2>
            <p class="sub">
              타당성 범위 {{ dist.a4.range_min }}~{{ dist.a4.range_max }} 안의 값만 그린다.
              범위 밖 {{ dist.a4.out_of_range_count }}건은 아래 이상치 목록 참조.
            </p>
          </div>

          <div v-if="dist.a4.percentiles" class="pct-row">
            <div class="pct"><span class="pct-k">n</span><span class="pct-v">{{ dist.a4.percentiles.n }}</span></div>
            <div class="pct hl"><span class="pct-k">P33</span><span class="pct-v">{{ dist.a4.percentiles.p33 }}</span></div>
            <div class="pct"><span class="pct-k">중앙값</span><span class="pct-v">{{ dist.a4.percentiles.p50 }}</span></div>
            <div class="pct hl"><span class="pct-k">P67</span><span class="pct-v">{{ dist.a4.percentiles.p67 }}</span></div>
            <div class="pct"><span class="pct-k">최소~최대</span><span class="pct-v">{{ dist.a4.percentiles.min }}~{{ dist.a4.percentiles.max }}</span></div>
          </div>
          <p v-if="thinSample(dist.a4.percentiles)" class="warn-line">
            ⚠ 표본이 {{ dist.a4.percentiles.n }}건뿐이다. 백분위가 크게 흔들리므로 이 값으로 경계를 확정하지 말 것.
          </p>

          <div class="hist">
            <div v-for="(c, i) in dist.a4.bins" :key="i" class="bar-row">
              <span class="bar-label">{{ a4BinLabel(i) }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: barPct(c, maxA4) }"></div>
              </div>
              <span class="bar-count">{{ c || '' }}</span>
            </div>
          </div>
        </section>

        <!-- 정답률 분포 -->
        <section class="panel">
          <div class="panel-head">
            <h2>종합 정답률 분포</h2>
            <p class="sub">세션 단위. 독해 경계값 산출의 기본 단위다.</p>
          </div>

          <div v-if="dist.accuracy.percentiles" class="pct-row">
            <div class="pct"><span class="pct-k">n</span><span class="pct-v">{{ dist.accuracy.percentiles.n }}</span></div>
            <div class="pct hl"><span class="pct-k">P33</span><span class="pct-v">{{ pctText(dist.accuracy.percentiles.p33) }}</span></div>
            <div class="pct"><span class="pct-k">중앙값</span><span class="pct-v">{{ pctText(dist.accuracy.percentiles.p50) }}</span></div>
            <div class="pct hl"><span class="pct-k">P67</span><span class="pct-v">{{ pctText(dist.accuracy.percentiles.p67) }}</span></div>
          </div>
          <p v-if="thinSample(dist.accuracy.percentiles)" class="warn-line">
            ⚠ 표본이 {{ dist.accuracy.percentiles.n }}건뿐이다. 경계 확정에는 부족하다.
          </p>

          <div class="hist">
            <div v-for="(c, i) in dist.accuracy.bins" :key="i" class="bar-row">
              <span class="bar-label">{{ i * 10 }}~{{ (i + 1) * 10 }}%</span>
              <div class="bar-track">
                <div class="bar-fill acc" :style="{ width: barPct(c, maxAcc) }"></div>
              </div>
              <span class="bar-count">{{ c || '' }}</span>
            </div>
          </div>
        </section>

        <!-- 영역별 정답률 -->
        <section class="panel">
          <div class="panel-head">
            <h2>영역별 정답률</h2>
            <p class="sub">문항 응답 전수 집계. 사실→추론→비판 순으로 낮아지는 것이 정상이다.</p>
          </div>
          <div class="area-grid">
            <div v-for="(v, k) in dist.area_accuracy" :key="k" class="area-card">
              <span class="area-name">{{ areaKo(k) }}</span>
              <span class="area-acc">{{ v.accuracy != null ? Math.round(v.accuracy * 100) + '%' : '—' }}</span>
              <span class="area-sub">{{ v.correct }} / {{ v.total }}</span>
            </div>
          </div>
        </section>

        <!-- 이상치 -->
        <section class="panel">
          <div class="panel-head">
            <h2>측정 이상치 <span class="count-chip">{{ outliers.count }}</span></h2>
            <p class="sub">
              A4 게이트({{ outliers.range_min }}~{{ outliers.range_max }})에 걸린 응시.
              게이트 범위를 조정하려면 이 목록을 하나씩 봐야 한다. 여기는 식별코드를 그대로 보여준다.
            </p>
          </div>
          <div v-if="!outliers.items.length" class="empty-inline">걸린 응시가 없다.</div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>학생</th><th>세션</th><th>회차</th><th>지문</th>
                  <th class="num">읽기시간(초)</th><th class="num">음절</th><th class="num">A4</th><th>사유</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in outliers.items" :key="it.fluency_id">
                  <td class="mono">{{ it.student }}</td>
                  <td>{{ it.session_id }}</td>
                  <td>{{ it.round_number ?? '—' }}</td>
                  <td class="mono dim">{{ it.text_code ?? '—' }}</td>
                  <td class="num">{{ it.silent_reading_time?.toFixed(1) ?? '—' }}</td>
                  <td class="num">{{ it.total_syllables ?? '—' }}</td>
                  <td class="num strong">{{ it.a4 }}</td>
                  <td>
                    <span class="reason" :class="it.reason">
                      {{ it.reason === 'too_slow' ? '너무 느림 (미독 의심)' : '너무 빠름 (버튼만 누름 의심)' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 중도이탈 -->
        <section class="panel">
          <div class="panel-head">
            <h2>중도이탈</h2>
            <p class="sub">문항 수·소요시간 조정의 근거.</p>
          </div>
          <div class="stat-row">
            <div class="stat"><span class="stat-k">전체 세션</span><span class="stat-v">{{ dropoff.total_sessions }}</span></div>
            <div class="stat"><span class="stat-k">완료율</span>
              <span class="stat-v">{{ dropoff.completion_rate != null ? Math.round(dropoff.completion_rate * 100) + '%' : '—' }}</span>
            </div>
            <div v-for="(c, k) in dropoff.status_counts" :key="k" class="stat">
              <span class="stat-k">{{ statusKo(k) }}</span><span class="stat-v">{{ c }}</span>
            </div>
          </div>

          <div class="two-col">
            <div>
              <h3 class="h3">도달 회차별 미완료</h3>
              <div v-if="!Object.keys(dropoff.incomplete_by_rounds_reached).length" class="empty-inline">없음</div>
              <ul v-else class="plain-list">
                <li v-for="(c, k) in dropoff.incomplete_by_rounds_reached" :key="k">
                  {{ k }}회차까지 진행 후 이탈 — <strong>{{ c }}건</strong>
                </li>
              </ul>
            </div>
            <div>
              <h3 class="h3">마지막 회차에서 멈춘 지점</h3>
              <ul class="plain-list">
                <li>읽기 전 — <strong>{{ dropoff.incomplete_last_round_stage.before_reading }}건</strong></li>
                <li>읽었으나 문항 미응답 — <strong>{{ dropoff.incomplete_last_round_stage.after_reading_no_answer }}건</strong></li>
                <li>문항 풀다 중단 — <strong>{{ dropoff.incomplete_last_round_stage.partial_answers }}건</strong></li>
              </ul>
            </div>
          </div>
        </section>
      </template>
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
const downloading = ref(false)
const anonymize = ref(true)

const dist = ref<any>(null)
const outliers = ref<any>(null)
const dropoff = ref<any>(null)

// 표본이 적으면 백분위가 크게 흔들린다. 이 값으로 경계를 확정하지 않도록 경고한다.
const THIN_SAMPLE = 30
function thinSample(p: any) { return p && p.n < THIN_SAMPLE }

const maxA4 = computed(() => Math.max(1, ...(dist.value?.a4.bins || [1])))
const maxAcc = computed(() => Math.max(1, ...(dist.value?.accuracy.bins || [1])))

function barPct(c: number, max: number) { return `${Math.round((c / max) * 100)}%` }
function pctText(v: number) { return `${Math.round(v * 100)}%` }

function a4BinLabel(i: number) {
  const lo = dist.value.a4.range_min + i * dist.value.a4.bin_width
  return `${lo.toFixed(1)}~${(lo + dist.value.a4.bin_width).toFixed(1)}`
}

// v-for 의 키는 string | number 로 들어온다
function areaKo(k: string | number) {
  return ({ A5: '사실적 이해', A6: '추론적 이해', A7: '비판적 이해' } as any)[k] || k
}
function statusKo(k: string | number) {
  return ({ in_progress: '진행중', completed: '완료', early_stop: '조기종료',
            indeterminate: '판정불가', abandoned: '중단' } as any)[k] || k
}

async function loadAll() {
  loading.value = true; error.value = ''
  try {
    const [d, o, r] = await Promise.all([
      api.get('/api/admin/pilot/distributions'),
      api.get('/api/admin/pilot/outliers'),
      api.get('/api/admin/pilot/dropoff'),
    ])
    dist.value = d.data; outliers.value = o.data; dropoff.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '분석 데이터를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

// CSV 는 인증 헤더가 필요해 <a href> 로 못 받는다. blob 으로 받아 저장한다.
async function download(level: 'session' | 'round') {
  downloading.value = true
  try {
    const res = await api.get('/api/admin/pilot/export.csv', {
      params: { level, anonymize: anonymize.value },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `stripe_${level}_${anonymize.value ? 'anon' : 'ident'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'CSV 내보내기에 실패했습니다.')
  } finally {
    downloading.value = false
  }
}

onMounted(loadAll)
function handleLogout() { router.push('/login') }
</script>

<style scoped>
.pilot-page { display: flex; flex-direction: column; gap: 1.2rem; }
.page-note {
  background: rgba(255,193,94,0.1); border: 1px solid rgba(255,193,94,0.3);
  border-radius: 12px; padding: 0.8rem 1.2rem; color: #C99A4E; font-size: 0.85rem; line-height: 1.6;
}
.page-note strong { color: #FFC15E; font-weight: 900; }

.panel {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1.5rem;
}
.panel-head { margin-bottom: 1.2rem; }
.panel-head h2 {
  font-size: 1rem; font-weight: 900; color: #fff;
  display: flex; align-items: center; gap: 0.5rem;
}
.unit { font-size: 0.75rem; font-weight: 700; color: #555; }
.count-chip {
  background: rgba(255,107,107,0.15); color: #FF6B6B;
  font-size: 0.75rem; padding: 0.15rem 0.6rem; border-radius: 99px;
}
.sub { font-size: 0.8rem; color: #666; margin-top: 0.35rem; line-height: 1.6; }

.export-row { display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; flex-wrap: wrap; }
.export-btns { display: flex; gap: 0.6rem; flex-shrink: 0; }
.check { display: flex; align-items: flex-start; gap: 0.6rem; font-size: 0.85rem; color: #aaa; line-height: 1.6; cursor: pointer; }
.check input { margin-top: 0.2rem; accent-color: #4ECDC4; flex-shrink: 0; }
.dim { color: #555; }

.pct-row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.9rem; }
.pct {
  background: #252836; border-radius: 8px; padding: 0.5rem 0.9rem;
  display: flex; flex-direction: column; gap: 0.15rem; min-width: 84px;
}
.pct.hl { background: rgba(78,205,196,0.12); border: 1px solid rgba(78,205,196,0.3); }
.pct-k { font-size: 0.7rem; font-weight: 800; color: #666; text-transform: uppercase; }
.pct-v { font-size: 0.95rem; font-weight: 900; color: #fff; }
.pct.hl .pct-v { color: #4ECDC4; }

.warn-line {
  color: #FFC15E; font-size: 0.8rem; font-weight: 700;
  margin-bottom: 0.9rem; line-height: 1.6;
}

.hist { display: flex; flex-direction: column; gap: 0.25rem; }
.bar-row { display: grid; grid-template-columns: 84px 1fr 32px; align-items: center; gap: 0.7rem; }
.bar-label { font-size: 0.72rem; color: #666; font-family: 'SFMono-Regular', Consolas, monospace; text-align: right; }
.bar-track { background: #252836; border-radius: 4px; height: 16px; overflow: hidden; }
.bar-fill { background: #4ECDC4; height: 100%; border-radius: 4px; transition: width 0.3s; }
.bar-fill.acc { background: #7C8CF8; }
.bar-count { font-size: 0.75rem; color: #888; font-weight: 700; }

.area-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.8rem; }
.area-card {
  background: #252836; border-radius: 10px; padding: 1rem;
  display: flex; flex-direction: column; gap: 0.3rem;
}
.area-name { font-size: 0.8rem; font-weight: 800; color: #888; }
.area-acc { font-size: 1.5rem; font-weight: 900; color: #4ECDC4; }
.area-sub { font-size: 0.75rem; color: #555; }

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 720px; }
.data-table th {
  text-align: left; padding: 0.7rem 0.9rem; font-size: 0.72rem; font-weight: 800;
  color: #555; text-transform: uppercase; border-bottom: 1px solid #2a2d3e; white-space: nowrap;
}
.data-table td { padding: 0.7rem 0.9rem; font-size: 0.85rem; color: #aaa; border-bottom: 1px solid #1e2130; }
.data-table tr:last-child td { border-bottom: none; }
.num { text-align: right; }
.strong { color: #fff; font-weight: 800; }
.mono { font-family: 'SFMono-Regular', Consolas, monospace; color: #4ECDC4; }
.mono.dim { color: #666; }
.reason { font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 99px; white-space: nowrap; }
.reason.too_slow { background: rgba(124,140,248,0.15); color: #7C8CF8; }
.reason.too_fast { background: rgba(255,107,107,0.15); color: #FF6B6B; }

.stat-row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
.stat { background: #252836; border-radius: 8px; padding: 0.6rem 1rem; display: flex; flex-direction: column; gap: 0.2rem; }
.stat-k { font-size: 0.72rem; font-weight: 800; color: #666; }
.stat-v { font-size: 1.1rem; font-weight: 900; color: #fff; }

.two-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; }
.h3 { font-size: 0.82rem; font-weight: 800; color: #4ECDC4; margin-bottom: 0.6rem; }
.plain-list { display: flex; flex-direction: column; gap: 0.4rem; }
.plain-list li { font-size: 0.85rem; color: #aaa; list-style: none; }
.plain-list strong { color: #fff; font-weight: 800; }

.empty-state {
  display: flex; align-items: center; gap: 0.7rem; justify-content: center;
  padding: 3rem; color: #555; font-size: 0.9rem;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
}
.empty-inline { color: #555; font-size: 0.85rem; padding: 0.6rem 0; }

.primary-btn {
  background: #4ECDC4; border: none; color: #12141c; padding: 0.6rem 1.2rem;
  border-radius: 8px; font-size: 0.85rem; font-weight: 800; cursor: pointer;
  font-family: 'Nunito', sans-serif; white-space: nowrap;
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn {
  background: none; border: 1px solid #2a2d3e; color: #888; padding: 0.6rem 1.2rem;
  border-radius: 8px; font-size: 0.85rem; font-weight: 700; cursor: pointer;
  font-family: 'Nunito', sans-serif; white-space: nowrap;
}
.ghost-btn:hover:not(:disabled) { border-color: #4ECDC4; color: #4ECDC4; }
.ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
