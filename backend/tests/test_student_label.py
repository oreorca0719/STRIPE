"""학생 노출 라벨 — 서버와 화면이 같은 말을 하는가 (STR-123).

[왜 이 테스트가 있나]
`label_5` 는 내부 ENUM 이고, 학생에게는 친화 표현으로 바꿔 보여준다(§2 SCR-13).
그 변환표가 **두 곳에** 있다.

    서버   app/services/diagnosis/report.py   STUDENT_LABEL
    화면   frontend/src/utils/diagnosis.ts    LABEL_5

결과 화면은 서버가 준 라벨을 쓰고 이 표를 폴백으로 쓰지만, **이력 화면은
리포트를 읽지 않아 항상 화면 표를 쓴다.** 두 표가 갈리면 같은 진단이 화면마다
다른 말로 보인다.

실제로 갈려 있었다. 화면 표가 한 단계씩 높았다.

    observe   서버 "보통이야"               화면 "잘함"
    caution   서버 "조금 더 연습하면 좋겠어"  화면 "보통"

폴백은 리포트 생성이 실패했을 때만 나오므로, 어긋나도 평소에는 드러나지
않는다. 드물게 어긋나는 쪽이 오히려 찾기 어렵다 — 그래서 테스트로 고정한다.

[왜 화면 파일을 읽나]
언어가 달라 공용 모듈로 묶을 수 없다. 화면 표를 서버 테스트가 직접 읽어
대조하는 것이, 두 표가 갈린 것을 CI 에서 잡는 가장 싼 방법이다.
"""
import re
from pathlib import Path

from app.models.core import Label5
from app.services.diagnosis.report import STUDENT_LABEL

TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "diagnosis.ts"

# 확정표 원문 (STR-123, 문준석 2026-08-01)
CONTRACT = {
    "excellent": "잘하는 편!",
    "observe": "보통이야",
    "caution": "조금 더 연습하면 좋겠어",
    "risk": "이 부분을 더 연습해보자",
    "urgent": "함께 연습해보자!",
}

# 난도 방향을 암시하는 말. 응원 문구가 추천 난도와 어긋나던 결함(STR-96)이
# 화면 폴백으로 되돌아오는 것을 막는다.
DIFFICULTY_WORDS = ("어려운", "쉬운", "높은 수준", "최고 수준", "더 넓은")


def _frontend_labels() -> dict:
    """화면 표에서 ko 값을 뽑는다. 파싱 실패는 테스트 실패로 드러나야 한다."""
    src = TS.read_text(encoding="utf-8")
    block = re.search(r"export const LABEL_5[^{]*\{(.*?)\n\}", src, re.S)
    assert block, "LABEL_5 표를 찾지 못했다 — 화면 구조가 바뀌었다"
    found = dict(re.findall(r"(\w+):\s*\{[^}]*?ko:\s*'([^']*)'", block.group(1)))
    assert found, "ko 값을 뽑지 못했다"
    return found


def test_서버_표가_확정표와_같다():
    assert {k.value: v for k, v in STUDENT_LABEL.items()} == CONTRACT


def test_화면_표가_확정표와_같다():
    """이력 화면은 리포트를 읽지 않아 이 표를 항상 쓴다."""
    assert _frontend_labels() == CONTRACT


def test_다섯_등급을_빠짐없이_덮는다():
    """빠진 등급이 있으면 그 학생만 기본값('결과 준비 중')을 보게 된다."""
    codes = {e.value for e in Label5}
    assert codes == set(CONTRACT), f"등급 목록 불일치: {codes ^ set(CONTRACT)}"


def test_화면_폴백_문구에_난도_표현이_없다():
    """STR-96 이 화면 쪽으로 되돌아오는 것을 막는다.

    특히 'observe'(보통이야) 학생에게 '최고 수준' 을 말하고 있었다.
    """
    src = TS.read_text(encoding="utf-8")
    block = re.search(r"export const LABEL_5[^{]*\{(.*?)\n\}", src, re.S).group(1)
    msgs = re.findall(r"msg:\s*'([^']*)'", block)
    assert msgs, "msg 값을 뽑지 못했다"
    for m in msgs:
        for w in DIFFICULTY_WORDS:
            assert w not in m, f"폴백 문구에 난도 표현 '{w}': {m}"
