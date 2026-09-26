"""schema-first 배포 전 운영 DB 정리 — PM 승인(2026-09-26)된 두 가지만 한다.

1. 진단 결과 8개 테이블을 비운다. 옛 모양의 JSONB 라 새 코드가 읽는 순간 실패한다.
2. student_profiles.interest_topics 가 새 스키마(TopicCodes)를 통과하지 못하는 행만
   NULL 로 비운다(1안). 설문 C-1 을 다시 받게 된다.

[안전장치]
    · 한 트랜잭션. 정리 후 precheck_schema_first 의 점검을 같은 트랜잭션 안에서 다시
      돌려, 하나라도 남으면 롤백한다.
    · 리비전이 015 가 아니면 멈춘다.
    · interest_topics 를 비울 행 id 를 --expect-profile-ids 로 받는다. 실제로 걸리는
      행이 그와 다르면 아무것도 하지 않는다 — 점검 뒤에 데이터가 바뀌었다는 뜻이다.
      두 번 돌려도 두 번째는 걸리는 행이 없어 여기서 멈춘다.
    · --confirm 이 없으면 끝에서 롤백한다(dry-run).

[실행]
    DATABASE_URL=... python scripts/apply_schema_first_cleanup.py --expect-profile-ids 9,10,14
    DATABASE_URL=... python scripts/apply_schema_first_cleanup.py --expect-profile-ids 9,10,14 --confirm
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import precheck_schema_first as pc  # 같은 폴더. sys.path·모델 로드도 여기서 한다

from app.core.config import settings  # noqa: E402
from app.models.core import StudentProfile  # noqa: E402

# 참조 순서: 자식 → 부모. TRUNCATE 는 CASCADE 없이 한 문장으로 — 이 8개 밖의 테이블이
# 참조하고 있으면 Postgres 가 거부한다(모르는 테이블까지 지우지 않는다).
DIAGNOSIS_TABLES_ORDERED = [
    "reports", "prescription_results", "judgment_results", "question_responses",
    "comprehension_results", "fluency_results", "diagnosis_rounds", "diagnosis_sessions",
]
assert set(DIAGNOSIS_TABLES_ORDERED) == pc.DIAGNOSIS_TABLES


async def _bad_interest_topic_ids(conn) -> set[int]:
    adapter = StudentProfile.__table__.c.interest_topics.type._adapter
    bad = set()
    for r in await conn.execute(text(
            "SELECT id, interest_topics FROM student_profiles WHERE interest_topics IS NOT NULL")):
        try:
            adapter.validate_python(r.interest_topics)
        except ValidationError:
            bad.add(r.id)
    return bad


async def run(expect_ids: set[int], confirm: bool) -> int:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            if revision != pc.EXPECTED_REVISION:
                print(f"[중단] 리비전 {revision} — {pc.EXPECTED_REVISION} 이 아니다")
                await trans.rollback()
                return 3

            bad = await _bad_interest_topic_ids(conn)
            if bad != expect_ids:
                print(f"[중단] interest_topics 불량 행이 예상과 다르다: 실제 {sorted(bad)} · 예상 {sorted(expect_ids)}")
                await trans.rollback()
                return 4

            before = {t: (await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar()
                      for t in DIAGNOSIS_TABLES_ORDERED}
            print("비우기 전 행 수:", before)

            await conn.execute(text(f"TRUNCATE {', '.join(DIAGNOSIS_TABLES_ORDERED)}"))
            n = (await conn.execute(text(
                "UPDATE student_profiles SET interest_topics = NULL WHERE id = ANY(:ids)"),
                {"ids": sorted(expect_ids)})).rowcount
            print(f"interest_topics NULL 처리: {n}행 (id {sorted(expect_ids)})")

            findings = await pc.migration_checks(conn) + await pc.jsonb_checks(conn)
            remaining = [f for f in findings if f.bad_rows]
            passed = f"{len(findings)}/{len(findings)}"
            if remaining:
                print("[롤백] 정리 후에도 남은 항목:")
                for f in remaining:
                    print(f"  ✗ {f.migration} {f.table}.{f.check} — {f.bad_rows}")
                await trans.rollback()
                return 5

            if not confirm:
                print(f"[dry-run] 정리 후 점검 {passed} 통과. --confirm 이 없어 롤백한다.")
                await trans.rollback()
                return 0
            await trans.commit()
            print(f"[적용] 정리 후 점검 {passed} 통과. 커밋했다.")
            return 0
    finally:
        await engine.dispose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--expect-profile-ids", required=True,
                    help="interest_topics 를 비울 student_profiles.id, 콤마 구분")
    ap.add_argument("--confirm", action="store_true", help="커밋한다. 없으면 dry-run")
    args = ap.parse_args()
    ids = {int(x) for x in args.expect_profile_ids.split(",") if x.strip()}
    return asyncio.run(run(ids, args.confirm))


if __name__ == "__main__":
    sys.exit(main())
