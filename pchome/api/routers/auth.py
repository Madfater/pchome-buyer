"""登入憑證匯入與 session 狀態"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Container, get_container

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthImportIn(BaseModel):
    payload: str  # auth_state.json 內容或擴充功能匯出的 cookie 陣列（原始 JSON 文字）


@router.post("/import")
def import_auth(body: AuthImportIn, c: Container = Depends(get_container)):
    result = c.auth.import_auth(body.payload)
    if not result.ok:
        raise HTTPException(400, result.error)
    return result.to_dict()


@router.get("/status")
def auth_status(live: bool = False, c: Container = Depends(get_container)):
    return c.auth.status(live=live)
