"""묵독 진단용 지문·문항 생성 스크립트 (모델 A — 일회성 시드 저작 도구).

Claude API로 G4_G6 묵독 진단용 지문 + 4지선다 문항(A5 사실 / A6 추론 / A7 비판)을
이은주(2026) 텍스트 7원칙 기반 프롬프트로 생성한다. 사용자용 기능이 아니라,
텍스트 풀을 한 번 채우기 위한 오프라인 저작 스크립트.

출력: scripts/generated/seed_content.json  (DB 적재는 별도 load 스크립트가 담당)
실행: (backend 디렉토리에서)  .venv\\Scripts\\python.exe scripts/generate_content.py --per-combo 1
"""
from __future__ import annotations
import os
import sys
import json
import argparse
import time
from pathlib import Path

# Windows 콘솔(cp949)에서 한글·em-dash 출력 깨짐/에러 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

from anthropic import Anthropic  # noqa: E402

# 생성 모델 (품질 우선). 실패 시 폴백.
MODEL_CANDIDATES = ["claude-sonnet-5", "claude-haiku-4-5-20251001"]

GENRES = ["narrative", "expository"]
DIFFICULTIES = ["easy", "normal", "hard"]

# 학년군별 대상·어휘 수준. 난도 가이드는 학년군마다 절대 길이가 달라야 한다
# (같은 'hard'라도 초등 고학년과 중1의 상한이 다름).
GRADE_SPECS = {
    "G4_G6": {
        "audience_ko": "초등 4~6학년",
        "expert_ko": "초등",
        "length_guide": {
            "easy":   "150~250자, 짧고 단순한 문장, 쉬운 일상 어휘, 구체적 내용",
            "normal": "250~400자, 중간 길이 문장, 학년 표준 어휘, 한두 개의 연결 관계",
            "hard":   "400~550자, 복문·수식 포함, 다소 추상적 어휘, 정보 밀도 높음",
        },
    },
    "G7": {
        "audience_ko": "중학교 1학년",
        "expert_ko": "중등",
        "length_guide": {
            "easy":   "250~400자, 평이한 문장, 중1 표준 어휘, 내용 전개가 명시적",
            "normal": "400~600자, 복문 포함, 중1 교과 수준 어휘, 두세 개의 논리 관계",
            "hard":   "600~800자, 추상적 개념어와 복합 논증, 정보 밀도 높음",
        },
    },
}

# B7 관심주제 태그 (시드용 최소 taxonomy — text_selection 관심매칭에 사용)
TOPIC_TAGS = {
    "narrative": ["ANIMAL", "FRIENDSHIP", "ADVENTURE", "FAMILY", "FANTASY"],
    "expository": ["SCIENCE", "NATURE", "SPACE", "HISTORY", "DAILY"],
}

GENRE_KO = {"narrative": "이야기글(서사)", "expository": "설명글(정보)"}
DIFF_KO = {"easy": "쉬움", "normal": "보통", "hard": "어려움"}

SYSTEM_TEMPLATE = (
    "당신은 한국 {expert_ko} 읽기 능력 진단 도구를 설계하는 국어교육 전문가입니다. "
    "{audience_ko} 학생의 묵독(소리 없이 읽기) 진단에 쓸 지문과 4지선다 문항을 만듭니다. "
    "반드시 이은주(2026)의 텍스트 선정 7원칙을 지킵니다: "
    "(1)특정 배경지식 없이도 읽을 수 있게, (2)특정 문화권 편향 배제, "
    "(3)요청 장르 충실, (4)학년 수준 어휘, (5)요청 길이 준수, "
    "(6)다른 지문과 독립적(자기완결), (7)성별·지역·특정 관심 편향 없이 중립적. "
    "문항은 사실적(A5)·추론적(A6)·비판적(A7) 이해를 정확히 구분해 측정합니다. "
    "출력은 오직 유효한 JSON 하나. 코드펜스·설명 없이 JSON만."
)

USER_TEMPLATE = """다음 조건으로 묵독 진단용 지문 1편과 문항 6개를 생성하세요.

- 대상: {audience_ko}
- 장르: {genre_ko}
- 난도: {diff_ko} — {length_guide}
- 관심주제 태그: {topic} (지문이 이 주제와 자연스럽게 관련되게)

문항 6개 구성(반드시 이 분포):
- A5 사실적 이해 2개: 지문에 명시된 정보(세부/주제/명시적 인과)를 묻는다.
- A6 추론적 이해 2개: 지문에 드러나지 않은 의도·함의·원인결과를 추론하게 한다.
- A7 비판적 이해 2개: 주장의 타당성, 사실과 의견 구분, 글의 적절성을 4지선다로 판단하게 한다.

각 문항: 4개 선택지, 정답 1개, 그럴듯한 오답 3개(명백히 틀리지 않게).
answer_index는 1-based(1~4). evidence_text는 정답 근거가 되는 지문 속 문장(비판문항은 판단 근거).

아래 JSON 스키마로만 출력:
{{
  "title": "지문 제목",
  "content": "지문 본문(줄바꿈은 \\n)",
  "text_structure": "chronological|compare_contrast|cause_effect|problem_solution 중 택1 또는 null",
  "questions": [
    {{"target_area":"A5","question_text":"...","choices":["선택지1","선택지2","선택지3","선택지4"],"answer_index":1,"evidence_text":"...","explanation":"정답 해설"}}
  ]
}}
questions 배열은 정확히 6개(A5 2, A6 2, A7 2 순서)."""


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        # 남은 선행 'json' 제거
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    return s.strip()


def _extract_json(s: str) -> str:
    """텍스트에서 최외곽 JSON 객체({...})만 추출. 앞뒤 설명/코드펜스 무시."""
    s = _strip_fence(s)
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end < start:
        return s
    return s[start:end + 1]


def count_syllables(text: str) -> int:
    return sum(1 for ch in text if "가" <= ch <= "힣")


def validate_item(item: dict) -> list[str]:
    errs = []
    for k in ("title", "content", "questions"):
        if not item.get(k):
            errs.append(f"missing {k}")
    qs = item.get("questions", [])
    if len(qs) != 6:
        errs.append(f"questions count={len(qs)} (expected 6)")
    areas = [q.get("target_area") for q in qs]
    for a in ("A5", "A6", "A7"):
        if areas.count(a) != 2:
            errs.append(f"area {a} count={areas.count(a)} (expected 2)")
    for i, q in enumerate(qs):
        ch = q.get("choices", [])
        if len(ch) != 4:
            errs.append(f"q{i} choices={len(ch)} (expected 4)")
        ai = q.get("answer_index")
        if not isinstance(ai, int) or not (1 <= ai <= 4):
            errs.append(f"q{i} answer_index={ai} (expected 1..4)")
        if not q.get("evidence_text"):
            errs.append(f"q{i} missing evidence_text")
    return errs


def generate_one(client: Anthropic, model: str, genre: str, difficulty: str, topic: str,
                 grade_group: str) -> dict:
    spec = GRADE_SPECS[grade_group]
    user = USER_TEMPLATE.format(
        audience_ko=spec["audience_ko"], genre_ko=GENRE_KO[genre], diff_ko=DIFF_KO[difficulty],
        length_guide=spec["length_guide"][difficulty], topic=topic,
    )
    system = SYSTEM_TEMPLATE.format(
        expert_ko=spec["expert_ko"], audience_ko=spec["audience_ko"],
    )
    resp = client.messages.create(
        model=model, max_tokens=12000, system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [getattr(b, "text", None) for b in resp.content if getattr(b, "type", None) == "text"]
    body = "".join(p for p in parts if p)
    if not body:
        raise ValueError(f"빈 응답 (stop_reason={getattr(resp,'stop_reason',None)}, blocks={[getattr(b,'type',None) for b in resp.content]})")
    data = json.loads(_extract_json(body))
    # 주입 메타
    data["grade_group"] = grade_group
    data["genre"] = genre
    data["difficulty_level"] = difficulty
    data["topic_tags"] = [topic]
    data["syllable_count"] = count_syllables(data.get("content", ""))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-combo", type=int, default=1, help="조합(장르×난도)당 지문 수")
    ap.add_argument("--grade-group", default="G4_G6", choices=sorted(GRADE_SPECS),
                    help="대상 학년군")
    ap.add_argument("--topic-offset", type=int, default=0,
                    help="주제 태그 시작 인덱스. 기존 지문과 같은 주제가 반복되지 않도록 이월분 생성 시 지정")
    ap.add_argument("--out", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_content.json"))
    args = ap.parse_args()

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY 없음 (.env 확인)")
        sys.exit(1)
    client = Anthropic(api_key=key)

    # 사용할 모델 확정 (첫 후보로 1회 테스트)
    model = None
    for m in MODEL_CANDIDATES:
        try:
            client.messages.create(model=m, max_tokens=5, messages=[{"role": "user", "content": "OK"}])
            model = m
            break
        except Exception as e:
            print(f"  model {m} 사용 불가: {type(e).__name__}")
    if not model:
        print("ERROR: 사용 가능한 모델 없음")
        sys.exit(1)
    print(f"[모델] {model}")

    print(f"[학년군] {args.grade_group} ({GRADE_SPECS[args.grade_group]['audience_ko']})")

    items = []
    combos = [(g, d) for g in GENRES for d in DIFFICULTIES]
    for gi, (genre, difficulty) in enumerate(combos):
        tags = TOPIC_TAGS[genre]
        for n in range(args.per_combo):
            topic = tags[(n + args.topic_offset) % len(tags)]
            label = f"{args.grade_group}/{genre}/{difficulty}/{topic}#{n+1}"
            for attempt in range(3):
                try:
                    item = generate_one(client, model, genre, difficulty, topic,
                                        args.grade_group)
                    errs = validate_item(item)
                    if errs:
                        print(f"  [검증실패] {label} (시도{attempt+1}): {errs[:3]}")
                        continue
                    items.append(item)
                    print(f"  [OK] {label} — {item['syllable_count']}음절, 문항6")
                    break
                except json.JSONDecodeError as e:
                    print(f"  [JSON오류] {label} (시도{attempt+1}): {str(e)[:80]}")
                except Exception as e:
                    print(f"  [API오류] {label} (시도{attempt+1}): {type(e).__name__}: {str(e)[:100]}")
                    time.sleep(2)
            else:
                print(f"  [포기] {label} — 3회 실패")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n생성 완료: {len(items)}편 → {out}")


if __name__ == "__main__":
    main()
