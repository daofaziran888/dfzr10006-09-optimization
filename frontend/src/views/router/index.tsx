import { useCallback, useEffect, useMemo, useState } from 'react'

import { request } from '@/api/client'

const ENDPOINT = '/api/router'
const columns = [
  "规则编号",
  "匹配条件",
  "目标服务",
  "权重比例",
  "灰度标记",
  "降级服务",
  "重试次数",
  "规则状态"
]
const actions = [
  "启用规则",
  "降级路由",
  "关闭规则"
]
const statuses = [
  "草稿",
  "生效中",
  "已降级",
  "已关闭"
]
const stats = [
  {
    "label": "路由规则总数",
    "value": 0
  },
  {
    "label": "生效中规则",
    "value": 0
  },
  {
    "label": "已降级规则",
    "value": 0
  }
]

type Row = Record<string, string | number | null>

export default function RouterView() {
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [switchCheck, setSwitchCheck] = useState<{ 可切换: boolean; 未失效键名: string[]; 说明: string } | null>(null)
  const [filters, setFilters] = useState<Record<string, string>>({})
  const filterFields = useMemo(() => columns.slice(0, 3), [])

  const reload = useCallback(async () => {
    setErrorMessage('')
    const query = new URLSearchParams(filters).toString()
    try {
      const response = await request(`${ENDPOINT}?${query}`)
      if (!response.ok) {
        throw new Error('路由规则列表读取失败')
      }
      const payload = await response.json()
      setRows(payload.items ?? [])
      setTotal(payload.total ?? 0)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '查询路由分发列表读取失败')
    }
  }, [filters])

  useEffect(() => {
    void reload()
  }, [reload])

  async function runAction(action: string, row: Row) {
    setErrorMessage('')
    try {
      const response = await request(`${ENDPOINT}/${row.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      if (!response.ok) {
        throw new Error('查询路由分发动作未生效，请稍后重试')
      }
      await reload()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '查询路由分发操作失败')
    }
  }

  async function checkSwitch() {
    setErrorMessage('')
    try {
      const response = await request(`${ENDPOINT}/switch-check`)
      if (!response.ok) {
        throw new Error('切换前检查读取失败')
      }
      setSwitchCheck(await response.json())
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '切换前检查读取失败')
    }
  }

  return (
    <section className="page" data-module="router">
      <header className="page-head">
        <div>
          <h2>查询路由分发管理</h2>
          <p className="page-desc">维护查询路由的匹配条件、分发权重与降级策略，为查询路由分发提供可审计的数据工程流程。</p>
        </div>
        <div className="page-actions">
          <button className="btn primary" type="button" onClick={() => setErrorMessage('路由规则登记入口尚未接入审批流')}>
            登记路由规则
          </button>
          <button className="btn" type="button" onClick={() => void checkSwitch()}>
            切换前检查未失效键名
          </button>
          <button className="btn" type="button" onClick={() => window.open(`${ENDPOINT}/export`, '_blank')}>
            导出查询路由分发清单
          </button>
        </div>
      </header>

      {switchCheck && (
        <div className="panel">
          <h3>切换目标服务前检查</h3>
          <p className={switchCheck.可切换 ? 'muted' : 'error-text'}>{switchCheck.说明}</p>
          {switchCheck.未失效键名.length > 0 && (
            <p className="muted">未失效键名：{switchCheck.未失效键名.join('、')}</p>
          )}
        </div>
      )}

      <div className="stat-row">
        {stats.map((item) => (
          <article key={item.label} className="stat-card">
            <span className="stat-label">{item.label}</span>
            <strong className="stat-value">{item.value}</strong>
          </article>
        ))}
      </div>

      <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); void reload() }}>
        {filterFields.map((field) => (
          <label key={field} className="filter-item">
            <span>{field}</span>
            <input
              value={filters[field] ?? ''}
              placeholder={`按${field}检索`}
              onChange={(event) => setFilters((prev) => ({ ...prev, [field]: event.target.value }))}
            />
          </label>
        ))}
        <button className="btn" type="submit">查询</button>
        <button className="btn ghost" type="button" onClick={() => setFilters({})}>重置条件</button>
      </form>

      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => <th key={column}>{column}</th>)}
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id)}>
              {columns.map((column) => <td key={column}>{row[column] ?? '—'}</td>)}
              <td className="row-actions">
                {actions.map((action) => (
                  <button key={action} className="link" type="button" onClick={() => void runAction(action, row)}>
                    {action}
                  </button>
                ))}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="empty-state" colSpan={columns.length + 1}>暂无查询路由分发数据，可先登记路由规则</td>
            </tr>
          )}
        </tbody>
      </table>

      <footer className="page-foot">
        <span>共 {total} 条查询路由分发记录</span>
        {errorMessage && <span className="error-text">{errorMessage}</span>}
      </footer>
    </section>
  )
}
