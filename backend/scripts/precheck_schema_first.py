"""schema-first 배포 전 점검 — 운영 DB 가 016~022 와 새 스키마를 통과하는지 본다.

[왜]
start.sh 는 컨테이너가 뜰 때 `alembic upgrade head` 를 돌린다. 016~022 는 옛 값을
변환하지 않는다(학생 데이터가 없다는 전제). 목록 밖 값·NULL·중복이 한 행이라도
있으면 마이그레이션이 실패하고 서버가 뜨지 않는다. 마이그레이션을 통과해도 JSONB
칸은 읽는 순간 스키마 검사(SchemaJSONB)를 받으므로, 옛 모양의 행은 그 화면을 500
으로 만든다.

[하는 일]
    · 읽기 전용 트랜잭션(SET TRANSACTION READ ONLY). 아무것도 쓰지 않는다.
    · 1부  마이그레이션 실패 지점 — 016~022 의 형 변환·NOT NULL·유일 제약·CREATE TYPE
    · 2부  읽기 실패 지점 — 모든 SchemaJSONB 칸을 마이그레이션이 바꿀 모양으로 바꾼 뒤
           스키마로 검사한다. 칸 목록은 모델에서 자동으로 모은다(손으로 적지 않는다).
    · 각 항목을 [진단] (배포 전 비우기 대상) / [유지] (콘텐츠·설문·관리자 기록) 로 나눈다.
      [진단] 쪽 실패는 PM 확인 후 테이블을 비우면 사라진다. [유지] 쪽 실패는 데이터를
      고치거나 마이그레이션에 변환을 넣어야 한다.

[한계]
    enum 목록은 마이그레이션 파일(018·020 의 NEW_ENUMS)과 DB 의 기존 enum 타입에서
    읽는다. 즉 "새 코드의 규칙을 운영 데이터가 통과하는가"만 본다. 규칙 자체가
    운영에 맞는지는 결과를 보고 사람이 판단한다.

[실행] 새 코드(schema-first)와 운영 DB 접속이 둘 다 있는 곳에서:
    DATABASE_URL=postgresql+asyncpg://... python scripts/precheck_schema_first.py
    DATABASE_URL=... python scripts/precheck_schema_first.py --json   # 기계용 출력
    DATABASE_URL=... python scripts/precheck_schema_first.py --redact # 값 없이 id·건수·오류 위치만
                                                                      # (공개 로그에 남길 때)

종료 코드: 0 = 막는 것 없음 · 1 = [유지] 쪽 실패 있음 · 2 = [진단] 쪽만 실패(비우면 통과)
          · 3 = 전제가 맞지 않음(현재 리비전이 015 가 아님 등)
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  — 모든 모델을 Base.metadata 에 올린다
from app.schemas.column import SchemaJSONB  # noqa: E402

EXPECTED_REVISION = "015"
SAMPLE_LIMIT = 5
# --redact 일 때 샘플에서 남기는 키 — 행 식별자·건수·스키마 오류 위치뿐. 칸의 값은 버린다.
REDACT_KEEP = {"id", "ids", "rows", "error", "session_id", "round_id", "type", "question_id",
               "judgment_id", "diagnosis_session_id", "typname"}

# 배포 전 비우기 대상(016·017 docstring 의 "진단 결과 테이블"). 나머지는 유지 대상.
DIAGNOSIS_TABLES = {
    "diagnosis_sessions", "diagnosis_rounds", "comprehension_results", "question_responses",
    "fluency_results", "judgment_results", "prescription_results", "reports",
}


def _load_migration(prefix: str):
    path = next((BACKEND_DIR / "alembic" / "versions").glob(f"{prefix}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{prefix}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M018 = _load_migration("018")
M020 = _load_migration("020")


@dataclass
class Finding:
    migration: str
    table: str
    check: str
    bad_rows: int
    samples: list = field(default_factory=list)

    @property
    def group(self) -> str:
        return "진단" if self.table in DIAGNOSIS_TABLES else "유지"


# ---------------------------------------------------------------------------
# 1부 — 마이그레이션 실패 지점
# ---------------------------------------------------------------------------

async def _count_and_sample(conn, table: str, where: str, cols: str, params=None):
    params = params or {}
    n = (await conn.execute(text(f"SELECT count(*) FROM {table} WHERE {where}"), params)).scalar()
    samples = []
    if n:
        rows = await conn.execute(
            text(f"SELECT {cols} FROM {table} WHERE {where} ORDER BY 1 LIMIT {SAMPLE_LIMIT}"), params)
        samples = [dict(r._mapping) for r in rows]
    return n, samples


async def _enum_labels(conn, type_name: str) -> list[str] | None:
    rows = (await conn.execute(text(
        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = :n ORDER BY e.enumsortorder"), {"n": type_name})).scalars().all()
    return list(rows) or None


async def _check_enum_cast(conn, migration, table, col, enum_name, labels) -> Finding:
    where = f"{col} IS NOT NULL AND {col}::text <> ALL(:labels)"
    n, samples = await _count_and_sample(conn, table, where, f"id, {col}::text AS value",
                                         {"labels": labels})
    return Finding(migration, table, f"{col} → {enum_name} 형 변환 (허용: {', '.join(labels)})",
                   n, samples)


async def _check_duplicates(conn, migration, table, cols: list[str]) -> Finding:
    key = ", ".join(cols)
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in cols)
    n = (await conn.execute(text(
        f"SELECT count(*) FROM (SELECT {key} FROM {table} WHERE {not_null} "
        f"GROUP BY {key} HAVING count(*) > 1) d"))).scalar()
    samples = []
    if n:
        rows = await conn.execute(text(
            f"SELECT {key}, count(*) AS rows, array_agg(id ORDER BY id) AS ids FROM {table} "
            f"WHERE {not_null} GROUP BY {key} HAVING count(*) > 1 ORDER BY 1 LIMIT {SAMPLE_LIMIT}"))
        samples = [dict(r._mapping) for r in rows]
    return Finding(migration, table, f"({key}) 유일 제약 — 중복 묶음 수", n, samples)


async def migration_checks(conn) -> list[Finding]:
    out: list[Finding] = []

    # 016 — environment_level → level3
    level3 = await _enum_labels(conn, "level3")
    out.append(await _check_enum_cast(conn, "016", "prescription_results", "environment_level",
                                      "level3", level3))

    # 017 — fluency_results
    n, s = await _count_and_sample(
        conn, "fluency_results",
        "silent_reading_time IS NULL AND reading_time_seconds IS NULL",
        "id, type::text AS type, round_id")
    out.append(Finding("017", "fluency_results", "reading_time_ms NOT NULL — 읽기 시간이 둘 다 없음", n, s))
    n, s = await _count_and_sample(conn, "fluency_results", "round_id IS NULL",
                                   "id, session_id, type::text AS type")
    out.append(Finding("017", "fluency_results", "round_id NOT NULL — round_id 없음", n, s))
    out.append(await _check_duplicates(conn, "017", "fluency_results", ["round_id", "type"]))
    out.append(await _check_duplicates(conn, "017", "comprehension_results", ["round_id"]))
    out.append(await _check_duplicates(conn, "017", "question_responses", ["round_id", "question_id"]))

    # 018 — deleted_counts 키 이름 바꾸기: 빈 객체는 jsonb_object_agg 가 NULL 을 내 NOT NULL 에 걸린다
    n, s = await _count_and_sample(
        conn, "data_disposal_logs",
        "jsonb_typeof(deleted_counts) <> 'object' OR deleted_counts = '{}'::jsonb",
        "id, deleted_counts")
    out.append(Finding("018", "data_disposal_logs",
                       "deleted_counts 키 이름 바꾸기 — 빈 객체·객체 아님이면 NULL 이 되어 실패", n, s))
    for table, col, enum_name, _old in M018.CHANGES:
        labels = M018.NEW_ENUMS.get(enum_name) or await _enum_labels(conn, enum_name)
        out.append(await _check_enum_cast(conn, "018", table, col, enum_name, labels))
    out.append(await _check_duplicates(conn, "018", "judgment_results", ["diagnosis_session_id"]))
    out.append(await _check_duplicates(conn, "018", "prescription_results", ["judgment_id"]))

    # 019 — voluntary_reading → INTEGER (빈 문자열·"3권" 은 실패)
    n, s = await _count_and_sample(
        conn, "student_profiles",
        r"voluntary_reading IS NOT NULL AND voluntary_reading !~ '^\s*[+-]?[0-9]+\s*$'",
        "id, voluntary_reading")
    out.append(Finding("019", "student_profiles", "voluntary_reading → INTEGER 형 변환", n, s))

    # 020 — CREATE TYPE 은 checkfirst 가 없다. 이미 있으면 실패
    existing = (await conn.execute(text(
        "SELECT typname FROM pg_type WHERE typname = ANY(:n)"),
        {"n": list(M020.NEW_ENUMS)})).scalars().all()
    out.append(Finding("020", "(pg_type)", "새 enum 타입이 이미 있음 — CREATE TYPE 실패",
                       len(existing), [{"typname": t} for t in existing]))
    for table, col, enum_name, _old in M020.CHANGES:
        out.append(await _check_enum_cast(conn, "020", table, col, enum_name,
                                          M020.NEW_ENUMS[enum_name]))
    return out


# ---------------------------------------------------------------------------
# 2부 — 읽기 실패 지점 (SchemaJSONB)
# ---------------------------------------------------------------------------

def _rename_key(old: str, new: str):
    def f(v):
        if isinstance(v, dict) and old in v:
            v = {k: val for k, val in v.items() if k != old} | {new: v[old]}
        return v
    return f


def _suffix_count(v):
    return {f"{k}_count": val for k, val in v.items()} if isinstance(v, dict) else v


def _null_to_empty_codes(v):
    return {"codes": []} if v is None else v


# 마이그레이션이 값을 바꾸는 칸: (table, column) → (015 시점에 읽을 SQL 식, 변환)
TRANSFORMS = {
    ("texts", "readability_metrics"): ("readability_metrics",
                                       _rename_key("lexical_variety", "lexical_variety_ratio")),
    ("data_disposal_logs", "deleted_counts"): ("deleted_counts", _suffix_count),
    ("judgment_results", "disclaimer_flags"): ("disclaimer_flags", _null_to_empty_codes),
    ("reports", "disclaimer_flags"): ("disclaimer_flags", _null_to_empty_codes),
    # 017 이 raw_data.attention.events 를 옮긴다(묵독 행만)
    ("fluency_results", "away_events"): (
        "CASE WHEN type = 'silent' AND raw_data ? 'attention' "
        "THEN jsonb_build_object('events', raw_data->'attention'->'events') END",
        None),
}
# 021 이 새로 만드는 칸 — 기존 행은 모두 NULL
NEW_COLUMNS = {("fluency_results", "oral_analysis")}


async def _existing_columns(conn) -> set[tuple[str, str]]:
    rows = await conn.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"))
    return {(r.table_name, r.column_name) for r in rows}


def _short_error(e: ValidationError) -> str:
    errs = e.errors()
    first = errs[0]
    loc = ".".join(str(p) for p in first["loc"]) or "(전체)"
    more = f" 외 {len(errs) - 1}건" if len(errs) > 1 else ""
    return f"{loc}: {first['msg']}{more}"


async def jsonb_checks(conn) -> list[Finding]:
    have = await _existing_columns(conn)
    out: list[Finding] = []
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if not isinstance(col.type, SchemaJSONB):
                continue
            key = (table.name, col.name)
            if key in NEW_COLUMNS:
                continue
            expr, transform = TRANSFORMS.get(key, (col.name, None))
            if expr == col.name and key not in have:
                out.append(Finding("—", table.name, f"{col.name}: 015 시점 DB 에 칸이 없음 (점검 스크립트 갱신 필요)", 1))
                continue
            rows = await conn.execute(text(f"SELECT id, {expr} AS v FROM {table.name} ORDER BY id"))
            adapter = col.type._adapter
            bad, samples = 0, []
            for r in rows:
                v = transform(r.v) if transform else r.v
                if v is None:
                    if not col.nullable:
                        bad += 1
                        if len(samples) < SAMPLE_LIMIT:
                            samples.append({"id": r.id, "error": "NULL — NOT NULL 칸"})
                    continue
                try:
                    adapter.validate_python(v)
                except ValidationError as e:
                    bad += 1
                    if len(samples) < SAMPLE_LIMIT:
                        samples.append({"id": r.id, "error": _short_error(e)})
            out.append(Finding("읽기", table.name,
                               f"{col.name} 스키마 검사"
                               + (f" ({col.type.schema.__name__})" if isinstance(col.type.schema, type) else ""),
                               bad, samples))
    return out


# ---------------------------------------------------------------------------

async def row_counts(conn) -> dict[str, int]:
    out = {}
    for t in Base.metadata.sorted_tables:
        out[t.name] = (await conn.execute(text(f"SELECT count(*) FROM {t.name}"))).scalar()
    return out


async def run() -> dict:
    # 앱의 engine 은 ENV=dev 면 SQL 을 전부 찍는다. 점검 출력이 묻히지 않게 따로 만든다.
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        await conn.execute(text("SET TRANSACTION READ ONLY"))
        revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        result = {"revision": revision, "expected_revision": EXPECTED_REVISION}
        if revision != EXPECTED_REVISION:
            result["error"] = (f"현재 리비전이 {revision} 이다. 이 점검은 {EXPECTED_REVISION} 상태를 "
                               "전제로 한다(016~022 적용 전).")
            await engine.dispose()
            return result
        result["row_counts"] = await row_counts(conn)
        result["findings"] = [asdict(f) | {"group": f.group}
                              for f in await migration_checks(conn) + await jsonb_checks(conn)]
        await conn.rollback()
    await engine.dispose()
    return result


def _print_report(result: dict) -> None:
    print(f"리비전: {result['revision']} (전제 {result['expected_revision']})")
    if "error" in result:
        print(f"[중단] {result['error']}")
        return
    counts = result["row_counts"]
    print("\n행 수 (0 이 아닌 테이블)")
    for t, n in counts.items():
        if n:
            print(f"  {'[진단]' if t in DIAGNOSIS_TABLES else '[유지]'} {t}: {n}")

    for group in ("유지", "진단"):
        bad = [f for f in result["findings"] if f["group"] == group and f["bad_rows"]]
        title = ("[유지] 콘텐츠·설문·관리자 — 고쳐야 배포 가능" if group == "유지"
                 else "[진단] 비우기 대상 — PM 확인 후 비우면 사라짐")
        print(f"\n{title}: {len(bad)}건")
        for f in bad:
            print(f"  ✗ {f['migration']:>4} {f['table']}.{f['check']} — {f['bad_rows']}")
            for s in f["samples"]:
                print(f"        {s}")
    ok = sum(1 for f in result["findings"] if not f["bad_rows"])
    print(f"\n통과 {ok} / {len(result['findings'])} 항목")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    ap.add_argument("--redact", action="store_true",
                    help="샘플에서 칸의 값을 빼고 id·건수·오류 위치만 남긴다")
    args = ap.parse_args()
    result = asyncio.run(run())
    if args.redact:
        for f in result.get("findings", []):
            f["samples"] = [{k: v for k, v in s.items() if k in REDACT_KEEP} for s in f["samples"]]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(result)
    if "error" in result:
        return 3
    bad = [f for f in result["findings"] if f["bad_rows"]]
    if any(f["group"] == "유지" for f in bad):
        return 1
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
