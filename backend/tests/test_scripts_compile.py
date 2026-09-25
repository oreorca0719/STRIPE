"""앱 밖의 파이썬 파일(스크립트·마이그레이션)이 적어도 문법은 맞는가.

테스트는 app/ 만 불러온다. scripts/ 와 alembic/ 은 아무도 import 하지 않아서
문법 오류가 있어도 테스트가 통과한다. 실제로 지문 적재 스크립트가
(5c88be1 부터) 문자열 안의 줄바꿈 때문에 실행조차 되지 않았는데, 다음 날
직접 돌려 보기 전까지 몰랐다.
"""
import pathlib
import py_compile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = sorted([*ROOT.glob("scripts/*.py"), *ROOT.glob("alembic/versions/*.py")])


def test_검사할_파일이_있다():
    assert len(FILES) >= 20


@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_문법이_맞다(path, tmp_path):
    py_compile.compile(str(path), cfile=str(tmp_path / "x.pyc"), doraise=True)
