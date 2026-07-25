"""지문 난도 지표 백필 + 라벨 검증 리포트 (STR-103).

texts 의 난도 판단 근거 컬럼을 채우고, 현재 easy/normal/hard 라벨이 실제로
무엇을 가르고 있는지 보고한다. 추천의 축이 난도인 이상(§5-1) 그 축의 의미를
데이터로 확인해야 한다.

실행:
    .venv\\Scripts\\python.exe scripts/analyze_texts.py            # 리포트만
    .venv\\Scripts\\python.exe scripts/analyze_texts.py --write    # DB 갱신 포함
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from statistics import mean, stdev

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv                                  # noqa: E402
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select                                   # noqa: E402
from app.core.database import AsyncSessionLocal, engine         # noqa: E402
from app.models.core import TextContent                         # noqa: E402
from app.services.content.readability import analyze            # noqa: E402

DIFFS = ("easy", "normal", "hard")
ORDER = {d: i for i, d in enumerate(DIFFS)}


def _fmt(v, w=6, p=2):
    return f"{v:>{w}.{p}f}"


def report(rows) -> None:
    """rows: [(grade_group, difficulty, TextMetrics, title)]"""
    for gg in sorted({r[0] for r in rows}):
        sub = [r for r in rows if r[0] == gg]
        print(f"\n{'='*76}\n{gg}  ({len(sub)}편)\n{'='*76}")
        print(f"{'난도':<8}{'편수':>4}{'음절':>10}{'문장당어절':>12}"
              f"{'어절당음절':>12}{'긴어절%':>9}{'절밀도':>8}{'종합':>8}")
        for d in DIFFS:
            g = [r[2] for r in sub if r[1] == d]
            if not g:
                continue
            m = lambda f: mean([f(x) for x in g])                # noqa: E731
            print(f"{d:<8}{len(g):>4}{m(lambda x: x.syllable_count):>10.0f}"
                  f"{m(lambda x: x.avg_sentence_words):>12.2f}"
                  f"{m(lambda x: x.avg_word_syllables):>12.2f}"
                  f"{m(lambda x: x.long_word_ratio) * 100:>9.1f}"
                  f"{m(lambda x: x.clause_density):>8.2f}"
                  f"{m(lambda x: x.readability_score):>8.1f}")

        # 인접 난도 간 범위 겹침 — 겹치면 어떤 easy 가 어떤 normal 보다 어렵다는 뜻
        print("\n  [종합점수 범위 · 겹침]")
        prev = None
        for d in DIFFS:
            g = [r[2].readability_score for r in sub if r[1] == d]
            if not g:
                continue
            lo, hi = min(g), max(g)
            note = "" if prev is None or lo > prev else f"   ← 앞 등급 최대({prev:.1f})와 겹침"
            print(f"    {d:<7}{lo:6.1f} ~{hi:6.1f}{note}")
            prev = hi

        # 라벨 순서와 지표 순위의 일치도
        pairs = conc = 0
        for i in range(len(sub)):
            for j in range(i + 1, len(sub)):
                a, b = sub[i], sub[j]
                if ORDER[a[1]] == ORDER[b[1]]:
                    continue
                pairs += 1
                if (ORDER[a[1]] < ORDER[b[1]]) == (a[2].readability_score < b[2].readability_score):
                    conc += 1
        if pairs:
            print(f"\n  [라벨 순서 일치] {conc}/{pairs} = {conc / pairs * 100:.1f}%")

        # 어휘 등급이 난도와 무관하게 섞여 있는지
        print("  [어휘 대리등급 분포]")
        for d in DIFFS:
            g = [r[2].vocabulary_level for r in sub if r[1] == d]
            if g:
                c = {k: g.count(k) for k in ("basic", "intermediate", "advanced") if g.count(k)}
                print(f"    {d:<7}{c}")


async def run(write: bool) -> None:
    async with AsyncSessionLocal() as db:
        texts = (await db.execute(select(TextContent).order_by(TextContent.id))).scalars().all()
        if not texts:
            print("텍스트가 없습니다.")
            return

        rows = []
        for t in texts:
            m = analyze(t.content or "")
            rows.append((t.grade_group.value, t.difficulty_level.value, m, t.title))
            if write:
                t.sentence_complexity = m.avg_sentence_words
                t.vocabulary_level = m.vocabulary_level
                t.readability_score = m.readability_score
                t.readability_metrics = m.as_dict()
                # kread_index 는 건드리지 않는다 — 외부 지수

        if write:
            await db.commit()
            print(f"[갱신] {len(texts)}편의 난도 지표 저장 (kread_index 는 NULL 유지)")
        else:
            print(f"[리포트 전용] {len(texts)}편 분석 — 저장하려면 --write")

        report(rows)

    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="산출 결과를 DB에 저장")
    args = ap.parse_args()
    asyncio.run(run(args.write))


if __name__ == "__main__":
    main()
