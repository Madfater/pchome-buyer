"""job 啟動與取消（單卡或批次）"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Container, get_container

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class PidsIn(BaseModel):
    pids: list[str]


@router.post("/start")
def start_jobs(body: PidsIn, c: Container = Depends(get_container)):
    if not body.pids:
        raise HTTPException(400, "未指定要啟動的商品")
    c.jobs.start(body.pids)
    return c.state()


@router.post("/cancel")
def cancel_jobs(body: PidsIn, c: Container = Depends(get_container)):
    if not body.pids:
        raise HTTPException(400, "未指定要取消的商品")
    c.jobs.cancel(body.pids)
    return c.state()
