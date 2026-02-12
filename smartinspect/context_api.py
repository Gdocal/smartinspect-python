"""
Context and trace helpers inspired by SmartInspect C# APIs.

Provides:
- SiContext: async-aware scoped key/value context tags
- AsyncContext: correlation and operation depth tracking
- ContextBuilder/ContextKey/ContextValue helpers
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional
import uuid


_si_context_stack: ContextVar[List[Dict[str, str]]] = ContextVar("si_context_stack", default=[])
_correlation_id: ContextVar[Optional[str]] = ContextVar("si_correlation_id", default=None)
_operation_name: ContextVar[Optional[str]] = ContextVar("si_operation_name", default=None)
_operation_depth: ContextVar[int] = ContextVar("si_operation_depth", default=0)


@dataclass(frozen=True)
class ContextValue:
    key: str
    value: str


class ContextKey:
    def __init__(self, name: str):
        self.name = name

    def set(self, value: Any) -> ContextValue:
        return ContextValue(self.name, "" if value is None else str(value))


class ContextBuilder:
    def __init__(self):
        self._values: Dict[str, str] = {}

    def with_value(self, key: str, value: Any) -> "ContextBuilder":
        self._values[key] = "" if value is None else str(value)
        return self

    def with_(self, key: str, value: Any) -> "ContextBuilder":
        """Alias for fluent API parity (`with` is a Python keyword)."""
        return self.with_value(key, value)

    def begin(self):
        return SiContext.scope(self._values)


class SiContext:
    @staticmethod
    def current() -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for layer in _si_context_stack.get():
            merged.update(layer)
        return merged

    @staticmethod
    def get(key: str) -> Optional[str]:
        return SiContext.current().get(key)

    @staticmethod
    def has(key: str) -> bool:
        return key in SiContext.current()

    @staticmethod
    @contextmanager
    def scope(context: Any = None, *values: ContextValue, **kwargs: Any) -> Iterator[None]:
        """
        Create a scoped context layer.

        Supports:
        - dict-like context
        - object with attributes (__dict__)
        - ContextValue items: SiContext.scope(Ctx.request_id.set("abc"))
        - key/value kwargs: SiContext.scope(request_id="abc")
        """
        layer: Dict[str, str] = {}

        if context is not None:
            if isinstance(context, dict):
                for k, v in context.items():
                    if v is not None:
                        layer[str(k)] = str(v)
            else:
                try:
                    for k, v in vars(context).items():
                        if v is not None and not k.startswith("_"):
                            layer[str(k)] = str(v)
                except TypeError:
                    layer["value"] = str(context)

        for item in values:
            layer[item.key] = item.value

        for k, v in kwargs.items():
            if v is not None:
                layer[str(k)] = str(v)

        stack = list(_si_context_stack.get())
        stack.append(layer)
        token = _si_context_stack.set(stack)
        try:
            yield
        finally:
            _si_context_stack.reset(token)

    @staticmethod
    def build() -> ContextBuilder:
        return ContextBuilder()

    @staticmethod
    def get_merged_context(additional_context: Any = None) -> Optional[Dict[str, str]]:
        merged = SiContext.current()
        if additional_context is None:
            return merged or None

        if isinstance(additional_context, dict):
            for k, v in additional_context.items():
                if v is not None:
                    merged[str(k)] = str(v)
        else:
            try:
                for k, v in vars(additional_context).items():
                    if v is not None and not k.startswith("_"):
                        merged[str(k)] = str(v)
            except TypeError:
                merged["value"] = str(additional_context)

        return merged or None


class AsyncContext:
    @staticmethod
    def correlation_id() -> Optional[str]:
        return _correlation_id.get()

    @staticmethod
    def operation_name() -> Optional[str]:
        return _operation_name.get()

    @staticmethod
    def operation_depth() -> int:
        return _operation_depth.get()

    @staticmethod
    def new_correlation(operation_name: Optional[str] = None) -> str:
        cid = uuid.uuid4().hex
        _correlation_id.set(cid)
        _operation_name.set(operation_name)
        _operation_depth.set(0)
        return cid

    @staticmethod
    def clear() -> None:
        _correlation_id.set(None)
        _operation_name.set(None)
        _operation_depth.set(0)

    @staticmethod
    def push_operation(name: str) -> None:
        _operation_name.set(name)
        _operation_depth.set(_operation_depth.get() + 1)

    @staticmethod
    def pop_operation() -> None:
        depth = _operation_depth.get()
        if depth > 0:
            _operation_depth.set(depth - 1)

    @staticmethod
    @contextmanager
    def begin_operation(name: str) -> Iterator[None]:
        prev_name = _operation_name.get()
        AsyncContext.push_operation(name)
        try:
            yield
        finally:
            _operation_name.set(prev_name)
            AsyncContext.pop_operation()

    @staticmethod
    @contextmanager
    def begin_correlation(operation_name: Optional[str] = None) -> Iterator[None]:
        prev_cid = _correlation_id.get()
        prev_name = _operation_name.get()
        prev_depth = _operation_depth.get()
        AsyncContext.new_correlation(operation_name)
        try:
            yield
        finally:
            _correlation_id.set(prev_cid)
            _operation_name.set(prev_name)
            _operation_depth.set(prev_depth)


class Ctx:
    """Typed key helpers (subset of C# style)."""

    request_id = ContextKey("requestId")
    user_id = ContextKey("userId")
    trace_id = ContextKey("_traceId")
    span_name = ContextKey("_spanName")
