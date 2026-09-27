"""모듈 호출 계측 — 바깥에서 감싼다 (PM 결정 2026-09-24, B안).

[왜 데코레이터를 안 쓰는가]
서비스 파일에 `@trace` 를 붙이면 운영 코드 22개 모듈에 손을 대게 된다. 그중
상당수가 판정·채점 로직이고, 오늘 결함이 난 자리들이다. **관찰 목적으로 그
파일들을 다시 건드리는 것은 위험 대비 이득이 나쁘다.**

대신 여기서 모듈 객체의 함수를 런타임에 감싼다. 꺼져 있으면 감싸는 작업
자체를 하지 않으므로 **운영에서는 진짜로 아무 일도 일어나지 않는다.**

[무엇을 기록하는가]
형태만. 값은 남기지 않는다 — `shapes.py` 참조.

[어떻게 묶는가]
HTTP 요청 하나가 추적 하나다. 요청이 없는 호출(테스트·스크립트)은 "직접
호출" 묶음으로 들어간다. 나중에 관리자 화면으로 옮길 때 세션 단위로 묶을 수
있도록 session_id 를 함께 받는다.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import time
import uuid
from collections import deque
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

from app.core.config import settings
from app.dev import shapes
from app.dev import flow_registry as R

MAX_TRACES = 50          # 최근 것만 들고 있는다. 디스크에 쌓지 않는다


@dataclass
class Event:
    seq: int
    module: str                       # "diagnosis.judgment"
    fn: str                           # "judge_comprehension"
    args: Dict[str, str]              # {"grade_group": "GradeGroup.G4_G6"}
    ret: Optional[str] = None         # "ComprehensionJudgment{…}"
    ms: float = 0.0
    error: Optional[str] = None       # 예외 타입만. 메시지는 값을 담을 수 있다
    depth: int = 0


@dataclass
class Trace:
    id: str
    label: str                        # "POST /api/diagnosis/session/1/finalize"
    started_at: float
    session_id: Optional[int] = None
    events: List[Event] = field(default_factory=list)
    ms: float = 0.0
    done: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["modules"] = sorted({e.module for e in self.events})
        return d


_current: ContextVar[Optional[Trace]] = ContextVar("flow_trace", default=None)
_depth: ContextVar[int] = ContextVar("flow_depth", default=0)
_traces: Deque[Trace] = deque(maxlen=MAX_TRACES)
_installed = False


# ── 켜져 있는가 ──────────────────────────────────────────────────────────

def enabled() -> bool:
    """실시간 기록을 해도 되는가.

    운영(ENV=prod)에서 파일럿 동의 강제(REQUIRE_PILOT_CONSENT)가 켜지면 — 실제
    아동이 응시하기 시작하면 — 끈다. 값은 남기지 않지만 어느 학생이 어떤 경로를
    탔는지가 메모리에 남고, 그것은 파일럿 수집 범위 밖이다. 모듈 지도는 계속 보인다.
    """
    if not settings.FLOW_TRACE:
        return False
    if settings.ENV == "prod" and settings.REQUIRE_PILOT_CONSENT:
        return False
    return True


# ── 추적 단위 ────────────────────────────────────────────────────────────

def start(label: str, session_id: Optional[int] = None) -> Optional[Trace]:
    if not enabled():
        return None
    t = Trace(id=uuid.uuid4().hex[:12], label=label,
              started_at=time.time(), session_id=session_id)
    _traces.append(t)
    _current.set(t)
    _depth.set(0)
    return t


def finish(t: Optional[Trace]) -> None:
    if t is None:
        return
    t.ms = round((time.time() - t.started_at) * 1000, 1)
    t.done = True
    _current.set(None)


def traces() -> List[dict]:
    """최근 것이 위로."""
    return [t.to_dict() for t in reversed(_traces)]


def clear() -> None:
    _traces.clear()


def _record(module: str, fn: str, args: Dict[str, str]) -> Optional[Event]:
    t = _current.get()
    if t is None:
        return None
    ev = Event(seq=len(t.events), module=module, fn=fn, args=args,
               depth=_depth.get())
    t.events.append(ev)
    return ev


# ── 감싸기 ───────────────────────────────────────────────────────────────

def _wrap(module_key: str, mod: Any, name: str) -> None:
    original = getattr(mod, name)
    if getattr(original, "__flow_wrapped__", False):
        return
    try:
        arg_names = list(inspect.signature(original).parameters)
    except (TypeError, ValueError):
        arg_names = []

    def _before(args, kwargs):
        return _record(module_key, name, shapes.describe_args(args, kwargs, arg_names))

    def _after(ev, started, result, exc):
        if ev is None:
            return
        ev.ms = round((time.perf_counter() - started) * 1000, 2)
        if exc is not None:
            # 예외 **타입만**. 메시지에는 값이 섞일 수 있다.
            ev.error = type(exc).__name__
        else:
            ev.ret = shapes.describe(result)

    if asyncio.iscoroutinefunction(original):
        @functools.wraps(original)
        async def wrapper(*args, **kwargs):
            ev = _before(args, kwargs)
            _depth.set(_depth.get() + 1)
            started = time.perf_counter()
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                _after(ev, started, None, e)
                raise
            finally:
                _depth.set(max(0, _depth.get() - 1))
            _after(ev, started, result, None)
            return result
    else:
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            ev = _before(args, kwargs)
            _depth.set(_depth.get() + 1)
            started = time.perf_counter()
            try:
                result = original(*args, **kwargs)
            except Exception as e:
                _after(ev, started, None, e)
                raise
            finally:
                _depth.set(max(0, _depth.get() - 1))
            _after(ev, started, result, None)
            return result

    wrapper.__flow_wrapped__ = True          # 두 번 감싸지 않는다
    setattr(mod, name, wrapper)


def install() -> int:
    """레지스트리에 있는 모듈의 공개 함수를 감싼다. 감싼 개수를 돌려준다.

    감쌀 대상을 따로 적지 않는다 — 레지스트리가 이미 모듈별 공개 함수를
    코드에서 뽑고 있으므로, 새 함수가 생기면 자동으로 포함된다.
    """
    global _installed
    if not enabled() or _installed:
        return 0

    import importlib

    count = 0
    for key, meta in R.modules().items():
        try:
            mod = importlib.import_module(f"app.services.{key}")
        except Exception:
            continue
        for fn in meta.functions:
            target = getattr(mod, fn, None)
            if target is None or not callable(target):
                continue
            # 이 모듈에서 정의한 것만 감싼다. import 해 온 이름까지 감싸면
            # 같은 함수가 여러 모듈 이름으로 두 번 기록된다.
            if getattr(target, "__module__", "") != f"app.services.{key}":
                continue
            _wrap(key, mod, fn)
            count += 1
    _installed = True
    return count
