"""스키마 틀(schemas/base.py) 자체의 함정.

[공유 별칭의 기본값 오염 — 실제로 났다]
pydantic 2.5 는 `step: Annotated[int, Field(ge=0)] = 1` 처럼 별칭에 기본값을 주면
별칭 안의 Field 객체에 그 기본값을 **써 넣는다**. Count 가 `Field(ge=0)` 를 품고
있을 때 설문 스키마의 `step: Count = 1` 한 줄 때문에, 그 뒤에 정의된 모든 Count 칸
(정답 번호·읽기 시간·음절 수 …)이 기본값 1 을 갖게 됐다 — 빠진 칸이 거부되지
않고 1 로 채워졌다. 에러는 없었다.
"""
import importlib
import pkgutil
import typing

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

import app.schemas as schemas_pkg
from app.schemas.base import Count, Ratio


def _shared_aliases():
    for m in pkgutil.iter_modules(schemas_pkg.__path__):
        mod = importlib.import_module(f"app.schemas.{m.name}")
        for name, obj in vars(mod).items():
            if typing.get_origin(obj) is typing.Annotated:
                yield f"{m.name}.{name}", obj


def test_공유_별칭에_기본값이_새어_들어가지_않았다():
    """모든 스키마를 불러온 뒤에도 별칭 안의 Field 객체는 기본값이 없어야 한다."""
    leaked = [name for name, alias in _shared_aliases()
              for meta in typing.get_args(alias)[1:]
              if isinstance(meta, FieldInfo) and meta.default is not PydanticUndefined]
    assert not leaked, f"별칭에 기본값이 새어 들어갔다: {leaked}"


def test_기본값을_준_칸이_다른_칸을_오염시키지_않는다():
    class First(BaseModel):
        a: Count = 1
        r: Ratio = 0.5

    class Later(BaseModel):
        a: Count
        r: Ratio

    assert Later.model_fields["a"].is_required()
    assert Later.model_fields["r"].is_required()


def test_빠진_필수_칸은_거부된다():
    """오염이 실제로 드러났던 칸들."""
    from app.schemas.content import SeedText
    from app.schemas.measurement import AnswerSubmit, SilentReadingSubmit
    for model, field in [(SeedText, "syllable_count"), (AnswerSubmit, "student_answer"),
                         (SilentReadingSubmit, "reading_time_ms")]:
        assert model.model_fields[field].is_required(), f"{model.__name__}.{field}"


def test_한_칸에_같은_종류의_제약이_겹치지_않는다():
    """Annotated[Count, ...] = Field(ge=1) 처럼 겹치면 뒤에 붙은 Ge(0) 가 이겨
    ge=1 이 조용히 풀린다(선지 번호 0 이 통과됐다). 겹칠 일이 있으면 별칭을 따로 둔다."""
    import collections
    from tests.test_schema_principles import _all_schemas
    kinds = ("Ge", "Gt", "Le", "Lt", "MinLen", "MaxLen")
    dup = []
    for model in _all_schemas():
        for name, f in model.model_fields.items():
            c = collections.Counter(type(m).__name__ for m in f.metadata)
            if any(c[k] > 1 for k in kinds):
                dup.append(f"{model.__name__}.{name}")
    assert not dup, dup


def test_스키마는_contracts_폴더에만_있다():
    """스키마를 다른 곳에 만들면 원칙 검사·명세에서 빠진다. 실제로 app/schemas 의
    응답 25개가 느슨한 부모를 써서 검사 밖에 있었다(2026-09-26 옮김)."""
    import main  # noqa: F401 — 앱 전체를 불러와 모든 스키마가 등록되게 한다
    from pydantic_settings import BaseSettings

    seen, stack, outside = set(), [BaseModel], []
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            stack.append(sub)
            mod = sub.__module__
            if mod.startswith("app.") and not mod.startswith("app.schemas") \
                    and not issubclass(sub, BaseSettings):     # 서버 설정은 데이터 인터페이스가 아니다
                outside.append(f"{mod}.{sub.__name__}")
    assert not outside, f"스키마는 app/schemas 에 둔다: {outside}"
