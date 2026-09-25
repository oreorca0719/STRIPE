"""형식 정의의 공통 틀.

[이 폴더가 하는 일]
모듈이 주고받는 데이터의 형식을 **여기 한 곳에만** 적는다. 내보내는 쪽은
이 형식 객체를 만들어 넘기고, 받는 쪽은 이 형식 객체의 칸으로 읽는다.
dict 로 주고받지 않는다 — dict 는 키가 틀려도 조용히 빈 값이 된다.

[엄격한 이유]
형식이 달라도 파이썬은 에러를 내지 않는다. 실제 결함(A1 단위 6배, 태그
0/48 매칭)이 모두 에러 없이 틀린 결과만 냈다. 그래서 경계에서 드러나게 한다.

    모르는 키        → 거부 (extra="forbid")
    "5" → 5 변환     → 거부 (숫자 칸에 문자열·불리언 금지)
    만든 뒤 고치기    → 거부 (frozen) — 바꾸려면 model_copy 로 새로 만든다

[공통 원칙 5가지 — docs/데이터_형식_원칙.md]
1 단위를 이름에  2 null 은 0 이 아니다  3 정해진 값은 enum
4 원본과 계산값을 섞지 않는다  5 같은 사실은 한 곳에서만
1·2·3 은 tests/test_contract_principles.py 가 모든 형식을 훑어 검사한다.
"""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class Contract(BaseModel):
    """모든 형식의 부모. 이 규칙을 개별 형식에서 풀지 않는다."""
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


# ── 원칙 3: 자유 문자열은 표시를 달아야만 쓸 수 있다 ──────────────────────
class FreeText:
    """이 칸은 정해진 값이 아니라 사람이 읽는 문장이다.

    원칙 검사는 str 칸 가운데 이 표시가 없는 것을 실패시킨다. 정해진 값이면
    enum 으로 만들고, 정말 자유 문장일 때만 이 표시를 단다 — 고르는 순간
    "이게 정해진 값인가?" 를 한 번 생각하게 하려는 장치다.
    """
    def __init__(self, why: str):
        self.why = why


# ── 원칙 1: 단위가 없는 숫자에는 사유를 적는다 ───────────────────────────
class Unitless:
    """이 숫자 칸은 이름에 단위가 없어도 된다. 사유를 적는다."""
    def __init__(self, why: str):
        self.why = why


def _number_only(v: Any) -> Any:
    """숫자 칸에 문자열·불리언이 오면 거부한다. 정수 → 실수는 허용한다.

    파이썬에서 True 는 1 이다. 불리언이 숫자 칸에 들어가도 조용히 1 이 되므로
    막는다. "0.83" 같은 문자열을 숫자로 바꿔 주는 것도 막는다.
    """
    if isinstance(v, (str, bytes, bool)):
        raise ValueError(f"숫자 칸에 {type(v).__name__} 가 왔다")
    return v


Int = StrictInt
Bool = StrictBool
Float = Annotated[float, BeforeValidator(_number_only)]
Count = Annotated[StrictInt, Field(ge=0)]
Ratio = Annotated[float, BeforeValidator(_number_only), Field(ge=0.0, le=1.0)]
"""0~1 비율. 퍼센트(0~100)는 이름을 _pct 로 끝낸다."""


def Text(why: str):
    """자유 문장 칸. 사유를 반드시 적는다: `title: Text("지문 제목 — 콘텐츠 원문")`."""
    return Annotated[StrictStr, FreeText(why)]
