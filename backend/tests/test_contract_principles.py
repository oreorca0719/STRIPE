"""공통 원칙 1·2·3 을 모든 형식에 기계적으로 건다.

형식 하나하나를 사람이 검토하면 빠뜨린다. 여기서는 app/contracts 의 모든 형식을
훑어 칸마다 검사한다. 새 형식을 추가하면 자동으로 검사 대상이 된다.

    원칙 1  숫자 칸 이름에 단위가 있다 (없으면 Unitless("사유") 를 단다)
    원칙 2  숫자 칸의 기본값이 0 이 아니다 (없음은 None)
    원칙 3  문자열 칸은 enum 이다 (자유 문장이면 Text("사유") 를 단다)

원칙 4(원본과 계산값 분리)·5(같은 사실은 한 곳)는 구조의 문제라 기계적으로
판정할 수 없다. docs/데이터_형식_원칙.md 의 검토 항목으로 둔다.

[새 코드 가드]
모듈이 dict·Any 로 주고받는 함수를 새로 만들면 실패한다. 아직 정리하지 않은
곳은 ALLOWED_UNTYPED 에 사유와 함께 남기고, 정리하면 목록에서 지운다.
"""
import ast
import enum
import importlib
import pathlib
import pkgutil
import re
import types
import typing

import pytest
from pydantic import BaseModel

import app.contracts as contracts_pkg
from app.contracts.base import Contract, FreeText, Unitless

# 이름에 이 조각이 하나라도 있으면 단위가 드러난 것으로 본다.
UNIT_TOKENS = {
    "count", "counts", "ms", "sec", "seconds", "minute", "minutes", "month", "months",
    "ratio", "accuracy", "pct",
    "id", "ids", "syllable", "syllables", "score", "index", "number",
}


def _all_contracts():
    for m in pkgutil.iter_modules(contracts_pkg.__path__):
        importlib.import_module(f"app.contracts.{m.name}")
    seen, stack = [], [Contract]
    while stack:
        c = stack.pop()
        for sub in c.__subclasses__():
            if sub not in seen:
                seen.append(sub)
                stack.append(sub)
    return seen


def _leaves(tp, meta=()):
    """형식 칸의 타입을 끝까지 풀어 (기본 타입, 붙은 표시들) 을 낸다."""
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        base, *m = typing.get_args(tp)
        yield from _leaves(base, (*meta, *m))
    elif origin in (typing.Union, types.UnionType):
        for a in typing.get_args(tp):
            if a is not type(None):
                yield from _leaves(a, meta)
    elif origin in (list, tuple, set, frozenset):
        for a in typing.get_args(tp):
            if a is not Ellipsis:
                yield from _leaves(a, meta)
    else:
        yield tp, meta


def _fields():
    for model in _all_contracts():
        for name, f in model.model_fields.items():
            for tp, meta in _leaves(f.annotation, tuple(f.metadata)):
                yield model, name, f, tp, meta


FIELDS = list(_fields())
_ids = [f"{m.__name__}.{n}" for m, n, *_ in FIELDS]


def test_검사할_형식이_있다():
    """검사 대상을 못 찾으면 아래 검사가 전부 빈손으로 통과한다."""
    assert len(_all_contracts()) >= 15
    assert len(FIELDS) >= 40


@pytest.mark.parametrize("model,name,field,tp,meta", FIELDS, ids=_ids)
def test_원칙1_숫자_칸은_이름에_단위가_있다(model, name, field, tp, meta):
    if tp not in (int, float):
        return
    if any(isinstance(m, Unitless) for m in meta):
        return
    tokens = set(name.split("_"))
    assert tokens & UNIT_TOKENS, (
        f"{model.__name__}.{name}: 이름에 단위가 없다. "
        f"단위를 이름에 넣거나(예: _count, _ms, _ratio), Unitless('사유') 를 단다")


@pytest.mark.parametrize("model,name,field,tp,meta", FIELDS, ids=_ids)
def test_원칙2_숫자_칸의_기본값은_0이_아니다(model, name, field, tp, meta):
    if tp not in (int, float):
        return
    assert field.default != 0 or field.default is None or isinstance(field.default, bool), (
        f"{model.__name__}.{name}: 기본값이 0 이다. 값이 없으면 None 이다")


@pytest.mark.parametrize("model,name,field,tp,meta", FIELDS, ids=_ids)
def test_원칙3_문자열_칸은_정해진_값이거나_사유가_있다(model, name, field, tp, meta):
    if tp is not str:
        return
    assert any(isinstance(m, FreeText) for m in meta), (
        f"{model.__name__}.{name}: 자유 문자열이다. 정해진 값이면 enum 으로, "
        f"사람이 읽는 문장이면 Text('사유') 로 만든다")


def test_원칙_검사가_어긴_형식을_실제로_잡는다():
    """검사 로직 자체가 틀려 모두 통과시키는 경우를 막는다."""
    class Bad(BaseModel):
        speed: float
        memo: str
        n_items: int = 0

    got = {n: (tp, m) for n, f in Bad.model_fields.items()
           for tp, m in _leaves(f.annotation, tuple(f.metadata))}
    assert not (set("speed".split("_")) & UNIT_TOKENS)          # 원칙 1 위반으로 잡힌다
    assert not any(isinstance(m, FreeText) for m in got["memo"][1])  # 원칙 3 위반
    assert Bad.model_fields["n_items"].default == 0             # 원칙 2 위반


# ── 새 코드 가드: dict·Any 로 주고받는 서비스 함수 ─────────────────────────

# 아직 정리하지 않은 곳. 정리하면 지운다. 목록에 있는데 코드에서 사라져도 실패한다
# (목록이 낡지 않도록).
ALLOWED_UNTYPED = {
    "stt/adapter.py::STTResult.words": "음독 경로에서 정리 예정",
    "stt/analyzer.py::OralReadingAnalysis.alignment_deviations": "음독 경로에서 정리 예정",
    "stt/vad.py::to_dict": "음독 경로에서 정리 예정",
}

# 칸 타입이 드러나지 않는 것만 잡는다: 맨 dict·Dict, Any. Dict[str, str] 처럼 키·값
# 타입을 적은 것은 형식이 드러나 있으므로 통과한다(Dict[str, Any] 는 Any 로 잡힌다).
_UNTYPED = re.compile(r"\b(?:dict|Dict)\b(?!\[)|\bAny\b")


def _untyped_in_services():
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    hits = set()
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                sig = ast.unparse(n.args) + " -> " + (ast.unparse(n.returns) if n.returns else "")
                if _UNTYPED.search(sig):
                    hits.add(f"{rel}::{n.name}")
            if isinstance(n, ast.ClassDef):
                for s in n.body:
                    if isinstance(s, ast.AnnAssign) and _UNTYPED.search(ast.unparse(s.annotation)):
                        hits.add(f"{rel}::{n.name}.{ast.unparse(s.target)}")
    return hits


def test_새로_dict로_주고받는_서비스_함수가_생기지_않는다():
    new = _untyped_in_services() - set(ALLOWED_UNTYPED)
    assert not new, f"dict·Any 로 주고받는 함수가 새로 생겼다. 형식을 정의해 쓴다: {sorted(new)}"


def test_정리된_곳은_허용_목록에서_지운다():
    gone = set(ALLOWED_UNTYPED) - _untyped_in_services()
    assert not gone, f"이미 정리됐다 — ALLOWED_UNTYPED 에서 지운다: {sorted(gone)}"
