"""商品卡片管理：新增（網址或編號）、修改開賣時間、刪除"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.product_info import fetch_product_meta
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
    c.store.add(pid, sale_time, fetch_product_meta(pid))
    return c.state()


@router.get("/preview")
def preview_product(ref: str):
    """唯讀查詢：解析商品網址/編號並抓展示資訊，供新增前預覽，不寫入清單"""
    try:
        pid = parse_product_ref(ref)
    except ValueError as e:
        raise HTTPException(400, str(e))
    meta = fetch_product_meta(pid)
    return {"pid": pid, **(meta or {})}


class ProductPatch(BaseModel):
    sale_time: str = ""


@router.patch("/{pid}")
def update_product(pid: str, p: ProductPatch, c: Container = Depends(get_container)):
    sale_time = p.sale_time.strip()
    if sale_time:
        try:
            parse_sale_time(sale_time)
        except ValueError as e:
            raise HTTPException(400, str(e))
    try:
        c.jobs.update_sale_time(pid, sale_time)
    except KeyError:
        raise HTTPException(404, "找不到商品")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return c.state()


class PidsIn(BaseModel):
    pids: list[str]


# 仿 POST /api/jobs/start|cancel 的 {pids} 慣例（DELETE 帶 body 支援度差）
@router.post("/remove")
def remove_products(body: PidsIn, c: Container = Depends(get_container)):
    if not body.pids:
        raise HTTPException(400, "未指定要刪除的商品")
    c.jobs.remove_products(body.pids)
    return c.state()


@router.delete("/{pid}")
def remove_product(pid: str, c: Container = Depends(get_container)):
    c.jobs.remove_product(pid)
    return c.state()
