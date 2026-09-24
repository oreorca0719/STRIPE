/**
 * 진단 결과 표시 공용 유틸.
 *
 * 판정 등급(label_5)은 학생에게 원문 그대로 노출하지 않고 친화 표현으로 바꾼다(§2 SCR-13).
 * 홈·이력·결과 화면이 각자 매핑을 두면 같은 등급이 화면마다 다른 말로 보이므로 여기서만 정의한다.
 *
 * ★ 이 표의 `ko` 는 서버 `report.py` 의 STUDENT_LABEL 과 **같아야 한다**(STR-123 확정표).
 * 결과 화면은 서버가 준 라벨을 우선 쓰고 이 표를 폴백으로 쓰는데, 두 표가 다르면
 * 리포트 생성이 실패했을 때만 학생이 다른 말을 보게 된다 — 드물게 어긋나는 쪽이
 * 오히려 찾기 어렵다. 이력 화면은 리포트를 읽지 않으므로 **항상** 이 표를 쓴다.
 */

// lv(1~5 숫자 등급)는 제거했다(PM 결정 2026-09-24). 결과 화면에 'Lv. n / 5'
// 로 노출되던 값인데, 순위를 나누지 않는다는 제품 목적과 어긋났다.
// 수준은 라벨 문구가 전달한다.
export interface Label5Info {
  ko: string
  msg: string
  emoji: string
}

export const LABEL_5: Record<string, Label5Info> = {
  excellent: { ko: '잘하는 편!',            msg: '지금처럼 꾸준히 읽어보자 🌟',        emoji: '🌟' },
  observe:   { ko: '보통이야',              msg: '지금처럼 꾸준히 읽어보자 😊',        emoji: '😊' },
  caution:   { ko: '조금 더 연습하면 좋겠어', msg: '조금씩 같이 해보자 🌱',             emoji: '🌱' },
  risk:      { ko: '이 부분을 더 연습해보자', msg: '하나씩 같이 해보자. 할 수 있어 🤗',  emoji: '🤗' },
  urgent:    { ko: '함께 연습해보자!',       msg: '천천히 하나씩 같이 해보자 🌈',       emoji: '🌈' },
}

// 폴백 문구에서 난도 방향을 빼 둔 이유(STR-96): 위기 판정을 받은 학생이 애독자라는
// 이유로 "더 어려운 책에도 도전해보자" 를 받던 결함이 있었다. 서버 폴백에서는
// 걷어냈는데 화면 폴백에 "더 넓은 책의 세계로" · "최고 수준이에요" 가 남아 있었다.
// 후자는 특히 observe("보통이야") 학생에게 최상위에 가깝다고 말하는 것이었다.

export const DEFAULT_LABEL_5: Label5Info = { ko: '결과 준비 중', msg: '', emoji: '🌱' }

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
