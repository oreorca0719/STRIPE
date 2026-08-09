"""VAD 정확도 검증 — AI Hub 아동 음성 라벨의 SpeechStart/End 를 정답으로.

[왜 이것만 정량 검증이 가능한가]
이 데이터셋에는 미스큐 정답이 없다(ErrorTagged 전건 N/A, LabelText 는 대본).
그래서 '오류를 얼마나 잡나'는 잴 수 없다. 그런데 발화 구간은 라벨에
SpeechStart / SpeechEnd 로 들어 있다 — 21만 건 전부.

음독 B안에서 자동화하는 부분이 정확히 타이머다. 그게 아동 음성에서
믿을 만한지를 숫자로 답할 수 있는 유일한 경로다.

[무엇을 재는가]
  시작 오차   |VAD 시작 − 라벨 시작|
  끝 오차     |VAD 끝   − 라벨 끝|
  구간 오차   |VAD 발화시간 − 라벨 발화시간|   ← 소요시간에 직접 들어가는 값
  미검출률    발화를 아예 못 잡은 비율

구간 오차가 가장 중요하다. 자동성 = 정확 음절 ÷ 소요시간 이므로
소요시간 오차가 그대로 지표 오차가 된다.

실행:
    python validate_vad.py <원천 tar> <라벨 tar> [--n 300] [--model ...]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vad import SileroVad, load_wav_bytes          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def read_labels(tar_path: str, want: int) -> dict:
    """파일명(stem) → 라벨. 원천과 짝을 맞추려면 stem 이 키다."""
    out = {}
    with tarfile.open(tar_path, "r") as tf:
        for m in tf:
            if not (m.isfile() and m.name.endswith(".json")):
                continue
            try:
                d = json.load(tf.extractfile(m))
            except Exception:
                continue
            misc = d.get("Miscellaneous_Info", {})
            try:
                s = float(misc.get("SpeechStart"))
                e = float(misc.get("SpeechEnd"))
            except (TypeError, ValueError):
                continue
            sp = d.get("Speaker", {})
            out[Path(m.name).stem] = {
                "start": s, "end": e, "span": e - s,
                "year": sp.get("SchoolYear", "?"),
                "noise": d.get("Environment", {}).get("NoiseEnviron", "?"),
            }
            if len(out) >= want:
                break
    return out


def pct(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, int(len(s) * p / 100))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("labels")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--model", default=str(Path.home() / "Desktop" / "stt-lab" / "silero_vad.onnx"))
    ap.add_argument("--min-silence", type=int, default=300)
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    print(f"라벨 읽는 중… (최대 {args.n * 40:,}건 스캔)")
    labels = read_labels(args.labels, args.n * 40)
    print(f"라벨 {len(labels):,}건 확보\n")

    vad = SileroVad(args.model)
    d_start, d_end, d_span = [], [], []
    rel_span = []
    by_year = defaultdict(list)
    by_noise = defaultdict(list)
    missed = 0
    done = 0

    with tarfile.open(args.source, "r") as tf:
        for m in tf:
            if not (m.isfile() and m.name.endswith(".wav")):
                continue
            lab = labels.get(Path(m.name).stem)
            if lab is None:
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                audio = load_wav_bytes(f.read())
                r = vad.detect(audio, threshold=args.threshold,
                               min_silence_ms=args.min_silence)
            except Exception:
                continue

            done += 1
            if not r.segments:
                missed += 1
            else:
                d_start.append(abs(r.speech_start - lab["start"]))
                d_end.append(abs(r.speech_end - lab["end"]))
                err = abs(r.speech_span - lab["span"])
                d_span.append(err)
                if lab["span"] > 0:
                    rel = err / lab["span"] * 100
                    rel_span.append(rel)
                    by_year[lab["year"]].append(rel)
                    by_noise[lab["noise"]].append(rel)

            if done % 50 == 0:
                print(f"  {done}/{args.n} …", flush=True)
            if done >= args.n:
                break

    if not d_span:
        print("대조된 건이 없다. 원천과 라벨이 같은 구간인지 확인할 것.")
        return

    print("\n" + "=" * 62)
    print(f"VAD 정확도 — {done:,}건 (미검출 {missed}건, {missed/done*100:.1f}%)")
    print("=" * 62)
    print(f"  {'항목':10} {'중앙':>8} {'평균':>8} {'P90':>8} {'최대':>8}")
    for name, v in (("시작 오차", d_start), ("끝 오차", d_end), ("구간 오차", d_span)):
        print(f"  {name:10} {statistics.median(v):>7.3f}s {statistics.mean(v):>7.3f}s "
              f"{pct(v, 90):>7.3f}s {max(v):>7.3f}s")

    print(f"\n  구간 상대오차  중앙 {statistics.median(rel_span):.2f}% · "
          f"P90 {pct(rel_span, 90):.2f}%")
    within = sum(1 for e in d_span if e <= 0.5) / len(d_span) * 100
    print(f"  구간 오차 0.5초 이내: {within:.1f}%")

    print("\n  [학년별 상대오차 중앙]")
    for y in sorted(by_year):
        v = by_year[y]
        if len(v) >= 10:
            print(f"    {y:5} {statistics.median(v):>6.2f}%  (n={len(v)})")

    print("\n  [소음 조건별 상대오차 중앙]")
    for k in sorted(by_noise):
        v = by_noise[k]
        if len(v) >= 10:
            print(f"    {k:10} {statistics.median(v):>6.2f}%  (n={len(v)})")

    print("\n" + "=" * 62)
    print("해석")
    print("=" * 62)
    med = statistics.median(rel_span)
    if med < 5:
        print("  소요시간 오차가 5% 미만이다. 자동 타이머가 사람 대체 가능한 수준.")
    elif med < 10:
        print("  소요시간 오차가 5~10%. 쓸 수 있으나 임계값 설정 시 고려 필요.")
    else:
        print("  소요시간 오차가 10% 이상. 파라미터 조정 또는 다른 접근이 필요하다.")
    print("  ※ 자유발화 기준이다. 낭독은 호흡이 규칙적이라 더 낫게 나올 가능성이 높다.")


if __name__ == "__main__":
    main()
