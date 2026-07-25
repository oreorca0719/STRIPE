"""오답 선지 재생성 (STR-116 B안).

[문제] 정답이 최장 선지인 문항이 74.2%, 정답 길이가 오답 평균의 1.40배였다.
글을 읽지 않고 가장 긴 것만 골라도 정답률 0.742 — 독해 경계(0.55)를 넘는다.
LLM 이 정답에는 근거를 충실히 쓰고 오답은 짧은 단정문으로 처리한 결과다.

[왜 오답만 바꾸는가] 지문·문항·정답은 멀쩡하다. 잘못된 것은 오답의 성의뿐이다.
전체 재생성하면 난도 지표(STR-105)와 검수(STR-81)를 다시 해야 하지만, 오답만
바꾸면 그 둘이 그대로 유효하다.

[정답 위치는 보존한다] 이미 재배치로 고르게 맞춰 놓았다(STR-116 위치 편향 교정).
새 오답을 기존 정답 자리를 피해 채워 넣어 분포를 깨지 않는다.

실행:
    python scripts/regenerate_distractors.py --dry-run       # 1편만 시험
    python scripts/regenerate_distractors.py                 # 전체
    python scripts/regenerate_distractors.py --only-biased   # 편향 문항만(권장)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv                                   # noqa: E402
load_dotenv(BACKEND_DIR / ".env")

from anthropic import Anthropic                                  # noqa: E402
from app.services.content import item_quality as Q               # noqa: E402

MODEL_CANDIDATES = ["claude-sonnet-5", "claude-haiku-4-5-20251001"]

# 정답 길이 대비 허용 범위. 이 밖이면 재시도한다.
LEN_MIN, LEN_MAX = 0.80, 1.20
MAX_ATTEMPTS = 3

SYSTEM = (
    "당신은 한국 초·중등 읽기 진단 문항을 다듬는 국어교육 전문가입니다. "
    "주어진 지문·문항·정답은 그대로 두고, **오답 선택지 3개만** 다시 씁니다. "
    "출력은 오직 유효한 JSON 하나. 코드펜스·설명 없이 JSON만."
)

USER_TEMPLATE = """아래 지문과 문항의 **오답 3개**를 다시 써 주세요.

[지문]
{content}

[문항]
{question}

[정답 — 이 선택지는 절대 바꾸지 마세요]
{answer}

요구사항:
1. **길이를 정답과 비슷하게.** 정답이 {alen}자이므로 각 오답도 {lo}~{hi}자로 쓰세요.
   지금 문제는 정답만 길고 자세해서, 글을 읽지 않아도 가장 긴 것을 고르면 맞는다는
   점입니다. 오답도 정답만큼 구체적으로, 근거를 담아 쓰세요.
2. **'~는 아니다', '전혀 관계없다' 같은 짧은 부정문을 쓰지 마세요.** 그런 선택지는
   읽지 않아도 걸러집니다.
3. **지문을 읽어야만 구분되게.** 지문 내용과 관련은 있으나 사실과 어긋나거나,
   범위를 지나치게 넓히거나, 인과를 뒤집은 형태가 좋습니다.
4. 정답과 의미가 같아지면 안 됩니다. 명백히 틀려야 하되 그럴듯해야 합니다.

출력 형식:
{{"distractors": ["오답1", "오답2", "오답3"]}}"""


def _extract_json(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    a, b = s.find("{"), s.rfind("}")
    return s[a:b + 1] if a != -1 and b != -1 else s


def is_biased(q: dict) -> bool:
    """이 문항이 길이 단서를 주는가."""
    return Q._longest_strategy_hit(q["choices"], q["answer_index"]) > 0.5


def validate(distractors, answer: str) -> list[str]:
    errs = []
    if not isinstance(distractors, list) or len(distractors) != 3:
        return [f"오답이 3개가 아님 ({len(distractors) if isinstance(distractors, list) else '?'})"]
    alen = len(answer)
    for i, d in enumerate(distractors):
        if not isinstance(d, str) or not d.strip():
            errs.append(f"오답{i} 비어 있음")
            continue
        if d.strip() == answer.strip():
            errs.append(f"오답{i} 가 정답과 동일")
        r = len(d) / alen if alen else 1
        if not (LEN_MIN <= r <= LEN_MAX):
            errs.append(f"오답{i} 길이비 {r:.2f} (허용 {LEN_MIN}~{LEN_MAX})")
    if len({d.strip() for d in distractors if isinstance(d, str)}) < 3:
        errs.append("오답끼리 중복")
    return errs


def regen_question(client: Anthropic, model: str, content: str, q: dict) -> bool:
    """오답 3개를 새로 받아 교체. 정답과 그 위치는 보존. 성공 여부 반환."""
    ai = q["answer_index"]
    answer = q["choices"][ai - 1]
    alen = len(answer)

    user = USER_TEMPLATE.format(
        content=content, question=q["question_text"], answer=answer,
        alen=alen, lo=int(alen * LEN_MIN), hi=int(alen * LEN_MAX),
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.messages.create(
                model=model, max_tokens=2000, system=SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            body = "".join(
                getattr(b, "text", "") or "" for b in resp.content
                if getattr(b, "type", None) == "text"
            )
            data = json.loads(_extract_json(body))
            ds = data.get("distractors", [])
            errs = validate(ds, answer)
            if errs:
                if attempt == MAX_ATTEMPTS - 1:
                    print(f"      [포기] {errs[:2]}")
                continue

            # 정답은 원래 자리에 두고 나머지 세 칸을 채운다 — 위치 분포를 깨지 않는다
            new_choices = [None] * 4
            new_choices[ai - 1] = answer
            it = iter(ds)
            for i in range(4):
                if new_choices[i] is None:
                    new_choices[i] = next(it).strip()
            q["choices"] = new_choices
            return True
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"      [API] {type(e).__name__}: {str(e)[:70]}")
            time.sleep(2)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_all.json"))
    ap.add_argument("--dry-run", action="store_true", help="첫 지문 1편만 처리하고 저장하지 않음")
    ap.add_argument("--only-biased", action="store_true",
                    help="길이 단서를 주는 문항만 재생성(비용 절감)")
    args = ap.parse_args()

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY 없음")
        sys.exit(1)
    client = Anthropic(api_key=key)

    model = None
    for m in MODEL_CANDIDATES:
        try:
            client.messages.create(model=m, max_tokens=5,
                                   messages=[{"role": "user", "content": "OK"}])
            model = m
            break
        except Exception as e:
            print(f"  model {m} 사용 불가: {type(e).__name__}")
    if not model:
        print("ERROR: 사용 가능한 모델 없음")
        sys.exit(1)
    print(f"[모델] {model}")

    path = Path(args.file)
    items = json.loads(path.read_text(encoding="utf-8"))
    print(Q.format_report(Q.analyze(items)))

    targets = items[:1] if args.dry_run else items
    done = failed = skipped = 0

    for ti, item in enumerate(targets, 1):
        qs = item["questions"]
        pick = [q for q in qs if (not args.only_biased) or is_biased(q)]
        skipped += len(qs) - len(pick)
        if not pick:
            continue
        print(f"[{ti}/{len(targets)}] {item['title']} — 문항 {len(pick)}개")
        for qi, q in enumerate(pick, 1):
            before = len(q["choices"][q["answer_index"] - 1]) / (
                mean([len(c) for i, c in enumerate(q["choices"])
                      if i != q["answer_index"] - 1]) or 1)
            ok = regen_question(client, model, item["content"], q)
            if ok:
                after = len(q["choices"][q["answer_index"] - 1]) / (
                    mean([len(c) for i, c in enumerate(q["choices"])
                          if i != q["answer_index"] - 1]) or 1)
                print(f"    {qi}. 길이비 {before:.2f} → {after:.2f}")
                if args.dry_run:
                    print(f"       Q. {q['question_text']}")
                    for ci, c in enumerate(q["choices"]):
                        mark = "★" if ci == q["answer_index"] - 1 else " "
                        print(f"       {mark}({len(c):>2}자) {c}")
                done += 1
            else:
                print(f"    {qi}. 실패 — 원본 유지")
                failed += 1

    print(f"\n재생성 {done} / 실패 {failed} / 건너뜀 {skipped}")
    print(Q.format_report(Q.analyze(items)))

    if args.dry_run:
        print("\n[dry-run] 저장하지 않았습니다.")
        return
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
