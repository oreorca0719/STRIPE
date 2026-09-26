"""값이 아니라 **형태**를 적는다.

[왜 형태만인가]
흐름 대시보드는 "무엇이 오갔는가" 를 보여주는 도구다. 그런데 오가는 것이
아동의 설문 응답·판정 결과·리포트 문구다. 값을 파일에 남기면 그 파일이
학생 데이터가 된다(PM 결정 2026-09-24: A안 — 형태만).

그래서 이 모듈은 **타입·개수·키 이름**까지만 적는다.

    CellResponse[6]
    ComprehensionJudgment{comprehension_level: Level3.high,
                          profile: WeaknessProfile{cells: WeaknessCell[6]}, …}

[예외 둘 — 개인정보가 아니고, 없으면 흐름을 못 읽는다]
· enum 값        GradeGroup.G4_G6 · betts_level=instructional
                 흐름이 왜 그렇게 갈렸는지가 전부 enum 에서 결정된다
· 개수·null 여부  12키 중 3개 null
                 이 프로젝트의 null 은 "측정 안 함" 이고 0 과 다르다.
                 형식 파악의 핵심이라 개수는 남긴다

숫자·문자열 값은 남기지 않는다. `round_accuracy: 0.83` 은 학생의 점수다.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from pydantic import BaseModel

MAX_KEYS = 14          # 키를 다 적으면 화면이 넘친다. 12셀이 최대라 여유만 둔다
MAX_DEPTH = 3          # 중첩을 끝까지 파면 리포트 3층에서 끝이 없다


def describe(value: Any, depth: int = 0) -> str:
    """값의 형태를 한 줄로. 값 자체는 넣지 않는다."""
    if value is None:
        return "None"

    # enum 은 값을 남긴다 — 분기 이유가 여기에 있다
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.value}"

    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return type(value).__name__
    if isinstance(value, str):
        return f"str(len={len(value)})"
    if isinstance(value, bytes):
        return f"bytes({len(value)})"

    if depth >= MAX_DEPTH:
        return type(value).__name__

    # dataclass·스키마 객체(pydantic) — 칸 이름과 각 칸의 형태
    names = None
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        names = [f.name for f in dataclasses.fields(value)]
    elif isinstance(value, BaseModel):
        names = list(type(value).model_fields)
    if names is not None:
        parts = []
        for name in names:
            try:
                parts.append(f"{name}: {describe(getattr(value, name), depth + 1)}")
            except Exception:
                parts.append(f"{name}: ?")
        inner = ", ".join(parts[:MAX_KEYS])
        if len(parts) > MAX_KEYS:
            inner += f", …+{len(parts) - MAX_KEYS}"
        return f"{type(value).__name__}{{{inner}}}"

    if isinstance(value, dict):
        keys = list(value.keys())
        nulls = sum(1 for v in value.values() if v is None)
        head = ", ".join(str(k) for k in keys[:MAX_KEYS])
        if len(keys) > MAX_KEYS:
            head += f", …+{len(keys) - MAX_KEYS}"
        tail = f", null {nulls}" if nulls else ""
        return f"dict({len(keys)}키{tail}){{{head}}}" if keys else "dict(0키)"

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        kind = type(value).__name__
        if not items:
            return f"{kind}[0]"
        # 원소 타입이 한 가지면 그것만, 섞였으면 섞였다고 적는다
        types = {describe(i, depth + 1).split("{")[0].split("(")[0] for i in items[:8]}
        el = types.pop() if len(types) == 1 else "mixed"
        return f"{el}[{len(items)}]"

    # ORM 엔티티·세션 등. 클래스 이름만. 식별자를 남기지 않는다.
    return type(value).__name__


def describe_args(args: tuple, kwargs: dict, names: list[str]) -> dict:
    """호출 인자의 형태. 이름을 알면 이름을 쓰고, 모르면 위치로 적는다.

    DB 세션은 형태에 의미가 없어 지운다 — 모든 줄에 AsyncSession 이 뜨면
    읽히지 않는다.
    """
    out: dict = {}
    for i, v in enumerate(args):
        key = names[i] if i < len(names) else f"arg{i}"
        if type(v).__name__ in ("AsyncSession", "Session"):
            continue
        out[key] = describe(v)
    for k, v in kwargs.items():
        if type(v).__name__ in ("AsyncSession", "Session"):
            continue
        out[k] = describe(v)
    return out
