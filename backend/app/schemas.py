"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class RefreshBatchPayload(BaseModel):
    """批量失效刷新：一次提交多条缓存记录与多选时间范围。"""

    entry_ids: list[int] = Field(default_factory=list)
    time_ranges: list[str] = Field(default_factory=list)
    simulate_failure: bool = True



class RegistryEntry(BaseModel):
    """服务实例明细结构。"""

    field_0: str | None = None  # 实例编号
    field_1: str | None = None  # 服务名称
    field_2: str | None = None  # 服务地址
    field_3: str | None = None  # 服务版本
    field_4: str | None = None  # 注册时间
    field_5: str | None = None  # 心跳间隔
    field_6: str | None = None  # 健康状态
    field_7: str | None = None  # 实例标签

class RouterEntry(BaseModel):
    """路由规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 匹配条件
    field_2: str | None = None  # 目标服务
    field_3: str | None = None  # 权重比例
    field_4: str | None = None  # 灰度标记
    field_5: str | None = None  # 降级服务
    field_6: str | None = None  # 重试次数
    field_7: str | None = None  # 规则状态

class CacheEntry(BaseModel):
    """缓存配置明细结构。"""

    field_0: str | None = None  # 配置编号
    field_1: str | None = None  # 缓存键名
    field_2: str | None = None  # 过期秒数
    field_3: str | None = None  # 刷新策略
    field_4: str | None = None  # 预热开关
    field_5: str | None = None  # 容量上限
    field_6: str | None = None  # 淘汰算法
    field_7: str | None = None  # 配置状态

class LimiterEntry(BaseModel):
    """限流规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 限流对象
    field_2: str | None = None  # 限流算法
    field_3: str | None = None  # 每秒上限
    field_4: str | None = None  # 突发容量
    field_5: str | None = None  # 降级动作
    field_6: str | None = None  # 恢复时间
    field_7: str | None = None  # 规则状态

class OrchestraEntry(BaseModel):
    """编排流程明细结构。"""

    field_0: str | None = None  # 流程编号
    field_1: str | None = None  # 流程名称
    field_2: str | None = None  # 编排步骤
    field_3: str | None = None  # 并行策略
    field_4: str | None = None  # 超时控制
    field_5: str | None = None  # 失败回滚
    field_6: str | None = None  # 执行日志
    field_7: str | None = None  # 流程状态

class TraceEntry(BaseModel):
    """追踪记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 调用链ID
    field_2: str | None = None  # 服务名称
    field_3: str | None = None  # 调用耗时
    field_4: str | None = None  # 调用状态
    field_5: str | None = None  # 上游服务
    field_6: str | None = None  # 下游服务
    field_7: str | None = None  # 采样时间

class DiagnoseEntry(BaseModel):
    """诊断报告明细结构。"""

    field_0: str | None = None  # 报告编号
    field_1: str | None = None  # 诊断对象
    field_2: str | None = None  # 健康分值
    field_3: str | None = None  # 异常类型
    field_4: str | None = None  # 根因分析
    field_5: str | None = None  # 修复建议
    field_6: str | None = None  # 诊断耗时
    field_7: str | None = None  # 诊断时间

class SchemaEntry(BaseModel):
    """接口定义明细结构。"""

    field_0: str | None = None  # 接口编号
    field_1: str | None = None  # 接口名称
    field_2: str | None = None  # 请求方法
    field_3: str | None = None  # 请求参数
    field_4: str | None = None  # 响应字段
    field_5: str | None = None  # 字段类型
    field_6: str | None = None  # 契约版本
    field_7: str | None = None  # 接口状态

class SubscribeEntry(BaseModel):
    """订阅任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 数据源名称
    field_2: str | None = None  # 推送目标
    field_3: str | None = None  # 推送格式
    field_4: str | None = None  # 推送频率
    field_5: str | None = None  # 过滤条件
    field_6: str | None = None  # 最近推送
    field_7: str | None = None  # 任务状态

class TransformEntry(BaseModel):
    """加工规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 输入格式
    field_2: str | None = None  # 输出格式
    field_3: str | None = None  # 映射表达式
    field_4: str | None = None  # 字段过滤
    field_5: str | None = None  # 编码设置
    field_6: str | None = None  # 转换日志
    field_7: str | None = None  # 规则状态

class MockEntry(BaseModel):
    """模拟配置明细结构。"""

    field_0: str | None = None  # 配置编号
    field_1: str | None = None  # 模拟对象
    field_2: str | None = None  # 数据模板
    field_3: str | None = None  # 生成条数
    field_4: str | None = None  # 字段规则
    field_5: str | None = None  # 响应延迟
    field_6: str | None = None  # 错误概率
    field_7: str | None = None  # 配置状态

class GatewayEntry(BaseModel):
    """网关配置明细结构。"""

    field_0: str | None = None  # 配置编号
    field_1: str | None = None  # 网关名称
    field_2: str | None = None  # 监听端口
    field_3: str | None = None  # 协议类型
    field_4: str | None = None  # 认证方式
    field_5: str | None = None  # 超时秒数
    field_6: str | None = None  # 并发上限
    field_7: str | None = None  # 配置状态

class MetricEntry(BaseModel):
    """指标采集器明细结构。"""

    field_0: str | None = None  # 采集器编号
    field_1: str | None = None  # 监控对象
    field_2: str | None = None  # 指标名称
    field_3: str | None = None  # 采集间隔
    field_4: str | None = None  # 聚合方式
    field_5: str | None = None  # 保留天数
    field_6: str | None = None  # 最近采集
    field_7: str | None = None  # 采集器状态

class WhitelistEntry(BaseModel):
    """来源登记明细结构。"""

    field_0: str | None = None  # 登记编号
    field_1: str | None = None  # 应用名称
    field_2: str | None = None  # 调用标识
    field_3: str | None = None  # 日配额上限
    field_4: str | None = None  # 优先级
    field_5: str | None = None  # 生效日期
    field_6: str | None = None  # 失效日期
    field_7: str | None = None  # 登记状态

class BalanceEntry(BaseModel):
    """均衡策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 策略名称
    field_2: str | None = None  # 均衡算法
    field_3: str | None = None  # 服务列表
    field_4: str | None = None  # 权重配置
    field_5: str | None = None  # 故障转移
    field_6: str | None = None  # 健康检查
    field_7: str | None = None  # 策略状态

class RollbackEntry(BaseModel):
    """版本快照明细结构。"""

    field_0: str | None = None  # 快照编号
    field_1: str | None = None  # 服务名称
    field_2: str | None = None  # 版本号
    field_3: str | None = None  # 配置快照
    field_4: str | None = None  # 创建时间
    field_5: str | None = None  # 回退次数
    field_6: str | None = None  # 最近回退
    field_7: str | None = None  # 快照状态
