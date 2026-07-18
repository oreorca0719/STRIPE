"""생성 배치 여러 개를 하나의 시드 파일로 합친다.

generate_content.py 는 실행 1회당 파일 1개를 낸다(학년군·이월분마다 별도 실행).
적재는 load_content.py 가 단일 파일을 받으므로 여기서 병합한다.
text_code 는 load 단계에서 부여되므로 여기서는 (학년군, 장르, 난도, 제목) 중복만 거른다.

실행: .venv\\Scripts\\python.exe scripts/merge_seed.py out.json in1.json in2.json ...
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: merge_seed.py <out.json> <in.json> [in.json ...]")
        return 2

    out_path = Path(sys.argv[1])
    merged: list[dict] = []
    seen: set[tuple] = set()
    dropped = 0

    for src in sys.argv[2:]:
        p = Path(src)
        if not p.exists():
            print(f"  [건너뜀] {src} — 파일 없음")
            continue
        items = json.loads(p.read_text(encoding="utf-8"))
        added = 0
        for it in items:
            key = (it.get("grade_group"), it.get("genre"),
                   it.get("difficulty_level"), it.get("title"))
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            merged.append(it)
            added += 1
        print(f"  [병합] {p.name} — {added}편")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    combos = Counter((i["grade_group"], i["genre"], i["difficulty_level"]) for i in merged)
    print(f"\n합계 {len(merged)}편 (중복 제외 {dropped}편) → {out_path}")
    print("조합별 커버리지:")
    for (gg, genre, diff), n in sorted(combos.items()):
        print(f"  {gg:6} {genre:11} {diff:6} {n}편")
    qs = sum(len(i.get("questions", [])) for i in merged)
    print(f"문항 합계: {qs}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
