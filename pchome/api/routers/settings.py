"""可調整設定的讀取/更新：登入以外的 CVC/AUTO_PAY/搶購時機/進階調校"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Container, get_container

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    cvc: str | None = None
    auto_pay: bool | None = None
    default_interval_secs: float | None = None
    default_lead_secs: float | None = None
    fast_poll_window_secs: float | None = None
    slow_poll_factor: float | None = None
    resync_secs: float | None = None
    max_retries: int | None = None
    retry_delay_secs: float | None = None


@router.get("")
def get_settings(c: Container = Depends(get_container)):
    return c.settings_repository.get()


@router.patch("")
def update_settings(body: SettingsPatch, c: Container = Depends(get_container)):
    try:
        return c.settings_repository.update(body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
