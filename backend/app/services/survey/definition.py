"""설문 문항 정의 로더·검증기 (STR-122).

문항의 정본은 `app/data/survey_questions.json` 하나다. 화면은 이 정의를 받아
렌더링만 하고, 서버는 같은 정의로 응답을 검증한다.

[왜 화면에 하드코딩하지 않는가]
문구가 잠정본이라 계속 바뀐다(승인 절차 진행 중). 화면에 박아두면 문구가 바뀔
때마다 프론트를 다시 빌드·배포해야 하고, 서버의 검증 규칙과 화면의 선지가
따로 놀 여지가 생긴다. 실제로 관심주제(C-1)에서 선지 순서와 저장 코드가 어긋날
뻔한 적이 있다.

[왜 DB 마스터로 가지 않는가]
문구 한 줄 고치는 데 마이그레이션이나 관리 화면이 필요해진다. 지금은 그 비용이
얻는 것보다 크다. 이 JSON 이 나중에 DB 마스터의 시드가 되므로 옮겨갈 때 손해가 없다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "survey_questions.json"

# MVP1 런타임에서 화면에 뜨는 상태. reserved 는 정의만 있고 수집하지 않는다.
RENDERED = ("active", "conditional")


@lru_cache(maxsize=1)
def load() -> Dict[str, Any]:
    """정의 전체를 읽는다. 파일이 바뀌지 않으므로 프로세스당 한 번만."""
    return json.loads(_PATH.read_text(encoding="utf-8"))


def questions(part: str, include_reserved: bool = False) -> List[dict]:
    """part('student'|'parent')의 문항 목록."""
    rows = load()[part]
    if include_reserved:
        return rows
    return [q for q in rows if q["status"] in RENDERED]


@lru_cache(maxsize=2)
def _by_code(part: str) -> Dict[str, dict]:
    return {q["code"]: q for q in load()[part]}


def get(part: str, code: str) -> Optional[dict]:
    return _by_code(part).get(code)


def option_values(part: str, code: str) -> List[Any]:
    q = get(part, code)
    return [o["value"] for o in (q or {}).get("options", [])]


def env_score_codes() -> List[str]:
    """home_environment_score 를 구성하는 문항 코드 (B-3~B-6)."""
    return [q["code"] for q in load()["parent"] if q.get("env_score")]


def storage_map(part: str) -> Dict[str, str]:
    """문항 코드 → 저장 컬럼명. 저장 필드가 없는 문항은 제외."""
    return {q["code"]: q["storage_field"]
            for q in load()[part] if q.get("storage_field")}


# ── 검증 ─────────────────────────────────────────────────────────────────

class AnswerError(ValueError):
    """설문 응답이 정의와 맞지 않을 때. 메시지는 그대로 사용자에게 나간다."""


def validate(part: str, code: str, value: Any) -> Any:
    """응답 하나를 정의에 비추어 검사하고, 정규화된 값을 돌려준다.

    None(미응답)은 통과시킨다. 필수 여부는 화면과 저장 단계에서 따로 다룬다 —
    여기서 막으면 보호자가 중간에 그만둔 응답을 아예 받지 못하게 된다.
    """
    q = get(part, code)
    if q is None:
        raise AnswerError(f"정의에 없는 문항입니다: {code}")
    if value is None:
        return None

    rtype = q["response_type"]

    if rtype in ("numeric_input", "slider"):
        if not isinstance(value, int) or isinstance(value, bool):
            raise AnswerError(f"{code}: 숫자로 답해야 합니다.")
        lo, hi = q.get("min"), q.get("max")
        if lo is not None and value < lo or hi is not None and value > hi:
            raise AnswerError(f"{code}: {lo}~{hi} 범위를 벗어났습니다.")
        return value

    if rtype == "grade_history":
        return _validate_grade_history(q, value)

    allowed = option_values(part, code)

    if rtype in ("multi_select", "rank"):
        if not isinstance(value, list):
            raise AnswerError(f"{code}: 목록으로 답해야 합니다.")
        if len(set(value)) != len(value):
            raise AnswerError(f"{code}: 같은 항목을 두 번 골랐습니다.")
        for v in value:
            if v not in allowed:
                raise AnswerError(f"{code}: 선택지에 없는 값입니다 ({v}).")
        lo, hi = q.get("min_select"), q.get("max_select")
        if lo is not None and len(value) < lo:
            raise AnswerError(f"{code}: 최소 {lo}개를 골라야 합니다.")
        if hi is not None and len(value) > hi:
            raise AnswerError(f"{code}: 최대 {hi}개까지 고를 수 있습니다.")
        return value

    # single_select / scale_N
    if value not in allowed:
        raise AnswerError(f"{code}: 선택지에 없는 값입니다 ({value}).")
    return value


def _validate_grade_history(q: dict, value: Any) -> list:
    """A-4. 항상 길이 7 배열이며 각 칸은 정의된 척도값 또는 null.

    길이를 강제하는 이유는 인덱스가 곧 학년이기 때문이다. 잘린 배열을 받으면
    life_graph[-1] 이 4학년의 마지막 응답인지 중1의 것인지 알 수 없다.
    """
    n = len(q["grades"])
    if not isinstance(value, list) or len(value) != n:
        raise AnswerError(f"{q['code']}: 학년 {n}칸을 모두 채운 배열이어야 합니다.")
    allowed = {o["value"] for o in q["scale"]}
    for v in value:
        if v not in allowed:
            raise AnswerError(f"{q['code']}: 선택지에 없는 값입니다 ({v}).")
    return value
