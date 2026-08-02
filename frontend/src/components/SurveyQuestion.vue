<template>
  <div class="q-block">
    <label class="q-label">
      {{ q.text }}
      <span v-if="hint" class="muted">{{ hint }}</span>
    </label>
    <p v-if="q.guide_text" class="q-guide">{{ q.guide_text }}</p>

    <!-- 단일 선택 · 척도 -->
    <div v-if="isSingle" class="chips wrap">
      <button v-for="o in q.options" :key="String(o.value)" class="chip"
              :class="{ sel: modelValue === o.value }"
              @click="emit('update:modelValue', o.value)">
        {{ o.label }}
      </button>
    </div>

    <!-- 복수 선택 -->
    <div v-else-if="q.response_type === 'multi_select'" class="chips wrap">
      <button v-for="o in q.options" :key="String(o.value)" class="chip"
              :class="{ sel: selected.includes(o.value), dim: !selected.includes(o.value) && atMax }"
              @click="toggle(o.value)">
        {{ o.label }}
      </button>
    </div>

    <!-- 권수 입력 -->
    <div v-else-if="q.response_type === 'numeric_input'" class="num-row">
      <button class="num-btn" :disabled="numValue <= q.min" @click="step(-1)">−</button>
      <input class="num-input" type="number" :min="q.min" :max="q.max"
             :value="modelValue ?? ''" @input="onNumber" />
      <span class="num-unit">{{ q.unit }}</span>
      <button class="num-btn" :disabled="numValue >= q.max" @click="step(1)">+</button>
    </div>

    <!-- 학년별 독서량 (A-4) -->
    <div v-else-if="q.response_type === 'grade_history'" class="grade-grid">
      <div class="grade-head">
        <span></span>
        <span v-for="s in q.scale" :key="String(s.value)" class="grade-scale-label">{{ s.label }}</span>
      </div>
      <div v-for="(g, i) in q.grades" :key="g.grade" class="grade-row"
           :class="{ disabled: isDisabled(i) }">
        <span class="grade-name">{{ g.label }}</span>
        <button v-for="s in q.scale" :key="String(s.value)" class="grade-cell"
                :class="{ sel: !isDisabled(i) && graph[i] === s.value }"
                :disabled="isDisabled(i)"
                :aria-label="`${g.label} ${s.label}`"
                @click="setGrade(i, s.value)">
          <span class="dot"></span>
        </button>
      </div>
    </div>

    <p v-if="error" class="q-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 문항 하나를 정의(survey_questions.json)대로 그린다.
 *
 * 화면이 문항을 알지 못한다 — 문구·선지·제약이 전부 서버 정의에서 온다.
 * 문구가 잠정본이라 계속 바뀌는데, 여기에 박아두면 문구 한 줄에 프론트를
 * 다시 빌드해야 하고 서버 검증과 어긋날 여지가 생긴다.
 */
const props = defineProps<{
  q: any
  modelValue: any
  error?: string
  /** A-4 의 auto_disable_after 대상 값 (B-1 에서 고른 학년) */
  currentGrade?: number | null
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: any): void }>()

const isSingle = computed(() =>
  props.q.response_type === 'single_select' || props.q.response_type.startsWith('scale_'))

const hint = computed(() => {
  const { min_select: lo, max_select: hi } = props.q
  if (lo && hi) return lo === hi ? `(${hi}개)` : `(${lo}~${hi}개)`
  if (hi) return `(최대 ${hi}개)`
  return ''
})

// ── 복수 선택 ─────────────────────────────────────────────────────────────
const selected = computed<any[]>(() => props.modelValue ?? [])
const atMax = computed(() =>
  !!props.q.max_select && selected.value.length >= props.q.max_select)

function toggle(v: any) {
  const cur = [...selected.value]
  const i = cur.indexOf(v)
  if (i >= 0) cur.splice(i, 1)
  // 상한을 넘기면 조용히 무시하지 않고 아무 반응도 하지 않는다 —
  // 눌리지 않는 선지는 흐리게 표시해 이유를 보여준다.
  else if (!atMax.value) cur.push(v)
  else return
  emit('update:modelValue', cur)
}

// ── 숫자 입력 ─────────────────────────────────────────────────────────────
const numValue = computed(() => props.modelValue ?? 0)

function clamp(n: number) {
  return Math.min(props.q.max, Math.max(props.q.min, n))
}
function step(d: number) {
  emit('update:modelValue', clamp(numValue.value + d))
}
function onNumber(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  if (raw === '') { emit('update:modelValue', null); return }
  const n = Number(raw)
  emit('update:modelValue', Number.isFinite(n) ? clamp(Math.trunc(n)) : null)
}

// ── 학년별 독서량 (A-4) ───────────────────────────────────────────────────
// 항상 길이 7 배열을 유지한다. 잘라서 보내면 마지막 요소가 몇 학년의 응답인지
// 서버가 알 수 없다(4학년의 마지막과 중1의 마지막이 구분되지 않는다).
const graph = computed<(number | null)[]>(() =>
  props.modelValue ?? new Array(props.q.grades?.length ?? 7).fill(null))

function isDisabled(i: number) {
  // 아직 오지 않은 학년은 묻지 않는다. B-1 을 고르기 전에는 전부 잠근다.
  if (!props.q.auto_disable_after) return false
  if (props.currentGrade == null) return true
  return props.q.grades[i].grade > props.currentGrade
}

function setGrade(i: number, v: number | null) {
  if (isDisabled(i)) return
  const next = [...graph.value]
  next[i] = v
  emit('update:modelValue', next)
}
</script>

<style scoped>
.q-block { margin-bottom: 1.8rem; }
.q-label {
  display: block; font-size: 1rem; font-weight: 800;
  color: var(--navy); margin-bottom: 0.6rem; line-height: 1.5;
}
.q-guide { font-size: 0.85rem; color: var(--gray); margin-bottom: 0.7rem; line-height: 1.5; }
.muted { font-weight: 600; color: var(--gray); font-size: 0.85rem; }
.q-error { margin-top: 0.5rem; font-size: 0.85rem; color: var(--coral); font-weight: 700; }

.chips { display: flex; gap: 0.5rem; }
.chips.wrap { flex-wrap: wrap; }
.chip {
  border: 2px solid var(--gray-light); background: #fff; color: var(--gray);
  padding: 0.6rem 1rem; border-radius: 99px; font-size: 0.92rem;
  font-weight: 700; cursor: pointer; transition: all 0.15s;
}
.chip:hover { border-color: var(--mint); }
.chip.sel { border-color: var(--mint); background: var(--mint); color: #fff; }
/* 상한에 걸려 더 고를 수 없는 선지 — 왜 안 눌리는지 보이게 한다 */
.chip.dim { opacity: 0.45; cursor: not-allowed; }

/* 권수 입력 — 초4도 쓸 수 있게 버튼을 크게 */
.num-row { display: flex; align-items: center; gap: 0.6rem; }
.num-btn {
  width: 44px; height: 44px; border-radius: 12px;
  border: 2px solid var(--gray-light); background: #fff;
  font-size: 1.3rem; font-weight: 800; color: var(--navy); cursor: pointer;
}
.num-btn:hover:not(:disabled) { border-color: var(--mint); color: var(--mint); }
.num-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.num-input {
  width: 90px; height: 44px; text-align: center;
  border: 2px solid var(--gray-light); border-radius: 12px;
  font-size: 1.1rem; font-weight: 800; color: var(--navy);
}
.num-unit { font-size: 0.95rem; font-weight: 700; color: var(--gray); }

/* 학년별 독서량 표 */
.grade-grid { overflow-x: auto; }
.grade-head, .grade-row {
  display: grid;
  grid-template-columns: 4.2rem repeat(6, minmax(3.2rem, 1fr));
  align-items: center; gap: 0.2rem;
}
.grade-scale-label {
  font-size: 0.68rem; color: var(--gray); text-align: center;
  font-weight: 700; line-height: 1.2; padding-bottom: 0.4rem;
}
.grade-row { margin-bottom: 0.25rem; }
.grade-row.disabled { opacity: 0.35; }
.grade-name { font-size: 0.85rem; font-weight: 700; color: var(--navy); }
.grade-cell {
  height: 40px; border: 2px solid var(--gray-light); background: #fff;
  border-radius: 10px; cursor: pointer; display: flex;
  align-items: center; justify-content: center; transition: all 0.12s;
}
.grade-cell:hover:not(:disabled) { border-color: var(--mint); }
.grade-cell:disabled { cursor: not-allowed; }
.grade-cell .dot {
  width: 10px; height: 10px; border-radius: 50%; background: var(--gray-light);
}
.grade-cell.sel { border-color: var(--mint); background: var(--mint); }
.grade-cell.sel .dot { background: #fff; }
</style>
