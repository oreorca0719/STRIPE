"""지문 주제 태그 — allowlist와 검증 (STR-125).

[왜 이 모듈이 필요한가]
주제 태그는 **두 곳에서 같은 어휘를 써야** 의미가 있다.

    지문   texts.topic_tags          "이 글은 무엇에 관한 글인가"
    학생   C-1 관심 주제 응답         "나는 무엇에 관심 있나"

텍스트 선택(§7)은 이 둘의 교집합 크기로 지문을 고른다. 어휘가 갈리면
교집합이 늘 비어 매칭이 조용히 죽는다. 실제로 죽어 있었다 —

    지문 태그  ANIMAL · FRIENDSHIP · SCIENCE …   (대문자)
    C-1 선지  animal · friendship · science …    (소문자)

집합 교집합이라 대소문자가 다르면 절대 만나지 않는다. 학생이 C-1 에서
15종을 전부 골라도 매칭되는 지문이 **0/48 편**이었다. 오류가 나지 않고
그냥 '관심 주제와 무관한 순서'로 떨어지기 때문에 드러나지 않았다.

[allowlist를 설문 정의에 둔 이유]
태그 목록을 이 파일에 또 적으면 세 번째 사본이 된다. 학생이 **고를 수 있는
것**이 곧 매칭 가능한 어휘의 전부이므로, C-1 선지가 allowlist다.
'기타'(other)는 자유입력용이라 태그가 아니다 — 제외한다.

[MVP1 은 태그 1개 고정]
문준석 확정(STR-125). 지문 식별자 형식이 태그 1개를 전제한다.

    TXT_{학년군}_{장르}_{주제태그}_{번호}

2개 이상이면 이 스키마로 식별자를 만들 수 없다. 저장 구조는 배열 그대로
두어, 복수 전환이 필요해지면 이 검증만 풀면 된다(스키마 변경 없음).
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from app.schemas.content import TopicTag

# MVP1 에서 지문 하나가 가질 수 있는 태그 수. 늘리려면 식별자 형식부터 바꿔야 한다.
MAX_TAGS = 1



class TagError(ValueError):
    """태그가 allowlist와 맞지 않는다. 메시지는 사람이 읽고 고칠 수 있어야 한다."""


def canonical() -> List[str]:
    """학생이 고를 수 있는 주제 코드. 이것이 매칭 가능한 어휘의 전부다."""
    return [t.value for t in TopicTag]


def normalize(tags: Iterable[str] | None) -> List[str]:
    """대소문자·공백만 정리한다. 없는 코드를 만들어내지 않는다.

    ANIMAL → animal 은 같은 낱말을 표기만 맞추는 것이라 안전하다. 반면
    NATURE → animal 같은 **뜻의 치환은 하지 않는다** — 그건 기획 결정이고,
    코드가 임의로 정하면 '동물 글'이 아닌 것이 동물로 추천된다.
    """
    return [str(t).strip().lower() for t in (tags or []) if str(t).strip()]


def validate(tags: Sequence[str] | None) -> List[str]:
    """정규화한 태그를 돌려준다. 규격에 맞지 않으면 TagError.

    검증을 저장 직전에 두는 이유: 잘못된 태그는 오류를 내지 않고 '매칭이 안
    되는 지문'으로 조용히 남는다. 들어올 때 막지 않으면 나중에 찾을 수 없다.
    """
    norm = normalize(tags)
    if len(norm) != MAX_TAGS:
        raise TagError(
            f"주제 태그는 정확히 {MAX_TAGS}개여야 합니다 (받은 값: {list(tags or [])}). "
            f"지문 식별자 형식 TXT_{{학년군}}_{{장르}}_{{주제태그}}_{{번호}} 가 1개를 전제합니다."
        )
    allowed = set(canonical())
    unknown = [t for t in norm if t not in allowed]
    if unknown:
        raise TagError(
            f"학생이 고를 수 없는 주제 태그입니다: {unknown}. "
            f"C-1 선지에 없는 코드를 달면 그 지문은 어떤 학생과도 매칭되지 않습니다. "
            f"허용 코드: {sorted(allowed)}"
        )
    return norm
