"""응원 문구 3축 조회 — DB 경로 검증 (STR-96). 실 Postgres 필요.

실행:
    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_report_tone_it.py -q

단위 테스트는 폴백 문구만 본다. 여기서는 '처방군 축이 실제로 조회에 걸리는가'를
확인한다 — 축이 하나 빠져도 단위 테스트는 통과하기 때문이다.
"""
import os
import asyncio
import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from sqlalchemy import text as sql_text

from app.core.database import AsyncSessionLocal, engine
from app.models.core import PrescriptionGroup, ReportRole, ReportTemplate, ToneCode
from app.services.diagnosis import report as R


def _tpl(group, tone, text, active=True):
    return ReportTemplate(
        template_code=R.encouragement_template_code(group, tone),
        condition_key=R.ENCOURAGEMENT_CONDITION_KEY,
        report_type=ReportRole.student,
        prescription_group=group.value if group else None,
        tone_variant=tone.value,
        template_text=text,
        is_active=active,
    )


async def _reset(*rows):
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("TRUNCATE report_templates RESTART IDENTITY CASCADE"))
        for r in rows:
            db.add(r)
        await db.commit()


def _run(coro_fn):
    async def go():
        try:
            return await coro_fn()
        finally:
            await engine.dispose()
    return asyncio.run(go())


def test_처방군마다_다른_문구가_나온다():
    """이게 STR-96 의 핵심이다. 같은 톤이라도 처방군이 다르면 문구가 갈려야 한다.
    G1(양호) 애독자에게는 난도 상향을 권해도 되지만, G4(독해집중) 애독자에게는
    안 된다 — 추천 지문이 난도를 낮추고 있기 때문이다."""
    async def go():
        await _reset(
            _tpl(PrescriptionGroup.G1, ToneCode.challenge, "G1 도전 문구"),
            _tpl(PrescriptionGroup.G4, ToneCode.challenge, "G4 도전 문구"),
        )
        async with AsyncSessionLocal() as db:
            t1, id1 = await R.resolve_encouragement(db, PrescriptionGroup.G1, ToneCode.challenge)
            t4, id4 = await R.resolve_encouragement(db, PrescriptionGroup.G4, ToneCode.challenge)
        assert t1 == "G1 도전 문구"
        assert t4 == "G4 도전 문구"
        assert id1 != id4
    _run(go)


def test_같은_처방군이라도_톤이_다르면_갈린다():
    async def go():
        await _reset(
            _tpl(PrescriptionGroup.G4, ToneCode.challenge, "G4 도전"),
            _tpl(PrescriptionGroup.G4, ToneCode.scaffold, "G4 발판"),
        )
        async with AsyncSessionLocal() as db:
            a, _ = await R.resolve_encouragement(db, PrescriptionGroup.G4, ToneCode.challenge)
            b, _ = await R.resolve_encouragement(db, PrescriptionGroup.G4, ToneCode.scaffold)
        assert (a, b) == ("G4 도전", "G4 발판")
    _run(go)


def test_다른_처방군_템플릿이_새지_않는다():
    """처방군 축이 빠지면 G1 문구가 G4 학생에게 나간다 — 원래 결함의 재현."""
    async def go():
        await _reset(_tpl(PrescriptionGroup.G1, ToneCode.challenge, "G1 전용"))
        async with AsyncSessionLocal() as db:
            text, tid = await R.resolve_encouragement(db, PrescriptionGroup.G4, ToneCode.challenge)
        assert text != "G1 전용"
        assert tid is None
        assert text == R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge]
    _run(go)


def test_템플릿이_없으면_난도_중립_폴백():
    """현재 상태. 템플릿 세트 제작 전까지는 항상 이 경로다."""
    async def go():
        await _reset()
        async with AsyncSessionLocal() as db:
            for group in PrescriptionGroup:
                for tone in ToneCode:
                    text, tid = await R.resolve_encouragement(db, group, tone)
                    assert tid is None
                    assert text == R.FALLBACK_ENCOURAGEMENT[tone]
                    for word in R._DIFFICULTY_WORDS:
                        assert word not in text, f"{group.value}/{tone.value}: {word}"
    _run(go)


def test_비활성_템플릿은_쓰이지_않는다():
    async def go():
        await _reset(_tpl(PrescriptionGroup.G4, ToneCode.challenge, "폐기된 문구", active=False))
        async with AsyncSessionLocal() as db:
            text, tid = await R.resolve_encouragement(db, PrescriptionGroup.G4, ToneCode.challenge)
        assert text == R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge]
        assert tid is None
    _run(go)
