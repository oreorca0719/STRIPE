"""리포트 → 학생 화면 라인의 형식.

생산자  services/diagnosis/report.py
소비자  frontend ResultView · AdminDiagnosesView
저장    reports.report_content · reports.disclaimer_flags · reports.template_ids_used

[이 라인의 성격 — 표시용 문서]
리포트는 판정·처방에서 **만들어 낸 결과물**이고, 학생이 본 그대로 남아야 한다.
그래서 판정 쪽과 달리 정답률·제목 같은 계산값과 표시 문구를 그대로 담는다.
원본은 판정·처방에 있고, 이 문서는 그 원본에서 한 번 만든 사본이다(원칙 4).
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.contracts.base import Bool, Contract, Float, Int, Ratio, Text, Unitless
from app.contracts.judgment import CELL_ORDER
from app.enums import (
    Difficulty, FluencyUnit, Label5, Level3, Metacognition, TargetArea, TextGenre,
)


class RecommendedPreview(Contract):
    """추천 지문 미리보기 한 편 — 리포트를 만든 시점의 제목 사본."""
    text_id: Int = Field(description="texts.id")
    title: Text("지문 제목 — 리포트 생성 시점의 사본")
    genre: TextGenre = Field(description="지문 장르")
    difficulty: Difficulty = Field(description="지문 난도")


class ReportSummary(Contract):
    """1층 — 요약."""
    label: Text("학생 친화 라벨 문구 (report.STUDENT_LABEL)")
    label_code: Label5 = Field(description="라벨 문구의 원래 코드")
    strengths: List[Text("강점 문구 — '이야기글에서 사실 찾기' 형태")]
    encouragement: Text("응원 문구 — 템플릿 또는 폴백, LLM 다듬기 가능")
    recommended_preview: List[RecommendedPreview] = Field(description="처방 추천 순서대로 최대 3편")

    @model_validator(mode="after")
    def _limits(self):
        if len(self.recommended_preview) > 3:
            raise ValueError("추천 미리보기는 최대 3편")
        if len(self.strengths) > 2:
            raise ValueError("강점은 최대 2개")
        return self


class FluencyView(Contract):
    """유창성 — 판정 값을 그대로 옮긴다(변조 금지 §6)."""
    level: Level3 = Field(description="유창성 3단 수준")
    valid: Bool = Field(description="판정에 쓴 값인가. false 면 화면이 수치를 보여주지 않는다")
    value: Annotated[Optional[Float], Unitless("단위는 짝 칸 value_unit")] = None
    value_unit: FluencyUnit = Field(description="SPS=음절/초, CWPM=음절/분, 값 없으면 none")


class AreaView(Contract):
    """영역 × 장르 한 칸의 정답률. 문항이 없던 칸은 null(측정 안 함)."""
    area: TargetArea = Field(description="독해 영역")
    genre: TextGenre = Field(description="지문 장르")
    accuracy: Optional[Ratio] = Field(None, description="정답률 0~1. 문항이 없던 칸은 null")


class ComprehensionView(Contract):
    """독해 — 판정 값을 그대로 옮긴다."""
    level: Level3 = Field(description="독해 3단 수준")
    overall_accuracy: Optional[Ratio] = Field(None, description="전체 정답률 0~1. 문항이 없으면 null")
    areas: List[AreaView] = Field(description="6칸, 약점 프로필과 같은 순서")

    @model_validator(mode="after")
    def _grid(self):
        if tuple((a.area, a.genre) for a in self.areas) != CELL_ORDER:
            raise ValueError("영역 칸은 약점 프로필과 같은 6칸·같은 순서여야 한다")
        return self


class TrainingView(Contract):
    """약점 훈련 안내 한 칸 — 처방의 훈련 대상에 안내 문장을 붙였다."""
    area: TargetArea = Field(description="훈련할 독해 영역")
    genre: TextGenre = Field(description="훈련할 지문 장르")
    activity: Text("활동 안내 문장 (prescription._ACTIVITY)")


class ReportDetail(Contract):
    """2층 — 더 알아보기."""
    fluency: FluencyView = Field(description="유창성")
    comprehension: ComprehensionView = Field(description="독해")
    metacognition: Optional[Metacognition] = Field(None, description="메타인지. D-2 미수집이면 null(판정 안 함)")
    weakness_training: List[TrainingView] = Field(description="처방의 훈련 대상 순서, 최대 2칸")


class ReportContent(Contract):
    """학생 리포트 문서. 3층(layer3)은 계약상 무엇이 들어가는지 확인 전이라 두지 않는다."""
    layer1: ReportSummary = Field(description="요약 — 학생이 처음 보는 화면")
    layer2: ReportDetail = Field(description="더 알아보기")


class TemplateIds(Contract):
    """이 리포트에 쓰인 문구 템플릿 id. 비어 있으면 폴백 문구로 조립됐다."""
    ids: List[Int] = Field(description="report_templates.id. 비면 폴백 문구 사용")
