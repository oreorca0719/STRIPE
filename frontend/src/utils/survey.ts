/**
 * 설문 문항의 화면 타입.
 *
 * 문항 형식은 서버(app/contracts/survey.py)가 응답 유형별로 나눠 정한다. 여기서는
 * 그 합집합에 이름만 붙인다 — response_type 으로 좁히면 유형별 칸(options·min·
 * grades …)이 드러난다.
 */
import type { SurveyQuestions } from '@/api-types'

export type SurveyItem = SurveyQuestions['questions'][number]

/** 문항 하나의 응답 값. 유형마다 모양이 달라 화면에서는 합집합으로 들고 다닌다. */
export type SurveyValue = number | string | (number | string)[] | (number | null)[] | null

/** 422 응답의 detail 은 문자열이거나(서버가 직접 막은 경우) 형식 검사 목록이다. */
export function errorDetail(e: any, fallback: string): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x: any) => x.msg).join(', ')
  return fallback
}
