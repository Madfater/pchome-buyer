"""商品卡片管理：新增（網址或編號）、刪除"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.timing import parse_sale_time
from ...services.product_id import parse_product_ref
from ..deps import Container, get_container

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductIn(BaseModel):
    ref: str  # 商品頁網址或商品編號
    sale_time: str = ""


@router.post("")
def add_product(p: ProductIn, c: Container = Depends(get_container)):
    try:
        pid = parse_product_ref(p.ref)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sale_time = p.sale_time.strip()
    if sale_time:
        try:
            parse_sale_time(sale_time)
        except ValueError as e:
            raise HTTPException(400, str(e))
    c.store.add(pid, sale_time)
    return c.state()


@router.delete("/{pid}")
def remove_product(pid: str, c: Container = Depends(get_container)):
    c.jobs.remove_product(pid)
    return c.state()
