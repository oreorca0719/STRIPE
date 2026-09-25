"""서버 형식에서 화면용 TypeScript 타입을 만든다.

    python -m app.contracts.typescript     # frontend/src/api-types.ts 를 다시 쓴다

[왜 생성하나]
화면에 응답 타입이 0개였다. 서버가 칸 이름을 바꿔도 화면은 컴파일되고, 실행 중에
빈칸이 된다. 타입을 손으로 적으면 서버와 화면 두 곳에 같은 형식이 생겨 어긋난다
(원칙 5). 그래서 서버가 실제로 쓰는 형식(OpenAPI)에서 만든다.

tests/test_api_types.py 가 파일이 서버와 같은지 확인한다. 형식을 바꾸고 다시
만들지 않으면 실패한다.
"""
from __future__ import annotations

import pathlib
import re

OUT = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src" / "api-types.ts"

_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _name(ref: str) -> str:
    return _ts_name(ref.rsplit("/", 1)[-1])


def _ts_name(schema_name: str) -> str:
    """요청·응답 양쪽에 쓰여 둘로 갈린 형식: 응답용(-Output)은 원래 이름, 요청용(-Input)은 Input."""
    if schema_name.endswith("-Output"):
        return schema_name[:-len("-Output")]
    if schema_name.endswith("-Input"):
        return schema_name[:-len("-Input")] + "Input"
    return schema_name.replace("-", "_")


def _ts(s: dict) -> str:
    """JSON Schema 하나 → TypeScript 타입 식."""
    if "$ref" in s:
        return _name(s["$ref"])
    if "const" in s:
        return repr(s["const"]).replace("'", '"') if isinstance(s["const"], str) else str(s["const"]).lower()
    if "enum" in s:
        return " | ".join(f'"{v}"' for v in s["enum"])
    if "anyOf" in s or "oneOf" in s:
        parts = [_ts(x) for x in s.get("anyOf", s.get("oneOf"))]
        return " | ".join(dict.fromkeys(parts))
    if "allOf" in s:
        return " & ".join(_ts(x) for x in s["allOf"])
    t = s.get("type")
    if isinstance(t, list):
        return " | ".join(_ts({**s, "type": x}) for x in t)
    if t == "null":
        return "null"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "string":
        return "string"
    if t == "array":
        inner = _ts(s.get("items", {}))
        return f"({inner})[]" if " " in inner else f"{inner}[]"
    if t == "object" or "properties" in s:
        if "properties" not in s:
            extra = s.get("additionalProperties")
            return f"Record<string, {_ts(extra) if isinstance(extra, dict) else 'unknown'}>"
        return "{ " + " ".join(_field(k, v, k in s.get("required", [])) for k, v in s["properties"].items()) + " }"
    return "unknown"


def _field(key: str, s: dict, required: bool) -> str:
    k = key if _IDENT.match(key) else f'"{key}"'
    return f"{k}{'' if required else '?'}: {_ts(s)};"


def _doc(text: str, indent: str = "") -> list[str]:
    lines = [l.rstrip() for l in (text or "").strip().splitlines()]
    if not lines:
        return []
    if len(lines) == 1:
        return [f"{indent}/** {lines[0]} */"]
    return [f"{indent}/**"] + [f"{indent} * {l}" if l else f"{indent} *" for l in lines] + [f"{indent} */"]


def render() -> str:
    from main import app
    spec = app.openapi()
    schemas = spec["components"]["schemas"]

    out = [
        "/* eslint-disable */",
        "// 자동 생성 — 손으로 고치지 않는다.",
        "// 정본: backend/app/contracts/ (서버 형식). 다시 만들기: backend 에서",
        "//   python -m app.contracts.typescript",
        "// 서버 형식과 다르면 backend/tests/test_api_types.py 가 실패한다.",
        "",
    ]
    for name in sorted(schemas):
        s = schemas[name]
        ts_name = _ts_name(name)
        out += _doc(s.get("description", ""))
        if "enum" in s:
            out.append(f"export type {ts_name} = {_ts(s)}")
        elif "properties" in s:
            out.append(f"export interface {ts_name} {{")
            required = set(s.get("required", []))
            for key, prop in s["properties"].items():
                out += _doc(prop.get("description", ""), "  ")
                out.append("  " + _field(key, prop, key in required))
            out.append("}")
        else:
            out.append(f"export type {ts_name} = {_ts(s)}")
        out.append("")

    # API 경로 → 응답 타입. 화면이 경로 문자열로 응답 타입을 찾을 수 있게 한다.
    out += ["/** API 경로별 응답 타입. 키는 `메서드 경로` 다. 형식이 없는 API 는 싣지 않는다. */",
            "export interface ApiResponses {"]
    for path in sorted(spec["paths"]):
        for method, op in sorted(spec["paths"][path].items()):
            ok = next((r for c, r in op.get("responses", {}).items() if c.startswith("2")), None)
            schema = (ok or {}).get("content", {}).get("application/json", {}).get("schema")
            if not schema or schema == {}:
                continue
            out.append(f'  "{method.upper()} {path}": {_ts(schema)};')
    out += ["}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
