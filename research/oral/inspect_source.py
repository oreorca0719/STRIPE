"""원천 데이터 구조 확인 + LabelText 정체 판별 (음독 Phase 1).

[이 스크립트가 답하려는 것]
라벨 JSON 의 Transcription.LabelText 가
  · 아이가 읽어야 했던 **대본**인가
  · 아이가 실제로 읽은 것의 **전사**인가

이 답에 따라 AI Hub 데이터의 쓸모가 갈린다.
  대본이면 → 미스큐 정답 없음. STT 인식률만 잴 수 있다
  전사면  → 대본과 diff 하면 미스큐 정답이 나온다. 오류 분류 벤치마크가 가능해진다

ErrorTagged 가 전건 N/A 라 전자일 가능성이 높으나, 원천 안에 대본 txt 가
따로 있다면 대조해서 확정할 수 있다. 완전히 일치하면 대본, 어긋나면 전사다.

실행:
    python inspect_source.py <원천 tar 또는 폴더> [--labels <라벨 tar>]
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def scan_archive(path: Path, limit: int = 400_000) -> tuple[Counter, list[str]]:
    """확장자 분포와 앞부분 항목 목록. 풀지 않고 훑는다."""
    ext = Counter()
    names: list[str] = []
    if path.is_dir():
        for i, p in enumerate(path.rglob("*")):
            if p.is_file():
                ext[p.suffix.lower()] += 1
                if len(names) < 40:
                    names.append(str(p.relative_to(path)))
            if i > limit:
                break
        return ext, names

    with tarfile.open(path, "r") as tf:
        for i, m in enumerate(tf):
            if m.isfile():
                ext[Path(m.name).suffix.lower()] += 1
                if len(names) < 40:
                    names.append(m.name)
            if i > limit:
                break
    return ext, names


def read_members(path: Path, suffixes: tuple[str, ...], want: int) -> dict[str, bytes]:
    """확장자별로 앞에서 want 개씩 꺼낸다."""
    out: dict[str, bytes] = {}
    need = Counter()
    if path.is_dir():
        for p in path.rglob("*"):
            s = p.suffix.lower()
            if p.is_file() and s in suffixes and need[s] < want:
                out[str(p.relative_to(path))] = p.read_bytes()
                need[s] += 1
            if all(need[s] >= want for s in suffixes):
                break
        return out

    with tarfile.open(path, "r") as tf:
        for m in tf:
            s = Path(m.name).suffix.lower()
            if m.isfile() and s in suffixes and need[s] < want:
                f = tf.extractfile(m)
                if f:
                    out[m.name] = f.read()
                    need[s] += 1
            if all(need[s] >= want for s in suffixes):
                break
    return out


def syllables(text: str) -> int:
    return sum(1 for ch in text if "가" <= ch <= "힣")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="원천 데이터 tar 또는 압축 푼 폴더")
    ap.add_argument("--labels", help="같은 구간의 라벨 tar (LabelText 대조용)")
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()

    src = Path(args.source)
    print("=" * 66)
    print("① 원천 데이터 구성")
    print("=" * 66)
    ext, names = scan_archive(src)
    for e, c in ext.most_common():
        print(f"  {e or '(확장자 없음)':16} {c:>10,}")
    print("\n  [앞부분 항목]")
    for n in names[:12]:
        print(f"   {n}")

    # 대본으로 보이는 텍스트 파일이 있는가
    text_exts = tuple(e for e in ext if e in (".txt", ".json", ".csv", ".tsv"))
    print()
    print("=" * 66)
    print("② 대본(script) 후보 파일")
    print("=" * 66)
    if not text_exts or set(text_exts) == {".json"}:
        print("  원천에 별도 대본 파일이 보이지 않는다.")
        print("  → 대본이 없다면 LabelText 만이 유일한 텍스트다. 그 경우")
        print("    '읽어야 했던 것'과 '읽은 것'을 구분할 방법이 데이터 안에 없다.")
    else:
        got = read_members(src, text_exts, args.samples)
        for name, raw in list(got.items())[: args.samples]:
            try:
                body = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                body = raw.decode("cp949", errors="replace").strip()
            print(f"\n  ── {name}")
            print("  " + body[:300].replace("\n", "\n  "))

    if not args.labels:
        print("\n(--labels 를 주면 LabelText 와 대조한다)")
        return

    print()
    print("=" * 66)
    print("③ LabelText ↔ 대본 대조 — 이게 핵심")
    print("=" * 66)
    lab = read_members(Path(args.labels), (".json",), 200)
    texts = {}
    for name, raw in lab.items():
        try:
            d = json.loads(raw)
        except Exception:
            continue
        stem = Path(name).stem
        texts[stem] = d.get("Transcription", {}).get("LabelText", "")

    scripts = {Path(n).stem: r for n, r in read_members(src, (".txt",), 200).items()}
    common = sorted(set(texts) & set(scripts))
    if not common:
        print("  같은 이름의 대본 파일을 찾지 못했다. 파일명 규칙을 눈으로 확인할 것.")
        print(f"  라벨 예: {list(texts)[:3]}")
        print(f"  원천 예: {list(scripts)[:3]}")
        return

    same = diff = 0
    for stem in common[:200]:
        try:
            s = scripts[stem].decode("utf-8").strip()
        except UnicodeDecodeError:
            s = scripts[stem].decode("cp949", errors="replace").strip()
        t = (texts[stem] or "").strip()
        if s == t:
            same += 1
        else:
            diff += 1
            if diff <= 5:
                print(f"\n  ── {stem}")
                print(f"     대본     : {s[:90]}")
                print(f"     LabelText: {t[:90]}")

    tot = same + diff
    print(f"\n  대조 {tot}건 — 일치 {same} / 불일치 {diff}")
    if tot and diff / tot < 0.02:
        print("  ▶ 사실상 전건 일치. LabelText 는 **대본**이다.")
        print("    미스큐 정답은 이 데이터에 없다. STT 인식률 측정까지만 가능하다.")
    else:
        print("  ▶ 어긋나는 건이 있다. LabelText 는 **실제 전사**일 가능성이 높다.")
        print("    대본과 diff 하면 미스큐 정답을 만들 수 있다 — 데이터 가치가 크게 오른다.")


if __name__ == "__main__":
    main()
