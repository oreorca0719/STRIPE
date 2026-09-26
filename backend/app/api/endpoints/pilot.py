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
from sqlalchemy import Integer, cast, func, select, true as sa_true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.schemas.pilot import (
    A4Distribution, AccuracyDistribution, AreaAccuracy, BettsCount, DifficultyRow,
    DifficultyValidity, DifficultyVerdict, Distributions, Dropoff, Duration,
    GradeGroupBetts, LastRoundStage, OutlierItem, Outliers, Percentiles, RoundsReached,
    StatusCount,
)
from app.core.database import get_db
from app.models.core import (
    FluencyType, Difficulty, GradeGroup,
    BettsLevel, ComprehensionResult, DiagnosisRound, DiagnosisSession, DiagSessionStatus,
    FluencyResult, JudgmentResult, QuestionResponse,
    StudentProfile, TargetArea, TextContent,
)
from app.enums import FINISHED_SESSION_STATUSES, OutlierReason
from app.models.user import User, UserRole
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


def _student_sessions():
    """분석 집계 대상 세션 — 학생 역할 계정의 응시만 (STR-107).

    관리자·교사 계정의 QA 응시가 섞이면 분포가 오염된다. 표본이 클 때는 묻히지만
    파일럿 초기 30~100건 규모에서는 몇 건만으로도 P33/P67 과 Betts 비율이 눈에
    띄게 흔들린다. 운영 중에도 내부 QA 는 계속할 것이므로 상시 제외한다.

    비활성 계정은 제외하지 않는다 — 응시를 마친 뒤 계정만 잠근 경우가 있고,
    그 데이터는 유효한 표본이다.
    """
    return DiagnosisSession.student_id.in_(
        select(User.id).where(User.role == UserRole.student)
    )


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
    students_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """진단 결과 CSV.

    level=session — 학생 1명당 1행. 임계값(P33/P67) 산출의 기본 단위다.
    level=round   — 회차별 1행. A4 는 회차마다 나오므로 분포를 더 촘촘히 볼 때 쓴다.

    anonymize=true 면 아이디를 익명 라벨로 치환한다. 기본값을 true 로 둔 이유는
    내보낸 파일이 메일·메신저로 옮겨 다니기 때문이다 — 식별이 필요한 경우에만 끄도록.

    students_only=true 는 관리자·교사 계정의 QA 응시를 제외한다(STR-107). 임계값
    산출용이 기본 용도이므로 true 를 기본값으로 둔다. 장애 재현처럼 전수가 필요할
    때만 끄도록.
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
            .where(_student_sessions() if students_only else sa_true())
            .order_by(DiagnosisSession.id)
        )).all()

        writer.writerow([
            # 학년은 두 곳에서 따로 정해진다 — 섞지 않고 두 열로 낸다.
            "session_id", "student", "survey_grade", "account_grade", "status", "round_count",
            "fluency_a4", "fluency_level", "fluency_valid",
            "overall_accuracy", "comprehension_level", "correct_count", "question_count",
            "label_5", "prescription_group", "matrix_position",
            "metacognition", "predicted_correct", "actual_correct_count_of_10", "metacognition_gap_count",
            "reliability_flag", "reading_freq", "reading_attitude",
            "started_at", "completed_at",
        ])
        for s, u, j, p in rows:
            writer.writerow([
                s.id,
                _anon(u.id) if anonymize else u.username,
                p.grade if p else None,
                u.grade.value if u.grade else None,
                s.status.value,
                s.round_count,
                j.fluency_value if j else None,
                j.fluency_level.value if j else None,
                j.fluency_valid if j else None,
                j.overall_accuracy if j else None,
                j.comprehension_level.value if j else None,
                j.correct_count if j else None,
                j.question_count if j else None,
                j.label_5.value if j else None,
                j.prescription_group.value if j else None,
                j.matrix_position if j else None,
                j.metacognition.value if j and j.metacognition else None,
                p.predicted_correct if p else None,
                j.actual_correct_count_of_10 if j else None,
                j.metacognition_gap_count if j else None,
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
            # 묵독 기록만 붙인다. 음독 기록까지 붙으면 한 회차가 두 줄이 된다.
            .outerjoin(FluencyResult, (FluencyResult.round_id == DiagnosisRound.id)
                       & (FluencyResult.type == FluencyType.silent))
            .outerjoin(TextContent, TextContent.id == DiagnosisRound.text_id)
            .where(_student_sessions() if students_only else sa_true())
            .order_by(DiagnosisRound.diagnosis_session_id, DiagnosisRound.round_number)
        )).all()

        writer.writerow([
            "round_id", "session_id", "student", "round_number",
            "text_code", "genre", "difficulty",
            "reading_time_ms", "text_syllable_count", "a4_syllable_per_sec",
            "question_count", "correct_count", "round_accuracy", "betts_level",
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
                f.reading_time_ms if f else None,
                # 음절 수는 지문의 사실이다 — 지문 테이블에서 읽는다(원칙 5).
                # 예전에는 묵독이 쓰지 않는 fluency_results.total_syllables 를 읽어 늘 비었다.
                t.syllable_count if t else None,
                f.a4_syllable_per_sec if f else None,
                c.question_count if c else None,
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

@router.get("/distributions", response_model=Distributions)
async def get_distributions(db: AsyncSession = Depends(get_db)):
    """A4·정답률·영역별 정답률 분포. 임계값 조정의 근거가 되는 화면용 집계."""
    # A4 는 회차 단위로 나온다 — 세션당 여러 값이 있을 수 있어 회차에서 모은다.
    a4_values = [
        v for (v,) in (await db.execute(
            select(FluencyResult.a4_syllable_per_sec)
            .join(DiagnosisSession, DiagnosisSession.id == FluencyResult.session_id)
            .where(FluencyResult.a4_syllable_per_sec.isnot(None), _student_sessions())
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
            .join(DiagnosisSession,
                  DiagnosisSession.id == JudgmentResult.diagnosis_session_id)
            .where(JudgmentResult.overall_accuracy.isnot(None), _student_sessions())
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
        )
        .join(DiagnosisRound, DiagnosisRound.id == QuestionResponse.round_id)
        .join(DiagnosisSession,
              DiagnosisSession.id == DiagnosisRound.diagnosis_session_id)
        .where(_student_sessions())
        .group_by(QuestionResponse.target_area)
    )).all()
    area_totals = {area: (int(correct or 0), total) for area, total, correct in area_rows}

    return Distributions(
        a4=A4Distribution(
            bin_width=A4_BIN_WIDTH,
            range_min=A4_PLAUSIBLE_MIN,
            range_max=A4_PLAUSIBLE_MAX,
            bin_counts=a4_bins,
            in_range_count=len(a4_in_range),
            out_of_range_count=len(a4_values) - len(a4_in_range),
            percentiles=_percentiles(a4_in_range),
        ),
        accuracy=AccuracyDistribution(
            bin_counts=acc_bins,
            session_count=len(acc_values),
            percentiles=_percentiles(acc_values),
        ),
        area_accuracy=[
            AreaAccuracy(
                area=a, correct_count=area_totals.get(a, (0, 0))[0],
                question_count=area_totals.get(a, (0, 0))[1],
                accuracy=(round(area_totals[a][0] / area_totals[a][1], 4)
                          if area_totals.get(a, (0, 0))[1] else None),
            )
            for a in TargetArea
        ],
    )


def _percentiles(values: list) -> Optional[Percentiles]:
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

    return Percentiles(sample_count=len(s), p33=pct(0.33), p50=pct(0.50), p67=pct(0.67),
                       min=round(s[0], 3), max=round(s[-1], 3))


# ── 측정 이상치 ──────────────────────────────────────────────────────────

@router.get("/outliers", response_model=Outliers)
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
        .where(FluencyResult.a4_syllable_per_sec.isnot(None), _student_sessions())
        .where(
            (FluencyResult.a4_syllable_per_sec < A4_PLAUSIBLE_MIN)
            | (FluencyResult.a4_syllable_per_sec > A4_PLAUSIBLE_MAX)
        )
        .order_by(FluencyResult.a4_syllable_per_sec)
    )).all()

    return Outliers(
        range_min=A4_PLAUSIBLE_MIN,
        range_max=A4_PLAUSIBLE_MAX,
        item_count=len(rows),
        items=[
            OutlierItem(
                fluency_id=f.id,
                session_id=s.id,
                student=u.username,
                round_number=r.round_number if r else None,
                text_code=t.text_code if t else None,
                reading_time_ms=f.reading_time_ms,
                text_syllable_count=t.syllable_count if t else None,
                a4_syllable_per_sec=f.a4_syllable_per_sec,
                reason=(OutlierReason.too_slow if f.a4_syllable_per_sec < A4_PLAUSIBLE_MIN
                        else OutlierReason.too_fast),
            )
            for f, r, s, u, t in rows
        ],
    )


# ── 중도이탈 ─────────────────────────────────────────────────────────────

@router.get("/dropoff", response_model=Dropoff)
async def get_dropoff(db: AsyncSession = Depends(get_db)):
    """어느 단계에서 응시를 그만두는지. 문항 수·소요시간 조정의 근거."""
    status_rows = (await db.execute(
        select(DiagnosisSession.status, func.count(DiagnosisSession.id))
        .where(_student_sessions())
        .group_by(DiagnosisSession.status)
    )).all()
    status_counts = {st: 0 for st in DiagSessionStatus}
    for st, c in status_rows:
        status_counts[st] = c

    # 미완료 세션이 몇 회차까지 갔는지 — 이탈 지점
    incomplete = (await db.execute(
        select(DiagnosisSession.id, func.count(DiagnosisRound.id))
        .outerjoin(DiagnosisRound,
                   DiagnosisRound.diagnosis_session_id == DiagnosisSession.id)
        .where(DiagnosisSession.status.notin_(FINISHED_SESSION_STATUSES), _student_sessions())
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
        .where(DiagnosisSession.status.notin_(FINISHED_SESSION_STATUSES), _student_sessions())
        .where(DiagnosisRound.completed_at.is_(None))
        .group_by(DiagnosisRound.id, DiagnosisSession.status)
    )).all()

    before = after_no_answer = partial = 0
    for _rid, _st, n_resp, n_flu in stage_rows:
        if n_flu == 0:
            before += 1
        elif n_resp == 0:
            after_no_answer += 1
        else:
            partial += 1

    total = sum(status_counts.values())
    # 조기종료·판정불가도 엔진이 정상적으로 끝낸 세션이다 — 이탈이 아니다.
    finished = sum(status_counts[st] for st in FINISHED_SESSION_STATUSES)
    return Dropoff(
        status_counts=[StatusCount(status=st, session_count=n) for st, n in status_counts.items()],
        session_count=total,
        completion_ratio=round(finished / total, 4) if total else None,
        incomplete_by_rounds_reached=[
            RoundsReached(rounds_reached_count=k, session_count=v) for k, v in sorted(by_round.items())
        ],
        incomplete_last_round_stage=LastRoundStage(
            before_reading_count=before,
            after_reading_no_answer_count=after_no_answer,
            partial_answers_count=partial,
        ),
    )


# ── 난도 라벨 타당성 ─────────────────────────────────────────────────────

@router.get("/difficulty-validity", response_model=DifficultyValidity)
async def get_difficulty_validity(db: AsyncSession = Depends(get_db)):
    """난도 라벨 × Betts 분포 — 라벨이 실제로 작동하는지 판정하는 근거 (STR-106).

    이 서비스의 목적은 순위 판별이 아니라 '이 수준이면 이런 책을 읽으면 좋겠다'를
    알려주는 것이다. 그렇다면 검증해야 할 것은 학생 판정 정밀도가 아니라
    **난도 라벨이 실제 읽기 부담과 대응하는가** 이다.

    Betts 는 그 대응을 재는 지표다(독립=혼자 읽을 수 있음 / 교수=도움 필요 /
    좌절=지금은 무리). 라벨이 제 역할을 한다면 easy 는 독립 쪽, hard 는 좌절 쪽으로
    분포가 기울어야 한다. 세 등급이 비슷하게 나오면 라벨이 읽기 부담을 가르지 못하는
    것이므로 STR-106 에서 재정의하거나 어휘 통제를 넣어야 한다.

    STR-105 에서 산출한 readability_score 와도 함께 본다. 지표는 갈리는데 Betts 가
    안 갈리면 우리 지표가 실제 부담을 못 잡는 것이고, 둘 다 갈리면 라벨을 유지해도
    된다는 근거가 된다.
    """
    rows = (await db.execute(
        select(
            TextContent.difficulty_level,
            TextContent.grade_group,
            ComprehensionResult.betts_level,
            ComprehensionResult.round_accuracy,
            TextContent.readability_score,
        )
        .join(DiagnosisRound, DiagnosisRound.text_id == TextContent.id)
        .join(ComprehensionResult, ComprehensionResult.round_id == DiagnosisRound.id)
        .join(DiagnosisSession,
              DiagnosisSession.id == DiagnosisRound.diagnosis_session_id)
        .where(ComprehensionResult.betts_level.isnot(None), _student_sessions())
    )).all()

    # 난도 × Betts 교차표. 각 난도에서 세 수준이 어떤 비율로 나오는지가 핵심.
    by_diff: dict = {}
    for diff, grade_group, betts, acc, score in rows:
        d = by_diff.setdefault(diff, {"betts": {b: 0 for b in BettsLevel}, "acc": [], "score": [],
                                      "gg": {}})
        d["betts"][betts] += 1
        if acc is not None:
            d["acc"].append(acc)
        if score is not None:
            d["score"].append(score)
        d["gg"].setdefault(grade_group, {b: 0 for b in BettsLevel})[betts] += 1

    def counts(c: dict) -> list:
        n = sum(c.values())
        return [BettsCount(betts_level=b, round_count=c[b],
                           ratio=round(c[b] / n, 4) if n else None) for b in BettsLevel]

    by_difficulty = [
        DifficultyRow(
            difficulty=diff,
            round_count=sum(d["betts"].values()),
            betts=counts(d["betts"]),
            mean_accuracy=round(sum(d["acc"]) / len(d["acc"]), 4) if d["acc"] else None,
            mean_readability_score=round(sum(d["score"]) / len(d["score"]), 2) if d["score"] else None,
            by_grade_group=[GradeGroupBetts(grade_group=g, betts=counts(d["gg"][g]))
                            for g in GradeGroup if g in d["gg"]],
        )
        for diff in Difficulty if (d := by_diff.get(diff))
    ]

    # 라벨이 기울어 있는가 — easy 는 독립 비율이, hard 는 좌절 비율이 높아야 한다.
    verdict = None
    if len(by_difficulty) >= 2:
        def ratio(row: DifficultyRow, level: BettsLevel) -> float:
            return next(b.ratio for b in row.betts if b.betts_level == level) or 0.0
        indep = [ratio(r, BettsLevel.independent) for r in by_difficulty]
        frust = [ratio(r, BettsLevel.frustration) for r in by_difficulty]
        # 단조 감소(독립)·단조 증가(좌절)를 기대한다
        indep_ok = all(indep[i] >= indep[i + 1] for i in range(len(indep) - 1))
        frust_ok = all(frust[i] <= frust[i + 1] for i in range(len(frust) - 1))
        verdict = DifficultyVerdict(
            independent_decreasing=indep_ok,
            frustration_increasing=frust_ok,
            label_works=indep_ok and frust_ok,
            note=("난도 라벨이 읽기 부담과 대응한다" if indep_ok and frust_ok
                  else "라벨과 실제 부담이 어긋난다 — STR-106 검토 필요"),
        )

    round_count = sum(r.round_count for r in by_difficulty)
    return DifficultyValidity(
        round_count=round_count,
        # 표본이 적으면 판정을 신뢰할 수 없다. 화면에서 경고를 띄우기 위한 값.
        sufficient_sample=round_count >= 30,
        by_difficulty=by_difficulty,
        verdict=verdict,
    )


# ── 소요시간 ─────────────────────────────────────────────────────────────

@router.get("/duration", response_model=Duration)
async def get_duration(db: AsyncSession = Depends(get_db)):
    """1회 진단 소요시간 분포 (STR-112).

    보호자 동의서에 '20~30분'이라고 적었는데 측정한 값이 아니라 구조에서 추정한
    수치였다. 보호자에게 제시하는 문서에 근거 없는 숫자가 들어가 있어서는 안 된다.
    도메인 문서 미해결 공백 #6(1회 진단 소요 시간 목표)도 이 값으로 채운다.

    두 가지를 함께 낸다.
    - 세션 총 소요: started_at ~ completed_at. 실제 학생이 앉아 있는 시간
    - 읽기·응답 합: 실제 과업에 쓴 시간. 총 소요와의 차이가 곧 '멈칫한 시간'이다

    완료된 세션만 센다. 중단 세션의 소요시간은 이탈 지점 분석(dropoff)의 몫이다.
    """
    DONE = FINISHED_SESSION_STATUSES

    rows = (await db.execute(
        select(DiagnosisSession.id, DiagnosisSession.started_at,
               DiagnosisSession.completed_at)
        .where(DiagnosisSession.status.in_(DONE),
               DiagnosisSession.completed_at.isnot(None),
               _student_sessions())
    )).all()

    total_minutes = [
        round((c - s).total_seconds() / 60.0, 2)
        for _sid, s, c in rows if s and c
    ]

    # 묵독 시간 — 세션 단위 합. 완료 세션만.
    done_ids = [sid for sid, _s, _c in rows]
    reading_rows = (await db.execute(
        select(DiagnosisSession.id, func.sum(FluencyResult.reading_time_ms))
        .join(DiagnosisRound, DiagnosisRound.diagnosis_session_id == DiagnosisSession.id)
        .join(FluencyResult, (FluencyResult.round_id == DiagnosisRound.id)
              & (FluencyResult.type == FluencyType.silent))
        .where(DiagnosisSession.id.in_(done_ids))
        .group_by(DiagnosisSession.id)
    )).all() if done_ids else []
    reading_minutes = [round(ms / 60000.0, 2) for _sid, ms in reading_rows]

    # 문항 응답 시간은 화면이 보내지 않는다(response_time_ms 가 늘 null). 예전에는
    # null 을 0 으로 더해 '과업 시간'이라 불렀다 — 실제로는 묵독 시간뿐이었다.
    # 잰 건수를 그대로 알린다.
    measured = (await db.execute(
        select(func.count(QuestionResponse.id))
        .join(DiagnosisRound, DiagnosisRound.id == QuestionResponse.round_id)
        .where(DiagnosisRound.diagnosis_session_id.in_(done_ids),
               QuestionResponse.response_time_ms.isnot(None))
    )).scalar_one() if done_ids else 0

    return Duration(
        session_count=len(total_minutes),
        # 표본이 적으면 이 값으로 동의서 문구를 확정하지 말 것
        sufficient_sample=len(total_minutes) >= 20,
        total_minutes=_percentiles(total_minutes),
        reading_minutes=_percentiles(reading_minutes),
        answer_time_measured_count=measured,
    )
