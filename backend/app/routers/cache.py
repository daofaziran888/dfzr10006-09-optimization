"""结果缓存加速接口：维护缓存配置，覆盖启用缓存、暂停缓存、关闭缓存等动作。

批量失效刷新：一次提交多条缓存记录与多选时间范围，按缓存键名和过期秒数分段推进；
中断后从失败段继续，已完成段不重算；结果落到缓存配置清单供路由服务核对。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, RefreshBatchPayload
from app.services.cache import CacheService
from app.services.cache_refresh import cache_refresh

router = APIRouter(prefix="/api/cache", tags=["结果缓存加速"])

service = CacheService()

LIST_FIELDS = ["配置编号", "缓存键名", "过期秒数", "刷新策略", "预热开关", "容量上限", "淘汰算法", "配置状态"]
STATUSES = ["草稿", "生效中", "已暂停", "已关闭"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按配置编号检索"),
    status: str | None = Query(default=None, description="草稿、生效中、已暂停、已关闭"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按配置编号与状态过滤结果缓存加速列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出结果缓存加速清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "cache", "total": total, "items": items}


@router.post("/refresh-batches")
def create_refresh_batch(payload: RefreshBatchPayload) -> dict[str, Any]:
    """提交批量失效刷新：按缓存键名和过期秒数分段，逐条返回失效结果。

    两个批次争抢同一缓存键名时，只有一个推进快照版本，另一个读取已完成结果；
    批次中断时返回失败位置，可凭批次编号从失败段继续。
    """
    batch, error = cache_refresh.create_batch(
        payload.entry_ids,
        payload.time_ranges,
        simulate_failure=payload.simulate_failure,
    )
    if batch is None:
        raise HTTPException(status_code=400, detail=error)
    results = cache_refresh.entry_results(batch)
    if batch["status"] == "已中断":
        message = f"批次 {batch['批次编号']} 已中断：{batch['失败位置']['原因']}"
    else:
        message = f"批次 {batch['批次编号']} 批量失效刷新完成"
    return {"ok": batch["status"] == "已完成", "message": message, "batch": batch, "results": results}


@router.get("/refresh-batches")
def list_refresh_batches() -> dict[str, Any]:
    """刷新批次列表：查看每个批次的状态与失败位置。"""
    items = cache_refresh.list_batches()
    return {"total": len(items), "items": items}


@router.get("/refresh-batches/{batch_id}")
def get_refresh_batch(batch_id: int) -> dict[str, Any]:
    """批次明细：每段完成位置、快照版本与逐条失效结果。"""
    batch = cache_refresh.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"刷新批次 {batch_id} 不存在")
    return {"batch": batch, "results": cache_refresh.entry_results(batch)}


@router.post("/refresh-batches/{batch_id}/resume")
def resume_refresh_batch(batch_id: int) -> dict[str, Any]:
    """从失败段继续：已完成段不重算、不回滚，完成水位只保留一份。"""
    batch, error = cache_refresh.resume_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=400, detail=error)
    results = cache_refresh.entry_results(batch)
    if batch["status"] == "已中断":
        message = f"批次 {batch['批次编号']} 再次中断：{batch['失败位置']['原因']}"
    else:
        message = f"批次 {batch['批次编号']} 已从失败段继续并完成"
    return {"ok": batch["status"] == "已完成", "message": message, "batch": batch, "results": results}


@router.get("/manifest")
def cache_manifest() -> dict[str, Any]:
    """缓存配置清单：每个缓存键名的失效状态与唯一一份完成水位。"""
    items = cache_refresh.manifest()
    return {"total": len(items), "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条缓存配置明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"缓存配置 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条缓存配置，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="缓存配置已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条缓存配置执行启用缓存、暂停缓存、关闭缓存；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
