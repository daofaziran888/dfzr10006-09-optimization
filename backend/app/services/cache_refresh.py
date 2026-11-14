"""结果缓存加速：批量失效与分段刷新。

设计口径（批次大小与并发策略）：
- 每个缓存键名拆成 4 个逻辑分片，每 2 个分片为一段，即每条缓存配置 2 段；
- 批次内分段按序推进，完成水位单调向前：中断后从失败段继续，已完成段不重算、不回滚；
- 批次之间允许并发提交：同一缓存键名用互斥锁 + 快照版本仲裁，
  先拿到锁的批次推进版本，后到的批次读取已完成快照直接复用；
- 段指纹 = 缓存键名 + 过期秒数 + 时间范围，指纹一致的段视为未受新配置影响，不再重算。
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.store import store

MODULE = "cache"

SHARDS_PER_KEY = 4  # 每个缓存键名的逻辑分片数
SEGMENT_SIZE = 2  # 每段分片数（批次大小）：每条缓存配置 2 段
RECOMPUTE_LATENCY = 0.05  # 模拟单段重算耗时，让并发争抢可观测

SEGMENT_DONE = ("已刷新", "复用快照")

# 中断样本：CACH-0002 的第二段首次刷新时模拟一次下游超时，恢复后不再触发
TRANSIENT_FAILURE_POINT = ("CACH-0002", 2)


class SegmentRefreshError(RuntimeError):
    """单段刷新失败：批次在此中断，等待从失败段继续。"""


@dataclass
class KeyState:
    """缓存键名的版本状态：版本只单调推进，重算次数用于核对是否重复计算。

    segments 记录每一段（段内序号）已完成的指纹与快照：指纹一致才算同一段工作，
    避免同一键名的后续段被误判成已完成。
    """

    version: int = 0
    recompute_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    segments: dict[int, dict[str, Any]] = field(default_factory=dict)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _fingerprint(key_name: str, ttl: str, time_ranges: list[str]) -> str:
    raw = "|".join([key_name, ttl, *sorted(time_ranges)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class CacheRefreshService:
    """批量失效刷新的编排器：计划分段、推进水位、仲裁版本。"""

    def __init__(self) -> None:
        self._mu = threading.Lock()
        self._batches: list[dict[str, Any]] = []
        self._key_states: dict[str, KeyState] = {}
        self._watermarks: dict[str, dict[str, Any]] = {}
        self._failures_consumed: set[tuple[str, int]] = set()

    # ---------- 批次计划 ----------

    def create_batch(
        self,
        entry_ids: list[int],
        time_ranges: list[str],
        simulate_failure: bool = True,
    ) -> tuple[dict[str, Any] | None, str]:
        if not entry_ids:
            return None, "请至少选择一条缓存记录"
        ranges = [str(item).strip() for item in time_ranges if str(item).strip()]
        if not ranges:
            return None, "请至少选择一个时间范围"
        entries: list[dict[str, Any]] = []
        missing: list[str] = []
        for entry_id in entry_ids:
            row = store.find(MODULE, int(entry_id))
            if row is None:
                missing.append(str(entry_id))
            else:
                entries.append(row)
        if missing:
            return None, f"缓存配置 {', '.join(missing)} 不存在或已归档"

        with self._mu:
            batch_id = len(self._batches) + 1
            batch: dict[str, Any] = {
                "id": batch_id,
                "批次编号": f"BATC-{batch_id:04d}",
                "status": "运行中",
                "时间范围": ranges,
                "模拟故障": simulate_failure,
                "配置编号列表": [str(entry.get("配置编号", "")) for entry in entries],
                "segments": [],
                "失败位置": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
            seq = 0
            for entry in entries:
                key_name = str(entry.get("缓存键名", ""))
                ttl = str(entry.get("过期秒数", ""))
                shards = [f"{key_name}#{index}" for index in range(SHARDS_PER_KEY)]
                for offset in range(0, len(shards), SEGMENT_SIZE):
                    seq += 1
                    batch["segments"].append({
                        "段序号": seq,
                        "段内序号": offset // SEGMENT_SIZE + 1,
                        "配置编号": str(entry.get("配置编号", "")),
                        "缓存键名": key_name,
                        "过期秒数": ttl,
                        "分片": shards[offset:offset + SEGMENT_SIZE],
                        "指纹": _fingerprint(key_name, ttl, ranges),
                        "status": "待刷新",
                        "快照版本": None,
                        "完成位置": None,
                        "结果": None,
                        "error": None,
                    })
            self._batches.append(batch)

        self._run(batch)
        return batch, ""

    def list_batches(self) -> list[dict[str, Any]]:
        with self._mu:
            batches = list(self._batches)
        return [
            {
                "id": batch["id"],
                "批次编号": batch["批次编号"],
                "status": batch["status"],
                "配置编号列表": batch["配置编号列表"],
                "时间范围": batch["时间范围"],
                "失败位置": batch["失败位置"],
                "created_at": batch["created_at"],
                "updated_at": batch["updated_at"],
            }
            for batch in batches
        ]

    def get_batch(self, batch_id: int) -> dict[str, Any] | None:
        with self._mu:
            for batch in self._batches:
                if batch["id"] == batch_id:
                    return batch
        return None

    def resume_batch(self, batch_id: int) -> tuple[dict[str, Any] | None, str]:
        batch = self.get_batch(batch_id)
        if batch is None:
            return None, f"刷新批次 {batch_id} 不存在"
        if batch["status"] != "已中断":
            return None, f"批次 {batch['批次编号']} 当前状态为「{batch['status']}」，只有已中断批次需要继续"
        self._run(batch)
        return batch, ""

    # ---------- 分段执行 ----------

    def _run(self, batch: dict[str, Any]) -> None:
        batch["status"] = "运行中"
        batch["updated_at"] = _now()
        for segment in batch["segments"]:
            if segment["status"] in SEGMENT_DONE:
                continue  # 已完成段不重算、不回滚
            try:
                self._run_segment(batch, segment)
            except SegmentRefreshError as exc:
                segment["status"] = "失败"
                segment["error"] = str(exc)
                batch["status"] = "已中断"
                batch["失败位置"] = {
                    "配置编号": segment["配置编号"],
                    "段序号": segment["段序号"],
                    "段内序号": segment["段内序号"],
                    "原因": segment["error"],
                }
                batch["updated_at"] = _now()
                return
        batch["status"] = "已完成"
        batch["失败位置"] = None
        batch["updated_at"] = _now()

    def _run_segment(self, batch: dict[str, Any], segment: dict[str, Any]) -> None:
        key_name = segment["缓存键名"]
        seg_no = segment["段内序号"]
        with self._mu:
            state = self._key_states.setdefault(key_name, KeyState())
        with state.lock:
            mark = state.segments.get(seg_no)
            if mark is not None and mark["fingerprint"] == segment["指纹"]:
                # 争抢同一键名的另一个批次已推进版本：直接读取已完成结果，不重算
                segment["status"] = "复用快照"
                segment["快照版本"] = mark["version"]
                segment["结果"] = mark["result"]
            else:
                self._maybe_fail(batch, segment)
                time.sleep(RECOMPUTE_LATENCY)  # 模拟重算耗时
                state.recompute_count += 1
                state.version += 1
                result = {
                    "分片": segment["分片"],
                    "时间范围": batch["时间范围"],
                    "刷新行数": len(segment["分片"]) * 100,
                    "生成时间": _now(),
                }
                state.segments[seg_no] = {
                    "fingerprint": segment["指纹"],
                    "result": result,
                    "version": state.version,
                }
                segment["status"] = "已刷新"
                segment["快照版本"] = state.version
                segment["结果"] = result
            segment["完成位置"] = f"分片{seg_no * SEGMENT_SIZE}/{SHARDS_PER_KEY}"
            segment["error"] = None
        self._advance_watermark(batch, segment)

    def _maybe_fail(self, batch: dict[str, Any], segment: dict[str, Any]) -> None:
        point = (segment["配置编号"], segment["段内序号"])
        if not batch["模拟故障"] or point != TRANSIENT_FAILURE_POINT:
            return
        with self._mu:
            if point in self._failures_consumed:
                return
            self._failures_consumed.add(point)
        raise SegmentRefreshError(
            f"模拟下游超时：{point[0]} 第 {point[1]} 段刷新报错，批次在此中断"
        )

    def _advance_watermark(self, batch: dict[str, Any], segment: dict[str, Any]) -> None:
        """推进完成水位：同一缓存键名在清单里只有一份水位记录，原地更新不追加。"""
        key_name = segment["缓存键名"]
        total = sum(1 for item in batch["segments"] if item["缓存键名"] == key_name)
        with self._mu:
            watermark = self._watermarks.get(key_name)
            if watermark is None or watermark["批次编号"] != batch["批次编号"]:
                watermark = {"批次编号": batch["批次编号"], "已完成段": 0, "总段数": total}
                self._watermarks[key_name] = watermark
            watermark["已完成段"] += 1
            watermark["完成位置"] = segment["完成位置"]
            watermark["快照版本"] = segment["快照版本"]
            watermark["更新时间"] = _now()

    # ---------- 结果与清单 ----------

    def entry_results(self, batch: dict[str, Any]) -> list[dict[str, Any]]:
        """按缓存记录逐条汇总失效结果。"""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for segment in batch["segments"]:
            grouped.setdefault(segment["配置编号"], []).append(segment)
        results: list[dict[str, Any]] = []
        for code, segments in grouped.items():
            done = [item for item in segments if item["status"] in SEGMENT_DONE]
            reused = [item for item in segments if item["status"] == "复用快照"]
            failed = [item for item in segments if item["status"] == "失败"]
            if failed:
                result, note = "刷新失败", f"{failed[0]['error']}；可从失败段继续"
            elif len(done) == len(segments):
                result = "已失效"
                note = "全部段复用已完成快照，未重算" if len(reused) == len(segments) else "全部段已失效"
            elif done:
                result, note = "部分失效", f"已完成 {len(done)}/{len(segments)} 段"
            else:
                result, note = "待失效", "尚未开始刷新"
            results.append({
                "配置编号": code,
                "缓存键名": segments[0]["缓存键名"],
                "失效结果": result,
                "完成段数": len(done),
                "总段数": len(segments),
                "复用段数": len(reused),
                "快照版本": done[-1]["快照版本"] if done else None,
                "说明": note,
            })
        return results

    def manifest(self) -> list[dict[str, Any]]:
        """缓存配置清单：每条缓存配置一行，带失效状态与唯一一份完成水位。"""
        rows: list[dict[str, Any]] = []
        for entry in store.rows(MODULE):
            key_name = str(entry.get("缓存键名", ""))
            watermark = self._watermarks.get(key_name)
            state = self._key_states.get(key_name)
            if watermark is None:
                status = "待失效"
            elif watermark["已完成段"] >= watermark["总段数"]:
                status = "已失效"
            else:
                status = "部分失效"
            rows.append({
                "配置编号": entry.get("配置编号"),
                "缓存键名": key_name,
                "过期秒数": entry.get("过期秒数"),
                "失效状态": status,
                "完成水位": watermark,
                "快照版本": state.version if state else 0,
                "重算次数": state.recompute_count if state else 0,
            })
        return rows

    def pending_invalidations(self) -> list[dict[str, Any]]:
        """尚未失效的缓存键名：路由服务切换目标服务前据此判断能否安全切换。"""
        return [row for row in self.manifest() if row["失效状态"] != "已失效"]


cache_refresh = CacheRefreshService()
