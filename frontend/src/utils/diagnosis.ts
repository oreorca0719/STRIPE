/**
 * 진단 결과 표시 공용 유틸.
 *
 * 판정 등급(label_5)은 학생에게 원문 그대로 노출하지 않고 친화 표현으로 바꾼다(§2 SCR-13).
 * 홈·이력·결과 화면이 각자 매핑을 두면 같은 등급이 화면마다 다른 말로 보이므로 여기서만 정의한다.
 */

export interface Label5Info {
  lv: number
  ko: string
  msg: string
  emoji: string
}

export const LABEL_5: Record<string, Label5Info> = {
  excellent: { lv: 5, ko: '아주 잘함', msg: '정말 훌륭해요! 더 넓은 책의 세계로 나아가 볼까요?', emoji: '🌟' },
  observe:   { lv: 4, ko: '잘함',      msg: '잘하고 있어요! 조금만 더 하면 최고 수준이에요.',    emoji: '😊' },
  caution:   { lv: 3, ko: '보통',      msg: '또래와 비슷해요. 꾸준히 읽으면 쑥쑥 늘어요 💪',     emoji: '🌱' },
  risk:      { lv: 2, ko: '조금 부족',  msg: '이 부분을 함께 연습해봐요. 할 수 있어요!',         emoji: '🤗' },
  urgent:    { lv: 1, ko: '도움 필요',  msg: '천천히 하나씩 같이 해봐요. 괜찮아요!',             emoji: '🌈' },
}

export const DEFAULT_LABEL_5: Label5Info = { lv: 3, ko: '보통', msg: '', emoji: '🌱' }

export function labelInfo(label5?: string | null): Label5Info {
  return (label5 && LABEL_5[label5]) || DEFAULT_LABEL_5
}

/** 등급 → 짧은 한국어(카드·목록용). */
export const LABEL_5_KO: Record<string, string> = Object.fromEntries(
  Object.entries(LABEL_5).map(([k, v]) => [k, v.ko]),
)

export const LEVEL_3_KO: Record<string, string> = {
  low: '낮음',
  mid: '보통',
  high: '높음',
}

export const SESSION_STATUS_KO: Record<string, string> = {
  in_progress: '진행 중',
  completed: '완료',
  early_stop: '완료(조기 종료)',
  indeterminate: '판정 보류',
}

/** 신뢰도가 낮은 결과에 붙일 안내. normal 이면 표시하지 않는다. */
export const RELIABILITY_KO: Record<string, string> = {
  low: '측정이 불안정해 참고용이에요',
  unstable: '측정값이 부족해 참고용이에요',
}

/** 2026. 7. 18. 형태. 값이 없으면 '-'. */
export function formatDateKo(iso?: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
}

/** 목록용 짧은 표기 — 7. 18. */
export function formatDateShort(iso?: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}
