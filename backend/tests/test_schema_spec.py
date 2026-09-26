"""스키마 명세 문서가 코드와 같은가.

명세는 코드(app/schemas)에서 자동으로 만든다. 스키마를 바꾸고 문서를 다시
만들지 않으면 여기서 실패한다 — 문서와 코드가 어긋난 채 남지 않게 한다.
실제로 어제 손으로 쓴 문서가 코드와 두 군데 어긋나 있었다(6칸·면책 코드 7종).
"""
from app.schemas import spec


def test_스키마_명세_문서가_코드와_같다():
    on_disk = spec.DOC_PATH.read_text(encoding="utf-8")
    assert on_disk == spec.render(), (
        "docs/스키마_명세.md 가 코드와 다르다. "
        "backend 에서 `python -m app.schemas.spec` 로 다시 만든다")


def test_모든_스키마_파일이_명세에_실린다():
    """새 스키마 파일을 만들고 MODULE_ORDER 에 넣지 않으면 명세에서 빠진다."""
    import pkgutil
    import app.schemas as pkg
    infra = {"base", "column", "spec", "typescript"}
    files = {m.name for m in pkgutil.iter_modules(pkg.__path__)} - infra
    assert files == set(spec.MODULE_ORDER), f"명세에 빠진 스키마 파일: {files - set(spec.MODULE_ORDER)}"
