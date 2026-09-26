"""스키마 정의(app/schemas)에서 명세 문서를 만든다.

코드가 SSOT다. 문서를 손으로 고치지 않는다 — 스키마를 바꾸면 이것을 다시 돌린다.

    python -m app.schemas.spec           # docs/스키마_명세.md 를 다시 쓴다

tests/test_schema_spec.py 가 문서가 코드와 같은지 확인한다. 스키마를 바꾸고
문서를 다시 만들지 않으면 테스트가 실패한다.
"""
from __future__ import annotations

import enum
import importlib
import inspect
import pathlib
import pkgutil
import types
import typing

from annotated_types import Ge, Le
from pydantic import BaseModel
from pydantic.fields import FieldInfo

import app.schemas as pkg
from app.schemas.base import Schema, FreeText, Unitless

DOC_PATH = pathlib.Path(__file__).resolve().parents[3] / "docs" / "스키마_명세.md"

# 명세에 싣는 순서 (인터페이스의 흐름 순서). 새 파일을 만들면 여기에 넣는다.
MODULE_ORDER = ["account", "session", "measurement", "oral", "judgment", "prescription", "report", "student", "survey", "content", "admin", "pilot", "privacy", "review", "ops"]


def _type_text(tp, meta=()) -> str:
    """칸 타입을 사람이 읽는 말로."""
    # Annotated 안의 Field(ge=…) 는 FieldInfo 로 남는다 — 안쪽 제약을 꺼낸다
    meta = tuple(x for m in meta for x in (m.metadata if isinstance(m, FieldInfo) else [m]))
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        base, *m = typing.get_args(tp)
        return _type_text(base, (*meta, *m))
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        inner = " · ".join(_type_text(a, meta) for a in args)
        return f"{inner} 또는 null"
    if origin in (list, typing.List):
        (a,) = typing.get_args(tp)
        return f"{_type_text(a)} 목록"
    lo = next((m.ge for m in meta if isinstance(m, Ge)), None)
    hi = next((m.le for m in meta if isinstance(m, Le)), None)
    rng = ""
    if lo is not None and hi is not None:
        rng = f" {lo:g}~{hi:g}"
    elif lo is not None:
        rng = f" ≥{lo:g}"
    if tp is bool:
        return "참/거짓"
    if tp is int:
        return f"정수{rng}"
    if tp is float:
        return f"실수{rng}"
    if tp is str:
        return "문장"
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return f"`{tp.__name__}`"
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return f"[{tp.__name__}](#{tp.__name__.lower()})"
    return getattr(tp, "__name__", str(tp))


def _field_note(field, meta) -> str:
    notes = [field.description] if field.description else []
    notes += [m.why for m in meta if isinstance(m, (FreeText, Unitless))]
    return " — ".join(notes)


def _leaf_meta(tp, meta=()):
    """칸 안쪽(목록 원소 등)에 달린 사유 표시까지 모은다."""
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        base, *m = typing.get_args(tp)
        return _leaf_meta(base, (*meta, *m))
    if origin in (typing.Union, types.UnionType, list, typing.List):
        out = tuple(meta)
        for a in typing.get_args(tp):
            out += _leaf_meta(a)
        return out
    return tuple(meta)


def _doc(obj) -> str:
    return inspect.cleandoc(obj.__doc__ or "").strip()


def _schemas_in(module):
    return [c for c in vars(module).values()
            if isinstance(c, type) and issubclass(c, Schema) and c is not Schema
            and c.__module__ == module.__name__]


def _enums_used(classes):
    found = []
    for c in classes:
        for f in c.model_fields.values():
            stack = [f.annotation]
            while stack:
                t = stack.pop()
                stack.extend(typing.get_args(t))
                if isinstance(t, type) and issubclass(t, enum.Enum) and t not in found:
                    found.append(t)
    return found


def render() -> str:
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"app.schemas.{m.name}")
    modules = [importlib.import_module(f"app.schemas.{n}") for n in MODULE_ORDER]
    all_classes = [c for mod in modules for c in _schemas_in(mod)]

    out = [
        "# 스키마 명세",
        "",
        "> **이 문서는 자동 생성된다. 손으로 고치지 않는다.**",
        "> SSOT는 `backend/app/schemas/` 의 코드다. 스키마를 바꾼 뒤",
        "> `python -m app.schemas.spec` 로 다시 만든다. 코드와 다르면 테스트가 실패한다.",
        "",
        "공통 규칙 (모든 스키마)",
        "",
        "| 규칙 | 어기면 |",
        "|---|---|",
        "| 스키마에 없는 키 | 거부 |",
        "| 숫자 칸에 문자열·참/거짓 (`\"5\"`, `True`) | 거부 — 자동 변환하지 않는다 |",
        "| 만든 뒤 값 고치기 | 거부 — 바꾸려면 새로 만든다 |",
        "| JSONB 칸에 dict 저장 | 거부 — 스키마 객체만 저장한다 |",
        "| DB 에서 스키마와 다른 행을 읽기 | 읽는 순간 오류 |",
        "",
        "`null` 은 **측정 안 함·해당 없음**이다. 0 과 다르다. 원칙은 `docs/스키마_원칙.md`.",
        "",
        "## 목차",
        "",
    ]
    for mod in modules:
        title = _doc(mod).splitlines()[0].rstrip(".")
        out.append(f"- **{title}**")
        for c in _schemas_in(mod):
            out.append(f"  - [{c.__name__}](#{c.__name__.lower()})")
    out.append("- **값 목록 (enum)**")
    out.append("")

    for mod in modules:
        doc = _doc(mod).splitlines()
        out += ["---", "", f"## {doc[0].rstrip('.')}", ""]
        body = [l for l in doc[1:] if l.strip()]
        if body:
            out += ["```"] + body + ["```", ""]
        for c in _schemas_in(mod):
            out += [f"### {c.__name__}", ""]
            d = _doc(c)
            if d:
                out += [d, ""]
            out += ["| 칸 | 스키마 | 필수 | 설명 |", "|---|---|---|---|"]
            for name, f in c.model_fields.items():
                meta = _leaf_meta(f.annotation, tuple(f.metadata))
                req = "필수" if f.is_required() else (
                    "생략 시 null" if f.default is None else f"생략 시 `{f.default}`")
                typ = _type_text(f.annotation, tuple(f.metadata))
                out.append(f"| `{name}` | {typ} | {req} | {_field_note(f, meta)} |")
            props = [n for n, v in vars(c).items() if isinstance(v, property)]
            if props:
                out += ["", "계산값 (저장하지 않는다): " + " · ".join(f"`{p}`" for p in props)]
            out.append("")

    out += ["---", "", "## 값 목록 (enum)", "",
            "여기 없는 값은 스키마 검사와 DB 양쪽에서 거부된다.", "",
            "| 이름 | 값 |", "|---|---|"]
    for e in _enums_used(all_classes):
        out.append(f"| `{e.__name__}` | " + " · ".join(f"`{m.value}`" for m in e) + " |")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    DOC_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {DOC_PATH}")
