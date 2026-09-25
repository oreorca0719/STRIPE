"""판정 → 처방·리포트 라인의 형식.

생산자  services/diagnosis/judgment.py
소비자  services/diagnosis/pipeline.py (저장) · prescription.py · report.py
저장    judgment_results.weakness_profile_12 · judgment_results.disclaimer_flags
"""
from __future__ import annotations

from itertools import product
from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.contracts.base import Bool, Contract, Count, Float, Int, Unitless
from app.enums import (
    DisclaimerCode, FluencySource, FluencyUnit, Label5, Level3, Metacognition,
    PrescriptionGroup, ReliabilityFlag, TargetArea, TextGenre,
)

# 약점 프로필 칸의 정해진 순서. 이 순서가 곧 형식이다 — 다른 순서는 거부한다.
CELL_ORDER = tuple(product(
    (TargetArea.A5, TargetArea.A6, TargetArea.A7),
    (TextGenre.narrative, TextGenre.expository),
))


# ── 면책 코드 집합 ──────────────────────────────────────────────────────
def canonical_disclaimers(codes) -> List[DisclaimerCode]:
    """중복을 없애고 enum 정의 순서로 정렬한다. 집합이므로 순서에 뜻이 없다."""
    order = list(DisclaimerCode)
    return sorted({DisclaimerCode(c) for c in codes}, key=order.index)


class Disclaimers(Contract):
    """면책 코드의 **집합**. 순서에 뜻이 없고 중복이 없다.

    코드가 없으면 빈 목록이다. null 이 아니다 — null 은 "판정하지 않음"이다.
    """
    codes: List[DisclaimerCode] = Field(description="면책 코드. 중복 없이 enum 정의 순서")

    @model_validator(mode="after")
    def _canonical(self):
        if list(self.codes) != canonical_disclaimers(self.codes):
            raise ValueError("면책 코드는 중복 없이 정해진 순서여야 한다 (canonical_disclaimers 로 만든다)")
        return self

    @classmethod
    def of(cls, codes) -> "Disclaimers":
        return cls(codes=canonical_disclaimers(codes))


# ── 파이프라인 → 판정: 문항 응답 한 건 ─────────────────────────────────
class CellResponse(Contract):
    """약점 프로필을 만들 문항 응답 — 어느 영역·어느 장르 지문의 문항을 맞혔는가."""
    target_area: TargetArea = Field(description="문항이 재는 독해 영역")
    genre: TextGenre = Field(description="그 문항이 딸린 지문의 장르")
    is_correct: Bool = Field(description="정답 여부")


# ── 약점 프로필 (고정 격자) ─────────────────────────────────────────────
class WeaknessCell(Contract):
    """영역 × 장르 한 칸. 정답 수와 문항 수를 남긴다.

    정답률만 남기면 2문항 중 1개와 10문항 중 5개가 같은 0.5 가 된다.
    정답률은 원본(두 수)에서 계산하는 값이라 저장하지 않는다(원칙 4).
    """
    area: TargetArea = Field(description="독해 영역")
    genre: TextGenre = Field(description="지문 장르")
    correct_count: Count = Field(description="맞힌 문항 수. 문항 수 이하")
    question_count: Count = Field(description="푼 문항 수. 0 이면 이 칸은 측정 안 함")

    @model_validator(mode="after")
    def _counts(self):
        if self.correct_count > self.question_count:
            raise ValueError("정답 수가 문항 수보다 많다")
        return self

    @property
    def accuracy(self) -> Optional[float]:
        """정답률 0~1. 문항이 없으면 None — 측정하지 않은 칸이다(0 이 아니다)."""
        if self.question_count == 0:
            return None
        return self.correct_count / self.question_count


class WeaknessProfile(Contract):
    """3영역 × 2장르 = **6칸 고정**, CELL_ORDER 순서.

    DB 칸 이름은 명세를 따라 `weakness_profile_12` 지만 실제는 6칸이다.
    12 가 무엇의 곱인지는 기획 확인 대기(docs/모듈간_데이터_확정필요.md 2-1).
    """
    cells: List[WeaknessCell] = Field(description="6칸. A5·A6·A7 × 이야기글·설명글 순서 고정")

    @model_validator(mode="after")
    def _grid(self):
        got = tuple((c.area, c.genre) for c in self.cells)
        if got != CELL_ORDER:
            raise ValueError(f"약점 프로필은 6칸이 정해진 순서여야 한다: {CELL_ORDER}")
        return self

    def cell(self, area: TargetArea, genre: TextGenre) -> WeaknessCell:
        return self.cells[CELL_ORDER.index((area, genre))]

    @property
    def correct_count(self) -> int:
        return sum(c.correct_count for c in self.cells)

    @property
    def question_count(self) -> int:
        return sum(c.question_count for c in self.cells)

    @property
    def overall_accuracy(self) -> Optional[float]:
        """전체 정답률. 칸들의 합에서 계산한다 — 따로 세지 않는다(원칙 5)."""
        return None if self.question_count == 0 else self.correct_count / self.question_count


# ── 판정 모듈의 결과 ────────────────────────────────────────────────────
class FluencyJudgment(Contract):
    """유창성 판정. 값의 단위가 경우마다 달라서 값 칸과 단위 칸을 짝으로 둔다(원칙 1)."""
    fluency_level: Level3 = Field(description="유창성 3단 수준. 측정 불가일 때도 배치를 위해 mid")
    fluency_source: FluencySource = Field(description="어느 측정에서 왔나. 측정 불가면 unavailable")
    fluency_valid: Bool = Field(description="판정에 쓸 수 있는 값인가")
    fluency_value: Annotated[Optional[Float], Unitless("단위는 짝 칸 fluency_value_unit")] = None
    fluency_value_unit: FluencyUnit = Field(description="값의 단위. SPS=음절/초(묵독), CWPM=음절/분(음독), 값 없으면 none")
    reliability_flag: ReliabilityFlag = Field(description="유창성 측정의 신뢰도")
    disclaimers: Disclaimers = Field(description="유창성에서 나온 면책 코드")

    @model_validator(mode="after")
    def _pair(self):
        if (self.fluency_value is None) != (self.fluency_value_unit == FluencyUnit.none):
            raise ValueError("유창성 값이 없으면 단위는 none, 값이 있으면 단위가 있어야 한다")
        return self


class ComprehensionJudgment(Contract):
    """독해 판정. 정답 수·정답률은 프로필에서 계산한다 — 두 번 세지 않는다(원칙 5)."""
    comprehension_level: Level3 = Field(description="독해 3단 수준. 문항이 없으면 배치를 위해 mid")
    profile: WeaknessProfile = Field(description="영역×장르 6칸의 정답 수·문항 수")
    reliability_flag: ReliabilityFlag = Field(description="문항이 하나도 없으면 unstable")

    @property
    def overall_accuracy(self) -> Optional[float]:
        return self.profile.overall_accuracy


class MatrixPlacement(Contract):
    """유창성 × 독해 9칸 배치. 위치 문자열은 두 수준에서 만든다(원칙 5)."""
    fluency_level: Level3 = Field(description="행 — 유창성 수준")
    comprehension_level: Level3 = Field(description="열 — 독해 수준")
    label_5: Label5 = Field(description="9칸에서 정해지는 5단 라벨")
    prescription_group: PrescriptionGroup = Field(description="9칸에서 정해지는 처방군")

    @property
    def matrix_position(self) -> str:
        return f"fluency_{self.fluency_level.value}__comp_{self.comprehension_level.value}"


class MetacognitionResult(Contract):
    """자기 예측(D-2)과 실제의 차이. 10문항 기준으로 환산한 정답 수로 비교한다."""
    metacognition: Metacognition = Field(description="예측이 실제보다 높은가·낮은가·맞는가")
    actual_correct_count_of_10: Count = Field(description="실제 정답률을 10문항 기준으로 환산한 정답 수 (반올림)")
    gap_count: Int = Field(description="예측 − 실제, 문항 수 차이. 음수면 과소평가 쪽")


# ── 판정 → 화면: 약점 프로필 보기 ───────────────────────────────────────
# 저장 형식(WeaknessProfile)은 정답 수·문항 수만 갖는다. 화면은 칸마다 정답률이
# 필요하므로, 계산을 화면에 맡기지 않고(원칙 5) 서버가 계산해 붙인 보기 형식을
# 따로 둔다. ORM 의 WeaknessProfile 객체에서 칸을 그대로 읽어 만든다.
from pydantic import ConfigDict  # noqa: E402

from app.contracts.base import Ratio  # noqa: E402


class WeaknessCellView(Contract):
    """화면에 보내는 약점 칸 — 저장 형식에 서버가 계산한 정답률을 붙였다."""
    model_config = ConfigDict(from_attributes=True)
    area: TargetArea = Field(description="독해 영역")
    genre: TextGenre = Field(description="지문 장르")
    correct_count: Count = Field(description="맞힌 문항 수")
    question_count: Count = Field(description="푼 문항 수")
    accuracy: Optional[Ratio] = Field(None, description="정답률 0~1. 문항이 없던 칸은 null")


class WeaknessProfileView(Contract):
    """화면에 보내는 약점 프로필 (판정 API · 관리자 진단 상세)."""
    model_config = ConfigDict(from_attributes=True)
    cells: List[WeaknessCellView] = Field(description="6칸, 저장 형식과 같은 순서")
