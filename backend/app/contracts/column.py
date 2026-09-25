"""JSONB 칸에 형식을 거는 칸 타입.

[문제]
JSONB 는 아무 JSON 이나 받는다. 쓰는 쪽이 키 이름을 바꾸면 DB 는 그대로
저장하고, 읽는 쪽은 `.get("cells", [])` 로 빈 값을 받아 조용히 틀린 결과를
낸다. 실제로 리포트가 그렇게 처방 결과를 읽고 있었다.

[이 타입이 하는 일]
    저장할 때  형식 객체만 받는다. dict 를 넘기면 TypeError.
               형식 검사를 다시 한 번 거쳐 JSON 으로 바꿔 저장한다.
    읽을 때    DB 의 JSON 을 형식으로 검사해 **형식 객체로 돌려준다**.
               어긋난 행이 있으면 읽는 순간 ValidationError — 조용히 넘어가지 않는다.

DB 의 칸 타입 자체는 JSONB 그대로다. 마이그레이션이 필요 없다.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


class ContractJSONB(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def __init__(self, contract: Any):
        super().__init__()
        self.contract = contract
        self._adapter = TypeAdapter(contract)
        self._is_model = isinstance(contract, type) and issubclass(contract, BaseModel)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if self._is_model and not isinstance(value, self.contract):
            raise TypeError(
                f"{self.contract.__name__} 칸에는 형식 객체만 저장할 수 있다 "
                f"({type(value).__name__} 가 왔다). dict 로 넘기지 말고 형식 객체를 만들어 넘긴다."
            )
        checked = self._adapter.validate_python(value)
        return self._adapter.dump_python(checked, mode="json")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._adapter.validate_python(value)

    @property
    def python_type(self):
        return self.contract
