"""정답 위치 재배치 (STR-116).

[문제] 생성된 288문항의 정답이 1번에 69.8% 몰려 있었다(4번은 단 1개). 48편 중
17편은 6문항이 전부 같은 번호였다. 지문을 전혀 읽지 않고 1번만 찍어도 정답률
0.698 이 나오고, 독해 경계(G4_G6 P33=0.55)를 넘어 **'보통(mid)' 판정**을 받는다.
즉 독해를 잰 것이 아니라 위치 편향을 잰 셈이 된다.

LLM 이 '가장 적절한 답'을 먼저 쓰는 경향 때문이며, 생성 프롬프트가 위치 분산을
지시하지 않은 결과다. 프롬프트는 따로 고치고(generate_content.py), 이 스크립트는
**이미 만들어진 콘텐츠를 재생성 없이 살린다.**

[왜 재생성이 아니라 재배치인가]
문항 내용·정답·오답·해설은 문제가 없다. 잘못된 것은 정답이 놓인 자리뿐이다.
선지 순서만 바꾸면 되므로 API 비용도, 재검수 부담도 없다.

[결정성] 고정 시드를 쓴다. 같은 입력이면 같은 결과가 나와야 검수·재현이 가능하다.

[해설의 위치 언급] '1번이 정답이다', '①의 주장' 처럼 선지 번호를 가리키는 해설이
있다. 섞으면 틀린 말이 되므로 새 위치로 함께 갱신한다.

실행:
    python scripts/rebalance_answers.py --check                 # 현재 분포만 확인
    python scripts/rebalance_answers.py --write                 # 시드 JSON 재배치
    python scripts/rebalance_answers.py --write --apply-db      # DB 에도 반영
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv                                  # noqa: E402
load_dotenv(BACKEND_DIR / ".env")

SEED = 20260726          # 고정. 바꾸면 배치가 달라져 재현이 깨진다
N_CHOICES = 4
CIRCLED = {1: "①", 2: "②", 3: "③", 4: "④"}


def target_positions(n: int, rng: random.Random) -> list[int]:
    """지문 하나의 n개 문항에 줄 정답 위치. 4개 자리를 고르게 돌려쓴다.

    문항이 6개면 [1,2,3,4] + [1,2] 를 섞어 준다 — 한 지문 안에서 같은 번호가
    몰리지 않게 하는 것이 목적이다. 전역 분포는 이 결과의 합으로 자연히 고르게 된다.
    """
    pool: list[int] = []
    while len(pool) < n:
        block = list(range(1, N_CHOICES + 1))
        rng.shuffle(block)
        pool.extend(block)
    out = pool[:n]
    rng.shuffle(out)
    return out


def _retarget_text(txt: str, old: int, new: int) -> str:
    """해설 속 선지 번호 언급을 새 위치로 옮긴다. 기존 정답 번호만 건드린다."""
    if not txt or old == new:
        return txt
    txt = re.sub(rf"(?<![0-9]){old}\s*번", f"{new}번", txt)
    txt = txt.replace(CIRCLED[old], CIRCLED[new])
    return txt


def rebalance_item(item: dict, rng: random.Random) -> int:
    """지문 1편의 문항 정답 위치를 재배치. 바뀐 문항 수를 반환."""
    qs = item.get("questions", [])
    targets = target_positions(len(qs), rng)
    changed = 0

    for q, t in zip(qs, targets):
        old = q["answer_index"]
        if old == t:
            continue
        choices = list(q["choices"])
        # 정답과 목표 자리의 선지를 맞바꾼다. 선지 내용은 그대로 보존된다.
        choices[old - 1], choices[t - 1] = choices[t - 1], choices[old - 1]
        q["choices"] = choices
        q["answer_index"] = t
        q["explanation"] = _retarget_text(q.get("explanation", ""), old, t)
        q["evidence_text"] = _retarget_text(q.get("evidence_text", ""), old, t)
        changed += 1
    return changed


def report(items: list[dict], title: str) -> float:
    """정답 위치 분포와 '1번 찍기' 기대 정답률."""
    c = Counter(q["answer_index"] for i in items for q in i["questions"])
    total = sum(c.values())
    print(f"\n[{title}] 문항 {total}개")
    for k in range(1, N_CHOICES + 1):
        n = c[k]
        print(f"  {k}번 {n:>4}개 {n / total * 100:5.1f}%  {'█' * int(n / total * 60)}")
    same = sum(1 for i in items
               if i["questions"] and len({q["answer_index"] for q in i["questions"]}) == 1)
    print(f"  한 지문 전부 같은 번호: {same}편")
    guess = c[1] / total
    print(f"  '1번만 찍기' 기대 정답률: {guess:.3f}")
    return guess


async def apply_db(items: list[dict]) -> None:
    """DB 문항을 question_code 기준으로 갱신. 행을 지우지 않아 id·응답 이력이 보존된다."""
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal, engine
    from app.models.core import Question

    by_code = {q["question_code"]: q
               for i in items for q in i["questions"] if q.get("question_code")}
    if not by_code:
        # 시드 JSON 에는 question_code 가 없다(적재 시 부여). 지문 제목+문항 순서로 맞춘다.
        print("  [건너뜀] 시드에 question_code 가 없어 DB 매칭 불가 — 아래 경로를 쓰세요.")
        print("           python scripts/load_content.py --reset  (재적재)")
        await engine.dispose()
        return

    updated = 0
    async with AsyncSessionLocal() as db:
        for code, src in by_code.items():
            row = (await db.execute(
                select(Question).where(Question.question_code == code)
            )).scalar_one_or_none()
            if not row:
                continue
            row.choices = src["choices"]
            row.answer_index = src["answer_index"]
            row.explanation = src.get("explanation")
            row.evidence_text = src.get("evidence_text")
            updated += 1
        await db.commit()
    print(f"  DB 갱신: {updated}문항")
    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_all.json"))
    ap.add_argument("--check", action="store_true", help="분포만 확인")
    ap.add_argument("--write", action="store_true", help="재배치 결과를 파일에 저장")
    ap.add_argument("--apply-db", action="store_true", help="DB 문항도 갱신")
    args = ap.parse_args()

    path = Path(args.file)
    items = json.loads(path.read_text(encoding="utf-8"))

    before = report(items, "재배치 전")
    if args.check:
        return

    rng = random.Random(SEED)
    changed = sum(rebalance_item(i, rng) for i in items)
    after = report(items, "재배치 후")
    print(f"\n위치가 바뀐 문항: {changed}개 (시드 {SEED})")
    print(f"'1번 찍기' 정답률 {before:.3f} → {after:.3f}")

    if args.write:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"저장: {path}")
        if args.apply_db:
            asyncio.run(apply_db(items))
    else:
        print("(--write 를 붙여야 저장됩니다)")


if __name__ == "__main__":
    main()
