"""파일럿 데이터 수집·분석 (STR-80) — 관리자 전용.

임계값 확정(STR-15)은 분포를 봐야 가능한데 관리자 화면은 건별 조회만 된다.
여기서 내보내는 CSV 와 분포는 STR-15 에 그대로 투입할 산출물이다.

CSV 는 외부 도구에서 백분위(P33/P67)를 계산하기 위한 것이고,
분포·이상치·이탈 집계는 파일럿 진행 중 화면에서 바로 보기 위한 것이다.
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.core import (
    ComprehensionResult, DiagnosisRound, DiagnosisSession, DiagSessionStatus,
    FluencyResult, JudgmentResult, QuestionResponse,
    StudentProfile, TargetArea, TextContent,
)
from app.models.user import User
from app.services.diagnosis.judgment import A4_PLAUSIBLE_MAX, A4_PLAUSIBLE_MIN

router = APIRouter(dependencies=[Depends(require_admin)])


# ── 분포 구간 ────────────────────────────────────────────────────────────
# A4 는 타당성 범위(0.3~15.0)를 0.5 폭으로 나눈다. 범위 밖 값은 이상치로 따로 센다.
A4_BIN_WIDTH = 0.5
# 정답률은 0~100% 를 10% 폭으로.
ACC_BIN_COUNT = 10


def _bin_index(value: float, lo: float, width: float, count: int) -> int:
    idx = int((value - lo) / width)
    return max(0, min(count - 1, idx))


def _anon(user_id: int) -> str:
    """식별코드(elem5-017) 대신 쓰는 익명 라벨.

    실명을 수집하지 않아도 식별코드는 시스템 밖 매핑표와 결합하면 개인을 특정한다.
    외부 공유용 내보내기에서는 이 값으로 치환한다.
    """
    return f"S{user_id:05d}"


# ── CSV 내보내기 ─────────────────────────────────────────────────────────

@router.get("/export.csv")
async def export_csv(
    level: str = Query("session", pattern="^(session|round)$"),
    anonymize: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """진단 결과 CSV.

    level=session — 학생 1명당 1행. 임계값(P33/P67) 산출의 기본 단위다.
    level=round   — 회차별 1행. A4 는 회차마다 나오므로 분포를 더 촘촘히 볼 때 쓴다.

    anonymize=true 면 아이디를 익명 라벨로 치환한다. 기본값을 true 로 둔 이유는
    내보낸 파일이 메일·메신저로 옮겨 다니기 때문이다 — 식별이 필요한 경우에만 끄도록.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    if level == "session":
        rows = (await db.execute(
            select(DiagnosisSession, User, JudgmentResult, StudentProfile)
            .join(User, User.id == DiagnosisSession.student_id)
            .outerjoin(JudgmentResult,
                       JudgmentResult.diagnosis_session_id == DiagnosisSession.id)
            .outerjoin(StudentProfile, StudentProfile.id == DiagnosisSession.profile_id)
            .order_by(DiagnosisSession.id)
        )).all()

        writer.writerow([
            "session_id", "student", "grade", "status", "total_rounds",
            "fluency_a4", "fluency_level", "fluency_valid",
            "overall_accuracy", "comprehension_level", "total_correct", "total_questions",
            "label_5", "prescription_group", "matrix_position",
            "metacognition", "predicted_correct", "actual_10", "d2_gap",
            "reliability_flag", "reading_freq", "reading_attitude",
            "started_at", "completed_at",
        ])
        for s, u, j, p in rows:
            writer.writerow([
                s.id,
                _anon(u.id) if anonymize else u.username,
                p.grade if p else (u.grade.value if u.grade else None),
                s.status.value,
                s.total_rounds,
                j.fluency_value if j else None,
                j.fluency_level.value if j else None,
                j.fluency_valid if j else None,
                j.overall_accuracy if j else None,
                j.comprehension_level.value if j else None,
                j.total_correct if j else None,
                j.total_questions if j else None,
                j.label_5.value if j else None,
                j.prescription_group.value if j else None,
                j.matrix_position if j else None,
                j.metacognition.value if j and j.metacognition else None,
                p.predicted_correct if p else None,
                j.actual_10 if j else None,
                j.d2_gap if j else None,
                (j.reliability_flag if j else s.reliability_flag).value,
                p.reading_freq if p else None,
                p.reading_attitude if p else None,
                s.started_at.isoformat() if s.started_at else None,
                s.completed_at.isoformat() if s.completed_at else None,
            ])
    else:
        rows = (await db.execute(
            select(
                DiagnosisRound, DiagnosisSession, User,
                ComprehensionResult, FluencyResult, TextContent,
            )
            .join(DiagnosisSession, DiagnosisSession.id == DiagnosisRound.diagnosis_session_id)
            .join(User, User.id == DiagnosisSession.student_id)
            .outerjoin(ComprehensionResult, ComprehensionResult.round_id == DiagnosisRound.id)
            .outerjoin(FluencyResult, FluencyResult.round_id == DiagnosisRound.id)
            .outerjoin(TextContent, TextContent.id == DiagnosisRound.text_id)
            .order_by(DiagnosisRound.diagnosis_session_id, DiagnosisRound.round_number)
        )).all()

        writer.writerow([
            "round_id", "session_id", "student", "round_number",
            "text_code", "genre", "difficulty",
            "silent_reading_time", "total_syllables", "a4_syllable_per_sec",
            "total_questions", "correct_count", "round_accuracy", "betts_level",
            "a5_factual", "a6_inferential", "a7_critical",
            "started_at", "completed_at",
        ])
        for r, s, u, c, f, t in rows:
            writer.writerow([
                r.id, s.id,
                _anon(u.id) if anonymize else u.username,
                r.round_number,
                t.text_code if t else None,
                r.genre.value, r.difficulty_level.value,
                f.silent_reading_time if f else None,
                f.total_syllables if f else None,
                f.a4_syllable_per_sec if f else None,
                c.total_questions if c else None,
                c.correct_count if c else None,
                c.round_accuracy if c else None,
                c.betts_level.value if c and c.betts_level else None,
                c.a5_factual_accuracy if c else None,
                c.a6_inferential_accuracy if c else None,
                c.a7_critical_accuracy if c else None,
                r.started_at.isoformat() if r.started_at else None,
                r.completed_at.isoformat() if r.completed_at else None,
            ])

    buf.seek(0)
    tag = "anon" if anonymize else "ident"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="stripe_{level}_{tag}.csv"'},
    )


# ── 분포 ─────────────────────────────────────────────────────────────────

@router.get("/distributions")
async def get_distributions(db: AsyncSession = Depends(get_db)):
    """A4·정답률·영역별 정답률 분포. 임계값 조정의 근거가 되는 화면용 집계."""
    # A4 는 회차 단위로 나온다 — 세션당 여러 값이 있을 수 있어 회차에서 모은다.
    a4_values = [
        v for (v,) in (await db.execute(
            select(FluencyResult.a4_syllable_per_sec)
            .where(FluencyResult.a4_syllable_per_sec.isnot(None))
        )).all()
    ]
    a4_in_range = [v for v in a4_values if A4_PLAUSIBLE_MIN <= v <= A4_PLAUSIBLE_MAX]

    bin_count = int((A4_PLAUSIBLE_MAX - A4_PLAUSIBLE_MIN) / A4_BIN_WIDTH) + 1
    a4_bins = [0] * bin_count
    for v in a4_in_range:
        a4_bins[_bin_index(v, A4_PLAUSIBLE_MIN, A4_BIN_WIDTH, bin_count)] += 1

    # 세션 단위 종합 정답률 — 독해 경계값 산출의 기본 단위
    acc_values = [
        v for (v,) in (await db.execute(
            select(JudgmentResult.overall_accuracy)
            .where(JudgmentResult.overall_accuracy.isnot(None))
        )).all()
    ]
    acc_bins = [0] * ACC_BIN_COUNT
    for v in acc_values:
        acc_bins[_bin_index(v, 0.0, 1.0 / ACC_BIN_COUNT, ACC_BIN_COUNT)] += 1

    # 영역별(A5 사실 / A6 추론 / A7 비판) 정답률 — 문항 응답에서 직접 집계
    area_rows = (await db.execute(
        select(
            QuestionResponse.target_area,
            func.count(QuestionResponse.id),
            func.sum(cast(QuestionResponse.is_correct, Integer)),
        ).group_by(QuestionResponse.target_area)
    )).all()
    area_accuracy = {
        area.value: {
            "total": total,
            "correct": int(correct or 0),
            "accuracy": round(float(correct or 0) / total, 4) if total else None,
        }
        for area, total, correct in area_rows
    }
    for a in TargetArea:
        area_accuracy.setdefault(a.value, {"total": 0, "correct": 0, "accuracy": None})

    return {
        "a4": {
            "bin_width": A4_BIN_WIDTH,
            "range_min": A4_PLAUSIBLE_MIN,
            "range_max": A4_PLAUSIBLE_MAX,
            "bins": a4_bins,
            "in_range_count": len(a4_in_range),
            "out_of_range_count": len(a4_values) - len(a4_in_range),
            "percentiles": _percentiles(a4_in_range),
        },
        "accuracy": {
            "bin_count": ACC_BIN_COUNT,
            "bins": acc_bins,
            "count": len(acc_values),
            "percentiles": _percentiles(acc_values),
        },
        "area_accuracy": area_accuracy,
    }


def _percentiles(values: list) -> Optional[dict]:
    """P33/P67 을 바로 보여준다 — 이 두 값이 곧 판정 경계 후보(STR-15)다.

    표본이 적으면 값이 크게 흔들리므로 개수를 함께 내보내 판단 근거로 삼게 한다.
    """
    if not values:
        return None
    s = sorted(values)

    def pct(p: float) -> float:
        if len(s) == 1:
            return round(s[0], 3)
        pos = p * (len(s) - 1)
        lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 3)

    return {"n": len(s), "p33": pct(0.33), "p50": pct(0.50), "p67": pct(0.67),
            "min": round(s[0], 3), "max": round(s[-1], 3)}


# ── 측정 이상치 ──────────────────────────────────────────────────────────

@router.get("/outliers")
async def get_outliers(db: AsyncSession = Depends(get_db)):
    """A4 타당성 게이트(0.3~15.0)에 걸린 응시.

    게이트 범위는 잠정값이다. 너무 빡빡하면 정상 학생이 측정불가가 되고 너무
    느슨하면 미독·이탈이 걸러지지 않으므로, 조정하려면 걸린 응시를 하나씩 봐야 한다.
    """
    rows = (await db.execute(
        select(FluencyResult, DiagnosisRound, DiagnosisSession, User, TextContent)
        .join(DiagnosisSession, DiagnosisSession.id == FluencyResult.session_id)
        .join(User, User.id == DiagnosisSession.student_id)
        .outerjoin(DiagnosisRound, DiagnosisRound.id == FluencyResult.round_id)
        .outerjoin(TextContent, TextContent.id == DiagnosisRound.text_id)
        .where(FluencyResult.a4_syllable_per_sec.isnot(None))
        .where(
            (FluencyResult.a4_syllable_per_sec < A4_PLAUSIBLE_MIN)
            | (FluencyResult.a4_syllable_per_sec > A4_PLAUSIBLE_MAX)
        )
        .order_by(FluencyResult.a4_syllable_per_sec)
    )).all()

    return {
        "range_min": A4_PLAUSIBLE_MIN,
        "range_max": A4_PLAUSIBLE_MAX,
        "count": len(rows),
        "items": [
            {
                "fluency_id": f.id,
                "session_id": s.id,
                "student": u.username,
                "round_number": r.round_number if r else None,
                "text_code": t.text_code if t else None,
                "silent_reading_time": f.silent_reading_time,
                "total_syllables": f.total_syllables,
                "a4": f.a4_syllable_per_sec,
                "reason": "too_slow" if f.a4_syllable_per_sec < A4_PLAUSIBLE_MIN else "too_fast",
            }
            for f, r, s, u, t in rows
        ],
    }


# ── 중도이탈 ─────────────────────────────────────────────────────────────

@router.get("/dropoff")
async def get_dropoff(db: AsyncSession = Depends(get_db)):
    """어느 단계에서 응시를 그만두는지. 문항 수·소요시간 조정의 근거."""
    status_rows = (await db.execute(
        select(DiagnosisSession.status, func.count(DiagnosisSession.id))
        .group_by(DiagnosisSession.status)
    )).all()
    status_counts = {st.value: 0 for st in DiagSessionStatus}
    for st, c in status_rows:
        status_counts[st.value] = c

    # 미완료 세션이 몇 회차까지 갔는지 — 이탈 지점
    incomplete = (await db.execute(
        select(DiagnosisSession.id, func.count(DiagnosisRound.id))
        .outerjoin(DiagnosisRound,
                   DiagnosisRound.diagnosis_session_id == DiagnosisSession.id)
        .where(DiagnosisSession.status != DiagSessionStatus.completed)
        .group_by(DiagnosisSession.id)
    )).all()

    by_round: dict = {}
    for _sid, n in incomplete:
        by_round[n] = by_round.get(n, 0) + 1

    # 마지막 회차에서 어디까지 갔는지 — 읽기만 하고 그만뒀는지, 문항을 풀다 말았는지
    stage_rows = (await db.execute(
        select(DiagnosisRound.id, DiagnosisSession.status,
               func.count(QuestionResponse.id), func.count(FluencyResult.id))
        .join(DiagnosisSession, DiagnosisSession.id == DiagnosisRound.diagnosis_session_id)
        .outerjoin(QuestionResponse, QuestionResponse.round_id == DiagnosisRound.id)
        .outerjoin(FluencyResult, FluencyResult.round_id == DiagnosisRound.id)
        .where(DiagnosisSession.status != DiagSessionStatus.completed)
        .where(DiagnosisRound.completed_at.is_(None))
        .group_by(DiagnosisRound.id, DiagnosisSession.status)
    )).all()

    stages = {"before_reading": 0, "after_reading_no_answer": 0, "partial_answers": 0}
    for _rid, _st, n_resp, n_flu in stage_rows:
        if n_flu == 0:
            stages["before_reading"] += 1
        elif n_resp == 0:
            stages["after_reading_no_answer"] += 1
        else:
            stages["partial_answers"] += 1

    total = sum(status_counts.values())
    completed = status_counts.get(DiagSessionStatus.completed.value, 0)
    return {
        "status_counts": status_counts,
        "total_sessions": total,
        "completion_rate": round(completed / total, 4) if total else None,
        "incomplete_by_rounds_reached": by_round,
        "incomplete_last_round_stage": stages,
    }
