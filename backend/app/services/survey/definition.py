"""설문 문항 정의 조회 (STR-122).

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

[형식]
파일의 형식은 app/contracts/survey.py 가 정한다. 읽는 순간 검사하고, 여기서는
형식 객체만 돌려준다. 응답 검증(선지·범위·개수)도 그 파일의 응답 형식이 한다 —
예전에는 여기의 validate() 가 dict 를 훑어 따로 검사했다.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Union

from app.contracts.survey import Question, definition
from app.enums import QuestionStatus

# MVP1 런타임에서 화면에 뜨는 상태. reserved 는 정의만 있고 수집하지 않는다.
RENDERED = (QuestionStatus.active, QuestionStatus.conditional)


def questions(part: str, include_reserved: bool = False) -> List[Question]:
    """part('student'|'parent')의 문항 목록."""
    rows = getattr(definition(), part)
    if include_reserved:
        return list(rows)
    return [q for q in rows if q.status in RENDERED]


@lru_cache(maxsize=2)
def _by_code(part: str) -> Dict[str, Question]:
    return {q.code: q for q in getattr(definition(), part)}


def get(part: str, code: str) -> Optional[Question]:
    return _by_code(part).get(code)


def option_values(part: str, code: str) -> List[Union[int, str]]:
    q = get(part, code)
    return [o.value for o in getattr(q, "options", [])]


def env_score_codes() -> List[str]:
    """home_environment_score 를 구성하는 문항 코드 (B-3~B-6)."""
    return [q.code for q in definition().parent if q.env_score]


def storage_map(part: str, include_reserved: bool = False) -> Dict[str, str]:
    """문항 코드 → 저장 칸 이름. 저장 칸이 없는 문항은 제외."""
    return {q.code: q.storage_field
            for q in questions(part, include_reserved) if q.storage_field}
