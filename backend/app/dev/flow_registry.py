"""모듈·기능 레지스트리 — 흐름 대시보드의 정적 지도.

[무엇을 사람이 적고, 무엇을 코드에서 뽑는가]

    모듈 목록        코드에서 자동 (app/services 를 훑는다)
    모듈 간 의존     코드에서 자동 (import 그래프)
    실제 오간 데이터  실행 중 계측 (tracer)
    기능 묶음        **여기에 손으로 적는다** — 사람만 알 수 있다

"이 기능은 어느 모듈을 쓰는가" 는 코드에서 자동으로 나오지 않는다. 함수를
부르는 경로가 엔드포인트·조건 분기에 흩어져 있기 때문이다. 그래서 FEATURES
만 선언하고, **선언이 실제와 어긋나면 테스트가 잡는다**(tests/test_flow_registry.py).

어긋난 지도는 없는 지도보다 나쁘다 — 보는 사람이 틀린 것을 믿게 된다.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

SERVICES_DIR = Path(__file__).resolve().parent.parent / "services"


# ── 모듈 ─────────────────────────────────────────────────────────────────

@dataclass
class Module:
    key: str                          # "diagnosis.judgment"
    label: str                        # 화면에 쓰는 한글 이름
    group: str                        # 지도에서 묶어 놓을 단위
    purity: str                       # pure | mixed | db — DB 를 건드리는가
    col: int = 0                      # 흐름도 열 위치 (왼→오른쪽 진행)
    functions: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)   # 반환 dataclass 이름


# 한글 이름·묶음·열 위치만 손으로 적는다. 목록 자체는 코드에서 나온다.
# 여기 없는 모듈이 코드에 생기면 테스트가 알려 준다.
#
# col = 흐름도의 열. 진단이 진행되는 순서대로 왼쪽에서 오른쪽으로 놓는다.
#   0 입력(설문·콘텐츠)  1 지문 배정  2 측정  3 판정  4 처방  5 산출물
_LABELS: Dict[str, tuple] = {
    #                            (한글 이름,            묶음,      col)
    "survey.definition":        ("설문 문항 정의",       "입력",     0),
    "survey.reader_type":       ("독자 유형 판별",       "입력",     0),
    "content.readability":      ("지문 난도 지표",       "콘텐츠",   0),
    "content.item_quality":     ("문항 품질 점검",       "콘텐츠",   0),
    "content.topic_tags":       ("주제 태그 허용 목록",       "콘텐츠",   0),
    "diagnosis.text_selection": ("지문 선택",            "배정",     1),
    "diagnosis.attention":      ("화면 이탈 집계",       "측정",     2),
    "stt.adapter":              ("STT 어댑터",           "측정",     2),
    "stt.clova":                ("Clova STT",            "측정",     2),
    "stt.mock":                 ("Mock STT",             "측정",     2),
    "stt.vad":                  ("발화 구간 검출",       "측정",     2),
    "stt.analyzer":             ("음독 채점 (A1·A2)",    "측정",     2),
    "diagnosis.scoring":        ("독해 채점 · Betts",    "측정",     2),
    "diagnosis.adaptive":       ("적응형 회차 판단",     "측정",     2),
    "diagnosis.judgment":       ("판정 (유창성×독해)",   "판정",     3),
    "diagnosis.pipeline":       ("판정·처방 파이프라인", "판정",     3),
    "diagnosis.prescription":   ("처방 생성",            "처방",     4),
    "diagnosis.environment":    ("환경 조정 처방",       "처방",     4),
    "diagnosis.book_recommend": ("적합도서 추천",        "처방",     4),
    "diagnosis.report":         ("학생 리포트 조립",     "산출물",   5),
    "legal":                    ("법정 기재 사항",       "운영",     5),
    "user_service":             ("계정",                 "운영",     0),
}


def _scan() -> Dict[str, Module]:
    """app/services 를 훑어 모듈 목록을 만든다. 손으로 적지 않는다."""
    found: Dict[str, Module] = {}
    for path in sorted(SERVICES_DIR.rglob("*.py")):
        if "__pycache__" in str(path) or path.name == "__init__.py":
            continue
        key = (path.relative_to(SERVICES_DIR).with_suffix("")
               .as_posix().replace("/", "."))
        tree = ast.parse(path.read_text(encoding="utf-8"))

        fns = [n for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not n.name.startswith("_")]
        dcs = [n.name for n in tree.body
               if isinstance(n, ast.ClassDef)
               and any("dataclass" in ast.unparse(d) for d in n.decorator_list)]

        # DB 세션을 인자로 받는 함수가 있으면 순수 변환이 아니다.
        db_fns = [n for n in fns
                  if any(a.annotation is not None
                         and "AsyncSession" in ast.unparse(a.annotation)
                         for a in n.args.args)]
        if not db_fns:
            purity = "pure"
        elif len(db_fns) == len(fns):
            purity = "db"
        else:
            purity = "mixed"

        label, group, col = _LABELS.get(key, (key, "미분류", 0))
        found[key] = Module(key=key, label=label, group=group, purity=purity,
                            col=col, functions=[f.name for f in fns], outputs=dcs)
    return found


def modules() -> Dict[str, Module]:
    return _scan()


# ── 연결선 (모듈이 실제로 주고받는 것) ───────────────────────────────────

@dataclass
class Edge:
    src: str
    dst: str
    payload: str                      # 무엇이 오가는가
    status: str = "fixed"             # fixed | undefined | mismatch
    note: str = ""
    schema: str = ""                # 이 인터페이스의 스키마 정의 (app/schemas 의 클래스)

    # status 의 뜻
    #   fixed      스키마가 정해져 있고 양쪽이 같은 것을 쓴다
    #   undefined  스키마를 적어 둔 곳이 없다. 지금은 우리 코드끼리만 맞다
    #   mismatch   두 곳에서 다르게 정의돼 있다. 지금 어긋나 있다


# ★ 이 목록이 곧 `docs/모듈간_데이터_확정필요.md` 의 대상이다.
#   화살표에 status 를 달아 두는 이유: 흐름도를 보면서 "어디가 아직
#   확정되지 않았나" 를 같이 읽을 수 있어야 한다.
EDGES: List[Edge] = [
    # 입력 → 배정
    Edge("survey.definition", "survey.reader_type",
         "A-1·A-2·A-3 응답 (빈도·태도·권수)", "fixed"),
    Edge("survey.reader_type", "diagnosis.text_selection",
         "type_1 / type_2", "fixed",
         "type_2 는 A-4 생애 그래프가 있어야 산출된다"),
    Edge("survey.definition", "diagnosis.text_selection",
         "interest_topics (C-1 코드 배열)", "mismatch",
         "지문 topic_tags 와 어휘가 갈려 있었다. 15편이 아직 허용 목록 밖"),
    Edge("content.topic_tags", "diagnosis.text_selection",
         "허용 주제 코드 15종", "fixed",
         "C-1 선지를 단일 진실 공급원으로 읽는다"),
    Edge("content.readability", "diagnosis.text_selection",
         "난도 라벨 (승인된 지문만)", "fixed",
         "라벨이 무엇을 가르는지는 STR-106 대기"),
    Edge("content.item_quality", "diagnosis.text_selection",
         "문항 품질 게이트 통과 여부", "fixed"),

    # 배정 → 측정
    Edge("diagnosis.text_selection", "diagnosis.scoring",
         "지문 + 문항 → 고른 답", "fixed",
         "그 회차 지문의 문항만, 선지 번호 1~선지 수. 회차·문항당 응답 하나",
         schema="measurement.AnswerSubmit"),
    Edge("diagnosis.text_selection", "diagnosis.attention",
         "읽기 시간(ms) + 이탈 이벤트 원본", "fixed",
         "읽기 시간은 두 버튼 사이 실제 시각 차이. 회차당 한 번(중복 409)",
         schema="measurement.SilentReadingSubmit"),
    Edge("stt.adapter", "stt.analyzer", "전사 텍스트", "fixed"),
    Edge("stt.vad", "stt.analyzer", "발화 구간 (참고용)", "fixed",
         "채점 시간으로 쓰지 않는다 — 계약 금지 사항"),

    # 측정 내부
    Edge("diagnosis.scoring", "diagnosis.adaptive",
         "회차 집계 → Betts 이력", "fixed",
         "2연속 instructional/frustration 으로 종료 판단. 회차당 집계 하나(중복 완료 409)",
         schema="measurement.RoundAggregate → AdaptiveDecision"),

    # 측정 → 판정
    Edge("diagnosis.scoring", "diagnosis.judgment",
         "CellResponse[] (영역×장르×정오)", "fixed",
         schema="judgment.CellResponse"),
    Edge("diagnosis.attention", "diagnosis.judgment",
         "A4 (음절/초)", "fixed",
         "A4 는 묵독 제출 API 가 지문 음절 수 ÷ 읽기 시간으로 계산해 저장한다. "
         "이탈 원본은 판정에 쓰지 않는다(보정 방식 미정)",
         schema="fluency_results.a4_syllable_per_sec"),
    Edge("stt.analyzer", "diagnosis.judgment",
         "A1 (음절/분) · A2", "undefined",
         "현재 음독은 판정에 도달하지 않는다. D-1 활성 시 연결될 경로"),
    Edge("survey.definition", "diagnosis.judgment",
         "predicted_correct (D-2)", "fixed",
         "D-2 예약·비활성이라 항상 None. 미수집은 null 로 둔다"),

    # 판정 → 처방
    Edge("diagnosis.judgment", "diagnosis.pipeline",
         "유창성·독해 판정 · 9칸 배치 · 약점 프로필 6칸", "fixed",
         "칸 이름은 명세대로 weakness_profile_12 지만 6칸이다 — 12 의 뜻은 기획 확인 대기",
         schema="judgment.FluencyJudgment · ComprehensionJudgment · MatrixPlacement"),
    Edge("diagnosis.pipeline", "diagnosis.prescription",
         "처방군 · 영점 난도 · 약점 프로필", "fixed",
         schema="judgment.WeaknessProfile → prescription.TrainingPlan"),
    Edge("diagnosis.pipeline", "diagnosis.environment",
         "home_environment_score (보호자 B-3~B-6)", "fixed",
         "경계값이 비어 항상 건너뛴다 (skipped_reason=no_thresholds)",
         schema="prescription.EnvironmentResult"),
    Edge("diagnosis.prescription", "diagnosis.text_selection",
         "난도 범위 (difficulty_range)", "fixed",
         "주제·장르 필터는 호출되지 않는다 — STR-111"),

    # 처방 → 산출물
    Edge("diagnosis.prescription", "diagnosis.report",
         "추천 지문 id 목록 · 훈련 대상 · 톤", "fixed",
         "처방은 지문을 id 로만 가리킨다. 제목은 리포트가 지문 테이블에서 읽는다",
         schema="prescription.RecommendedTexts · TrainingPlan"),
    Edge("diagnosis.environment", "diagnosis.report",
         "environment_level · environment_adjustment", "undefined",
         "스키마는 정했으나 리포트가 읽지 않는다 — 저장만 된다. 소비처(보호자 리포트) 미정",
         schema="prescription.EnvironmentResult"),
    Edge("diagnosis.prescription", "diagnosis.book_recommend",
         "난도 범위 · 관심 주제", "fixed",
         "books 테이블이 비어 결과는 빈 목록"),
    Edge("diagnosis.judgment", "diagnosis.report",
         "판정 결과 + 면책 코드 집합", "mismatch",
         "우리 쪽은 7종 enum 으로 고정했다. 계약 6종과 여전히 다르다 — 문준석 확인 대기",
         schema="judgment.Disclaimers → report.ReportContent"),
]


def edges() -> List[Edge]:
    return EDGES


# ── 기능 ─────────────────────────────────────────────────────────────────

@dataclass
class Feature:
    key: str
    label: str                        # 버튼에 쓰는 이름
    entry: str                        # 사용자가 하는 행동 (화면 기준)
    api: List[str]                    # 실제로 호출되는 엔드포인트
    modules: List[str]                # 이 기능이 거치는 모듈
    note: str = ""


# ★ 이 목록만 사람이 적는다. docs/동작흐름.md 와 같은 순서로 맞췄다.
FEATURES: List[Feature] = [
    Feature(
        key="survey_submit", label="설문 제출",
        entry="학생이 9문항을 채우고 '시작하기'",
        api=["POST /api/diagnosis/profile", "POST /api/diagnosis/session",
             "POST /api/diagnosis/session/{id}/start"],
        modules=["survey.definition", "survey.reader_type",
                 "diagnosis.text_selection"],
        note="프로필·세션 생성 + 1회차 지문 배정. 재시도를 걸지 않는 구간이다",
    ),
    Feature(
        key="silent_reading", label="지문 읽기 (묵독)",
        entry="'읽기 시작' → '다 읽었어'",
        api=["POST /api/diagnosis/fluency/silent"],
        modules=["diagnosis.attention"],
        note="A4(음절/초) 산출. 화면·서버 2중 타당성 가드",
    ),
    Feature(
        key="comprehension", label="문제 풀이",
        entry="문항 6개를 고를 때마다 즉시 저장",
        api=["POST /api/diagnosis/comprehension"],
        modules=["diagnosis.scoring"],
        note="문항별 규칙 채점",
    ),
    Feature(
        key="round_complete", label="회차 완료 · 다음 판단",
        entry="'제출하기'",
        api=["POST /api/diagnosis/round/{id}/complete"],
        modules=["diagnosis.scoring", "diagnosis.adaptive",
                 "diagnosis.text_selection"],
        note="집계 → Betts → 계속/종료 결정. 계속이면 다음 지문 배정",
    ),
    Feature(
        key="finalize", label="최종 판정 · 처방",
        entry="마지막 회차 종료 시 자동",
        api=["POST /api/diagnosis/session/{id}/finalize"],
        modules=["diagnosis.pipeline", "diagnosis.judgment",
                 "diagnosis.prescription", "diagnosis.environment",
                 "diagnosis.text_selection"],
        note="유창성×독해 9칸 → label_5 + G1~G6 → 처방",
    ),
    Feature(
        key="report", label="학생 리포트 생성",
        entry="판정 직후 자동",
        api=["POST /api/diagnosis/session/{id}/report"],
        modules=["diagnosis.report"],
        note="3층 구조 + 면책 문구. LLM 다듬기는 키가 있을 때만",
    ),
    Feature(
        key="books", label="적합도서 추천",
        entry="학생이 '나에게 맞는 책'",
        api=["GET /api/diagnosis/my/books"],
        modules=["diagnosis.book_recommend", "diagnosis.prescription"],
        note="books 테이블이 비어 현재 빈 목록",
    ),
    Feature(
        key="parent_survey", label="보호자 설문",
        entry="보호자가 10문항 제출",
        api=["POST /api/parent/survey"],
        modules=["survey.definition"],
        note="학생 진단과 시점이 분리돼 있다",
    ),
    Feature(
        key="oral", label="음독 채점 (비활성)",
        entry="현재 학생 화면에 진입 경로가 없다",
        api=["POST /api/audio/oral", "POST /api/diagnosis/fluency/oral"],
        modules=["stt.analyzer", "stt.adapter", "stt.mock", "stt.clova"],
        note="D-1 비활성. 계약은 확정됐으나 모호성 2축 기준 대기",
    ),
    Feature(
        key="content_review", label="콘텐츠 검수 (관리자)",
        entry="관리자가 지문·문항을 승인",
        api=["POST /api/admin/reviews"],
        modules=["content.readability", "content.item_quality",
                 "content.topic_tags"],
        note="승인 3단 게이트를 통과해야 진단에 쓰인다",
    ),
]


def features() -> List[Feature]:
    return FEATURES


def as_dict() -> dict:
    """대시보드가 받아 그리는 형태."""
    mods = modules()
    # 열 순서대로 내보낸다 — 화면이 왼→오른쪽으로 배치한다.
    ordered = sorted(mods.values(), key=lambda m: (m.col, m.group, m.label))
    return {
        "modules": [
            {"key": m.key, "label": m.label, "group": m.group, "col": m.col,
             "purity": m.purity, "functions": m.functions, "outputs": m.outputs}
            for m in ordered
        ],
        "cols": sorted({m.col for m in mods.values()}),
        "col_names": {0: "입력", 1: "지문 배정", 2: "측정", 3: "판정",
                      4: "처방", 5: "산출물"},
        "edges": [
            {"src": e.src, "dst": e.dst, "payload": e.payload,
             "status": e.status, "note": e.note, "schema": e.schema}
            for e in EDGES
        ],
        "features": [
            {"key": f.key, "label": f.label, "entry": f.entry, "api": f.api,
             "modules": f.modules, "note": f.note}
            for f in FEATURES
        ],
    }
