"""SSE 事件流

已知限制：同步 generator 由 starlette 丟到 threadpool 迭代，
每個訂閱分頁佔一條 threadpool 執行緒；個人工具 1-2 個分頁可接受。
"""

import json
import queue

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...infra.event_bus import EventBus
from ..deps import Container, get_container

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/state")
def state(c: Container = Depends(get_container)):
    return c.state()


@router.get("/events")
def events(c: Container = Depends(get_container)):
    return StreamingResponse(_sse_stream(c.bus), media_type="text/event-stream")


def _sse_stream(bus: EventBus):
    """15 秒無事件送 keepalive，斷線時解除訂閱"""
    q = bus.subscribe()
    try:
        yield "retry: 2000\n\n"
        while True:
            try:
                event = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        bus.unsubscribe(q)
