"""結帳紀錄：標記完成、清除已完成"""

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Container, get_container

router = APIRouter(prefix="/api/checkouts", tags=["checkouts"])


@router.post("/{record_id}/complete")
def complete_checkout(record_id: str, c: Container = Depends(get_container)):
    record = c.checkout_repository.update(record_id, completed=True)
    if record is None:
        raise HTTPException(404, f"找不到結帳紀錄: {record_id}")
    c.bus.publish({"type": "checkout", "record": record})
    return c.state()


@router.delete("/completed")
def clear_completed(c: Container = Depends(get_container)):
    c.checkout_repository.clear_completed()
    return c.state()
