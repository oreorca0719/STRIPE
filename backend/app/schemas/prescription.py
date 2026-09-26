"""처방 → 리포트·도서 인터페이스의 스키마.

생산자  services/diagnosis/prescription.py · environment.py · pipeline.py (저장)
소비자  services/diagnosis/report.py
저장    prescription_results.recommended_texts · weakness_training_plan
        · environment_level · environment_adjustment
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import Field, model_validator

from app.schemas.base import Bool, Schema, Count, Int
from app.enums import EnvironmentSkipReason, Level3, TargetArea, TextGenre


class RecommendedTexts(Schema):
    """추천 지문의 **참조 목록**, 우선순위 순서.

    예전에는 제목·난도·장르까지 복사해 저장했다. 그러면 같은 사실(지문 제목)이
    texts 와 여기 두 곳에 생긴다(원칙 5). 이제 id 만 남기고, 화면에 보여 줄
    때 리포트가 지문 테이블에서 읽는다. 보여 준 그대로의 사본은 리포트에 남는다.
    """
    text_ids: List[Int] = Field(description="texts.id. 앞이 우선순위 높음, 중복 없음, 최대 5")

    @model_validator(mode="after")
    def _unique(self):
        if len(set(self.text_ids)) != len(self.text_ids):
            raise ValueError("추천 지문이 중복됐다")
        return self


class TrainingTarget(Schema):
    """약점 훈련 대상 한 칸."""
    area: TargetArea = Field(description="훈련할 독해 영역")
    genre: TextGenre = Field(description="훈련할 지문 장르")


class TrainingPlan(Schema):
    """약점 훈련 대상, 우선순위 순서, 최대 2칸.

    예전에는 정답률과 활동 안내 문장까지 담았다. 정답률은 판정의 약점
    프로필에 이미 있고(원칙 5), 안내 문장은 영역에서 정해지는 표시용
    문구다. 이제 대상만 남긴다. 대상이 없으면 훈련이 필요 없다는 뜻이다.
    """
    targets: List[TrainingTarget] = Field(description="우선순위 순, 최대 2칸, 중복 없음. 비면 훈련 불필요")

    @model_validator(mode="after")
    def _valid(self):
        if len(self.targets) > 2:
            raise ValueError("훈련 대상은 최대 2칸")
        keys = [(t.area, t.genre) for t in self.targets]
        if len(set(keys)) != len(keys):
            raise ValueError("훈련 대상이 중복됐다")
        return self

    @property
    def needed(self) -> bool:
        return bool(self.targets)


class EnvironmentAdjustment(Schema):
    """가정환경 하위일 때 추천을 조절하는 값 (문준석 STR-92)."""
    success_emphasis: Bool = Field(description="완독 성공 경험을 강조할지")
    # 추천 지문 분량 상한(음절). 없으면 제한 없음. **아직 소비하는 곳이 없다.**
    syllable_limit: Optional[Count] = Field(None, description="추천 지문 분량 상한(음절). null 이면 제한 없음. 아직 소비처 없음")


class EnvironmentResult(Schema):
    """가정환경 판정. 판정했으면 수준·조절값이 있고, 건너뛰었으면 사유가 있다.

    수준이 null 인 이유를 남긴다 — 보호자가 답하지 않은 것과 경계값이 없는
    것은 다른 상황이다. 보호자 안내 문구는 수준에서 정해지므로 담지 않는다
    (environment.guidance_tone 으로 만든다).
    """
    environment_level: Optional[Level3] = Field(None, description="가정환경 3단 수준. 건너뛰었으면 null")
    environment_adjustment: Optional[EnvironmentAdjustment] = Field(None, description="수준이 있을 때만 있다")
    skipped_reason: Optional[EnvironmentSkipReason] = Field(None, description="건너뛰었을 때만 있다")

    @model_validator(mode="after")
    def _either(self):
        judged = self.environment_level is not None
        if judged != (self.environment_adjustment is not None):
            raise ValueError("환경 수준과 조절값은 함께 있거나 함께 없어야 한다")
        if judged == (self.skipped_reason is not None):
            raise ValueError("판정했으면 건너뛴 사유가 없고, 건너뛰었으면 사유가 있어야 한다")
        return self

    @property
    def applied(self) -> bool:
        return self.environment_level is not None
