"""테스트용 형식 객체 생성기.

테스트가 운영에서 나올 수 없는 모양(3칸짜리 dict 등)을 넣지 않도록, 형식을
통과하는 객체만 만든다. 적지 않은 칸은 문항 0개(측정 안 함)로 채운다.
"""
from app.contracts.judgment import CELL_ORDER, WeaknessCell, WeaknessProfile


def profile(**cells) -> WeaknessProfile:
    """profile(A5_narrative=(정답 수, 문항 수), ...) → 6칸 약점 프로필."""
    for key in cells:
        area, genre = key.split("_", 1)
        if (area, genre) not in [(a.value, g.value) for a, g in CELL_ORDER]:
            raise KeyError(f"없는 칸: {key}")
    out = []
    for area, genre in CELL_ORDER:
        correct, total = cells.get(f"{area.value}_{genre.value}", (0, 0))
        out.append(WeaknessCell(area=area, genre=genre, correct_count=correct, question_count=total))
    return WeaknessProfile(cells=out)
