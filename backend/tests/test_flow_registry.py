"""흐름 레지스트리가 코드와 어긋나지 않는가.

[왜 이 테스트가 필요한가]
대시보드는 이 레지스트리를 그린다. 레지스트리가 실제 코드와 어긋나면
**보는 사람이 틀린 것을 믿게 된다** — 없는 지도보다 나쁘다.

모듈 목록은 코드에서 자동으로 뽑으므로 어긋날 수 없다. 어긋날 수 있는 것은
사람이 적은 두 가지다.

    _LABELS   모듈 한글 이름·묶음 — 새 모듈이 생기면 빠진다
    FEATURES  기능이 거치는 모듈  — 코드가 바뀌면 낡는다

[FEATURES 검증의 한계 — 명시해 둔다]
"이 기능이 실제로 이 모듈을 부르는가" 를 정적으로 완전히 증명할 수는 없다.
호출이 엔드포인트·조건 분기에 흩어져 있기 때문이다. 그래서 아래는
**존재 검증**(적어 둔 모듈 키가 실재하는가)까지만 한다. 실제 호출 순서는
실행 중 계측(tracer)이 기록하며, 그 기록과 선언의 대조는 대시보드에서 본다.
"""
from pathlib import Path

from app.dev import flow_registry as R


def test_모든_모듈에_한글_이름이_있다():
    """새 서비스 모듈을 만들면 이 테스트가 먼저 알려 준다."""
    미분류 = [m.key for m in R.modules().values() if m.group == "미분류"]
    assert not 미분류, f"_LABELS 에 추가해야 한다: {미분류}"


def test_기능이_가리키는_모듈이_실재한다():
    """모듈을 지우거나 이름을 바꾸면 선언이 낡는다."""
    있는것 = set(R.modules())
    for f in R.features():
        없는것 = [m for m in f.modules if m not in 있는것]
        assert not 없는것, f"{f.key} 가 없는 모듈을 가리킨다: {없는것}"


def test_기능마다_모듈이_하나_이상이다():
    """모듈이 비면 버튼을 눌러도 아무 불이 안 켜진다."""
    for f in R.features():
        assert f.modules, f"{f.key} 에 모듈이 없다"


def test_기능_키가_중복되지_않는다():
    keys = [f.key for f in R.features()]
    assert len(keys) == len(set(keys))


def test_어느_기능도_쓰지_않는_모듈을_드러낸다():
    """실패시키지 않는다 — 다만 목록을 남겨 눈에 보이게 한다.

    어느 기능에도 안 잡힌 모듈은 둘 중 하나다. 선언이 빠졌거나, 정말로
    아무도 안 쓰는 코드다. 둘 다 알아야 한다.
    """
    쓰이는것 = {m for f in R.features() for m in f.modules}
    안쓰임 = sorted(set(R.modules()) - 쓰이는것)
    # 지금 알려진 것들. 늘어나면 이 목록을 갱신하며 사유를 확인한다.
    알려진것 = {
        "stt.vad",        # /api/audio/timing 참고 경로. 채점 시간으로 쓰지 않는다
        "legal",          # 관리자 시스템 점검(GET /api/admin/system)에서만 조회
        "user_service",   # 인증 경로. 진단 기능과 분리돼 있다
    }
    뜻밖 = [m for m in 안쓰임 if m not in 알려진것]
    assert not 뜻밖, f"어느 기능에도 안 잡힌 모듈: {뜻밖} — 선언 누락인지 사용처 없는지 확인"


def test_흐름도_배치표가_레지스트리를_모두_담는다():
    """흐름도는 좌표를 손으로 정한 표(NODE·ROUTE)로 그린다.

    레지스트리에 모듈·연결을 추가하고 배치표를 안 고치면 그 블록·선이
    화면에서 조용히 빠진다. 같은 개념이 두 곳에 적혀 있으니 여기서 맞춘다.
    """
    import re
    html = (Path(R.__file__).parent / "flow_dashboard.html").read_text(encoding="utf-8")
    node_block = html.split("const NODE={", 1)[1].split("};", 1)[0]
    route_block = html.split("const ROUTE={", 1)[1].split("};", 1)[0]
    배치된_모듈 = set(re.findall(r"'([\w.]+)':\s*\[", node_block))
    배치된_연결 = set(re.findall(r"'([\w.]+>[\w.]+)':", route_block))

    빠진_모듈 = sorted(set(R.modules()) - 배치된_모듈)
    빠진_연결 = sorted({f"{e.src}>{e.dst}" for e in R.edges()} - 배치된_연결)
    assert not 빠진_모듈, f"흐름도 NODE 에 좌표가 없다: {빠진_모듈}"
    assert not 빠진_연결, f"흐름도 ROUTE 에 경로가 없다: {빠진_연결}"
    # 반대 방향 — 지워진 모듈·연결의 좌표가 남으면 표가 낡는다
    assert not 배치된_모듈 - set(R.modules()), "NODE 에 없는 모듈의 좌표가 남아 있다"
    assert not 배치된_연결 - {f"{e.src}>{e.dst}" for e in R.edges()}, \
        "ROUTE 에 없는 연결의 경로가 남아 있다"


def test_기능이_실재하는_엔드포인트를_가리킨다():
    """경로를 고치고 레지스트리를 안 고치면 대시보드가 옛 경로를 보여 준다."""
    src = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (Path(__file__).resolve().parents[1] / "app" / "api" / "endpoints").glob("*.py")
    )
    for f in R.features():
        for entry in f.api:
            method, path = entry.split(" ", 1)
            # prefix 는 라우터 등록에서 붙으므로 마지막 조각으로 확인한다.
            tail = path.replace("/api/diagnosis", "").replace("/api/audio", "") \
                       .replace("/api/parent", "").replace("/api/review", "")
            tail = tail.replace("{id}", "{session_id}")
            assert tail.strip("/").split("/")[0] in src or tail in src, \
                f"{f.key}: {entry} 에 해당하는 라우트를 찾지 못했다"
