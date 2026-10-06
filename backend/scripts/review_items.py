"""지문·문항 AI 2차 검수 (일회성 리포트 도구).

시드 파일의 지문마다 문항 6개를 모델에게 다시 풀게 하고 아래를 점검한다.
DB 는 건드리지 않는다. 결과는 사람(기획)이 검토할 리포트 JSON 이다.

  · 정답 일치    — 모델이 고른 답이 answer_index 와 같은가 (다르면 정답 오류 의심)
  · 복수 정답    — 정답으로도 볼 수 있는 오답이 있는가
  · 영역 분류    — A5 사실 / A6 추론 / A7 비판 분류가 맞는가
  · 지문 없이 풀림 — 글을 읽지 않아도 상식으로 맞힐 수 있는가
  · 학년 적합성·민감 표현

실행: python scripts/review_items.py --file scripts/generated/seed_all.json --out /tmp/review.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

from anthropic import Anthropic  # noqa: E402

MODEL_CANDIDATES = ["claude-sonnet-5-5", "claude-haiku-4-5-20251001"]

AUDIENCE = {"G4_G6": "초등 4~6학년", "G7": "중학교 1학년"}

SYSTEM = (
    "당신은 한국 초·중등 읽기 진단 문항을 검수하는 국어교육 전문가입니다. "
    "문항의 결함을 찾는 것이 목적이므로, 문제가 없으면 없다고 하고 있으면 구체적으로 지적합니다. "
    "출력은 오직 유효한 JSON 하나. 코드펜스·설명 없이 JSON만."
)

USER_TEMPLATE = """대상: {audience}
장르: {genre} / 난도: {difficulty}

[지문]
{content}

[문항]
{questions}

각 문항을 직접 풀고 아래 JSON으로만 답하세요. 문항 번호(no)는 위 순서대로 1~6.
{{
  "text": {{"grade_fit": "ok|too_easy|too_hard", "sensitive": "없음 또는 구체적 지적", "note": "지문 자체 문제(없으면 빈 문자열)"}},
  "questions": [
    {{"no": 1, "my_answer": 1, "multiple_correct": [다른 정답 가능 선지 번호들, 없으면 빈 배열],
      "area_ok": true, "area_suggest": "A5|A6|A7|null", "answerable_without_text": false,
      "issue": "문제점(없으면 빈 문자열)"}}
  ]
}}"""


def _extract_json(s: str) -> str:
    start, end = s.find("{"), s.rfind("}")
    return s[start:end + 1] if start != -1 and end > start else s


def fmt_questions(qs: list[dict]) -> str:
    lines = []
    for i, q in enumerate(qs, start=1):
        lines.append(f"{i}. [{q['target_area']}] {q['question_text']}")
        for j, c in enumerate(q["choices"], start=1):
            lines.append(f"   {j}) {c}")
    return "\n".join(lines)


def review_one(client: Anthropic, model: str, item: dict) -> dict:
    user = USER_TEMPLATE.format(
        audience=AUDIENCE.get(item.get("grade_group"), item.get("grade_group")),
        genre=item.get("genre"), difficulty=item.get("difficulty_level"),
        content=item["content"], questions=fmt_questions(item["questions"]),
    )
    resp = client.messages.create(model=model, max_tokens=4000, system=SYSTEM,
                                  messages=[{"role": "user", "content": user}])
    body = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
    data = json.loads(_extract_json(body))
    # 정답 대조는 모델에게 맡기지 않고 여기서 한다.
    for q, r in zip(item["questions"], data.get("questions", [])):
        r["answer_index"] = q["answer_index"]
        r["target_area"] = q["target_area"]
        r["answer_mismatch"] = r.get("my_answer") != q["answer_index"]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_all.json"))
    ap.add_argument("--out", default=str(BACKEND_DIR / "scripts" / "generated" / "review.json"))
    ap.add_argument("--passes", type=int, default=1, help="같은 지문을 몇 번 검수할지 (모델 판단의 흔들림 확인용)")
    args = ap.parse_args()

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        sys.exit("ERROR: ANTHROPIC_API_KEY 없음")
    client = Anthropic(api_key=key)
    model = None
    for m in MODEL_CANDIDATES:
        try:
            client.messages.create(model=m, max_tokens=5, messages=[{"role": "user", "content": "OK"}])
            model = m
            break
        except Exception as e:
            print(f"  model {m} 사용 불가: {type(e).__name__}")
    if not model:
        sys.exit("ERROR: 사용 가능한 모델 없음")
    print(f"[모델] {model}")

    items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    out = Path(args.out)
    results: list[dict] = []

    def save():
        out.write_text(json.dumps({"model": model, "source": Path(args.file).name, "results": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")

    stop = False
    for p in range(args.passes):
        for idx, item in enumerate(items):
            label = f"pass{p+1} #{idx+1} {item.get('title', '')[:20]}"
            for attempt in range(3):
                try:
                    r = review_one(client, model, item)
                    results.append({"pass": p + 1, "index": idx, "title": item.get("title"),
                                    "grade_group": item.get("grade_group"), "genre": item.get("genre"),
                                    "difficulty_level": item.get("difficulty_level"), **r})
                    save()
                    bad = sum(1 for q in r.get("questions", []) if q.get("answer_mismatch"))
                    print(f"  [OK] {label} — 정답 불일치 {bad}", flush=True)
                    break
                except json.JSONDecodeError as e:
                    print(f"  [JSON오류] {label} (시도{attempt+1}): {str(e)[:80]}")
                except Exception as e:
                    msg = str(e)
                    print(f"  [API오류] {label} (시도{attempt+1}): {type(e).__name__}: {msg[:100]}")
                    if "credit balance" in msg.lower():
                        stop = True
                        break
                    time.sleep(5)
            if stop:
                break
        if stop:
            print("[중단] API 잔액 소진")
            break

    save()
    print(f"\n검수 완료: {len(results)}건 → {out}")


if __name__ == "__main__":
    main()
