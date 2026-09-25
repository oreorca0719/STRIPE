"""화면 타입(frontend/src/api-types.ts)이 서버 형식과 같은가, 화면이 그 타입을 쓰는가.

[1] 타입 파일은 서버 형식에서 자동 생성한다. 서버 형식을 바꾸고 다시 만들지
    않으면 여기서 실패한다.
[2] 화면이 API 를 부를 때 응답 타입을 지정하지 않으면 실패한다. 타입 없이 부르면
    응답이 any 가 되어, 서버가 칸 이름을 바꿔도 화면은 컴파일되고 빈칸이 된다.
    2026-09-25 전에는 60곳 전부가 그랬다.
"""
import pathlib
import re

from app.contracts import typescript

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_화면_타입_파일이_서버_형식과_같다():
    assert typescript.OUT.read_text(encoding="utf-8") == typescript.render(), (
        "frontend/src/api-types.ts 가 서버 형식과 다르다. "
        "backend 에서 `python -m app.contracts.typescript` 로 다시 만든다")


_CALL = re.compile(r"\b(?:api|axios)\.(get|post|patch|put|delete)\s*(<)?")


def _calls():
    for p in sorted(FRONT.rglob("*")):
        if p.suffix not in (".ts", ".vue") or p.name == "api-types.ts":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CALL.finditer(line):
                yield p.relative_to(FRONT).as_posix(), i, m.group(2) is not None, line


def test_화면_API_호출이_있다():
    assert sum(1 for _ in _calls()) >= 50


# 서버에 아직 응답 형식이 없는 API (tests/test_api_contracts.ALLOWED_UNTYPED 와 같은 사유)
_ALLOWED_PATHS = ("/api/admin/pilot/export.csv", "/api/diagnosis/survey/definition",
                  "/api/parent/survey/definition")


def test_화면이_응답_타입_없이_API를_부르지_않는다():
    untyped = [f"{f}:{n}" for f, n, typed, line in _calls()
               if not typed and not any(p in line for p in _ALLOWED_PATHS)]
    assert not untyped, f"응답 타입 없이 부르는 곳 (api.get<타입>(...) 으로): {untyped}"
