"""MVP1 진단 엔진 (Phase B).

규칙 기반(LLM 미사용, v1.2 §6 AI-05/AI-06):
- scoring: 회차 집계 + Betts 판정 + 영역별 정답률 (§2 SCR-10, §3-2)
- adaptive: 적응형 반복 엔진 max_rounds=2 (§4 S2-FN-05)
- text_selection: approved 3단 텍스트 선택 + B7 관심주제 정렬 (§7 S2-FN-01)
- judgment: 유창성/독해 수준 + 12셀 약점 + 매트릭스 9칸 + 메타인지 (§3)
- prescription: 처방A 난도/주제/장르 필터 + 처방유형·톤 + 처방B 약점훈련 (§5)
- pipeline: SYS-01 판정+처방 오케스트레이션·DB 저장 (§9)
- report: 학생 3층 리포트 조립 + 선택적 LLM 다듬기 (§2 SCR-13, AI-07/08)
"""
from app.services.diagnosis import (  # noqa: F401
    scoring, adaptive, text_selection, judgment, prescription, pipeline, report,
)
