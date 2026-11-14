import { useCallback, useEffect, useMemo, useState } from 'react'

import { request } from '@/api/client'

const ENDPOINT = '/api/cache'
const columns = [
  "配置编号",
  "缓存键名",
  "过期秒数",
  "刷新策略",
  "预热开关",
  "容量上限",
  "淘汰算法",
  "配置状态"
]
const actions = [
  "启用缓存",
  "暂停缓存",
  "关闭缓存"
]
const TIME_RANGES = [
  "09:00-11:00 早高峰",
  "12:00-14:00 午间",
  "18:00-21:00 晚高峰"
]

type Row = Record<string, string | number | null>

type Segment = {
  段序号: number
  段内序号: number
  配置编号: string
  缓存键名: string
  status: string
  快照版本: number | null
  完成位置: string | null
  error: string | null
}

type Batch = {
  id: number
  批次编号: string
  status: string
  时间范围: string[]
  失败位置: { 配置编号: string; 段序号: number; 段内序号: number; 原因: string } | null
  segments: Segment[]
}

type EntryResult = {
  配置编号: string
  缓存键名: string
  失效结果: string
  完成段数: number
  总段数: number
  复用段数: number
  快照版本: number | null
  说明: string
}

type ManifestRow = {
  配置编号: string
  缓存键名: string
  过期秒数: string
  失效状态: string
  完成水位: { 批次编号: string; 已完成段: number; 总段数: number; 完成位置: string; 快照版本: number } | null
  快照版本: number
  重算次数: number
}

function statusBadge(status: string) {
  if (status === '已失效' || status === '已刷新' || status === '已完成') return 'badge ok'
  if (status === '部分失效' || status === '复用快照') return 'badge warn'
  if (status === '刷新失败' || status === '失败' || status === '已中断') return 'badge err'
  return 'badge'
}

export default function CacheView() {
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [notice, setNotice] = useState('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const filterFields = useMemo(() => columns.slice(0, 3), [])

  const [selected, setSelected] = useState<number[]>([])
  const [ranges, setRanges] = useState<string[]>([])
  const [batch, setBatch] = useState<Batch | null>(null)
  const [results, setResults] = useState<EntryResult[]>([])
  const [manifest, setManifest] = useState<ManifestRow[]>([])
  const [busy, setBusy] = useState(false)

  const reload = useCallback(async () => {
    setErrorMessage('')
    const query = new URLSearchParams(filters).toString()
    try {
      const response = await request(`${ENDPOINT}?${query}`)
      if (!response.ok) {
        throw new Error('缓存配置列表读取失败')
      }
      const payload = await response.json()
      setRows(payload.items ?? [])
      setTotal(payload.total ?? 0)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '结果缓存加速列表读取失败')
    }
  }, [filters])

  const reloadManifest = useCallback(async () => {
    try {
      const response = await request(`${ENDPOINT}/manifest`)
      if (!response.ok) {
        throw new Error('缓存配置清单读取失败')
      }
      const payload = await response.json()
      setManifest(payload.items ?? [])
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '缓存配置清单读取失败')
    }
  }, [])

  useEffect(() => {
    void reload()
    void reloadManifest()
  }, [reload, reloadManifest])

  async function runAction(action: string, row: Row) {
    setErrorMessage('')
    try {
      const response = await request(`${ENDPOINT}/${row.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      if (!response.ok) {
        throw new Error('结果缓存加速动作未生效，请稍后重试')
      }
      await reload()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '结果缓存加速操作失败')
    }
  }

  function toggleSelected(id: number) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]))
  }

  function toggleRange(range: string) {
    setRanges((prev) => (prev.includes(range) ? prev.filter((item) => item !== range) : [...prev, range]))
  }

  async function submitBatch() {
    setBusy(true)
    setErrorMessage('')
    setNotice('')
    try {
      const response = await request(`${ENDPOINT}/refresh-batches`, {
        method: 'POST',
        body: JSON.stringify({ entry_ids: selected, time_ranges: ranges }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail ?? '批量失效刷新提交失败')
      }
      setBatch(payload.batch)
      setResults(payload.results ?? [])
      setNotice(payload.message ?? '')
      await reloadManifest()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '批量失效刷新提交失败')
    } finally {
      setBusy(false)
    }
  }

  async function resumeBatch() {
    if (!batch) return
    setBusy(true)
    setErrorMessage('')
    setNotice('')
    try {
      const response = await request(`${ENDPOINT}/refresh-batches/${batch.id}/resume`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail ?? '从失败段继续失败')
      }
      setBatch(payload.batch)
      setResults(payload.results ?? [])
      setNotice(payload.message ?? '')
      await reloadManifest()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '从失败段继续失败')
    } finally {
      setBusy(false)
    }
  }

  const allChecked = rows.length > 0 && rows.every((row) => selected.includes(Number(row.id)))

  return (
    <section className="page" data-module="cache">
      <header className="page-head">
        <div>
          <h2>结果缓存加速管理</h2>
          <p className="page-desc">维护查询结果的缓存参数、过期策略与预热机制，为结果缓存加速提供可验证的数据工程流程。</p>
        </div>
        <div className="page-actions">
          <button className="btn primary" type="button" onClick={() => setErrorMessage('缓存配置登记入口尚未接入审批流')}>
            登记缓存配置
          </button>
          <button className="btn" type="button" onClick={() => window.open(`${ENDPOINT}/export`, '_blank')}>
            导出结果缓存加速清单
          </button>
        </div>
      </header>

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

      <div className="panel">
        <h3>批量失效刷新</h3>
        <p className="muted">勾选多条缓存记录与多个时间范围，一次提交后按缓存键名和过期秒数分段刷新，逐条给出失效结果。</p>
        <div className="chip-row">
          <span className="muted">时间范围：</span>
          {TIME_RANGES.map((range) => (
            <button
              key={range}
              type="button"
              className={ranges.includes(range) ? 'chip active' : 'chip'}
              onClick={() => toggleRange(range)}
            >
              {range}
            </button>
          ))}
          <button
            className="btn primary"
            type="button"
            disabled={busy || selected.length === 0 || ranges.length === 0}
            onClick={() => void submitBatch()}
          >
            {busy ? '刷新中…' : `提交批量失效（已选 ${selected.length} 条）`}
          </button>
        </div>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                checked={allChecked}
                onChange={() => setSelected(allChecked ? [] : rows.map((row) => Number(row.id)))}
              />
            </th>
            {columns.map((column) => <th key={column}>{column}</th>)}
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id)}>
              <td>
                <input
                  type="checkbox"
                  checked={selected.includes(Number(row.id))}
                  onChange={() => toggleSelected(Number(row.id))}
                />
              </td>
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
              <td className="empty-state" colSpan={columns.length + 2}>暂无结果缓存加速数据，可先登记缓存配置</td>
            </tr>
          )}
        </tbody>
      </table>

      <footer className="page-foot">
        <span>共 {total} 条结果缓存加速记录</span>
        {errorMessage && <span className="error-text">{errorMessage}</span>}
        {notice && <span className="muted">{notice}</span>}
      </footer>

      {batch && (
        <div className="panel">
          <h3>
            批次 {batch.批次编号}
            <span className={statusBadge(batch.status)}>{batch.status}</span>
          </h3>
          <p className="muted">时间范围：{batch.时间范围.join('、')}</p>
          {batch.失败位置 && (
            <p className="error-text">
              失败位置：{batch.失败位置.配置编号} 第 {batch.失败位置.段内序号} 段（批次第 {batch.失败位置.段序号} 段）——{batch.失败位置.原因}
            </p>
          )}
          {batch.status === '已中断' && (
            <button className="btn primary" type="button" disabled={busy} onClick={() => void resumeBatch()}>
              {busy ? '继续中…' : '从失败段继续（已完成段不重算）'}
            </button>
          )}

          <h4>逐条失效结果</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>配置编号</th><th>缓存键名</th><th>失效结果</th><th>完成段数</th><th>复用段数</th><th>快照版本</th><th>说明</th>
              </tr>
            </thead>
            <tbody>
              {results.map((item) => (
                <tr key={item.配置编号}>
                  <td>{item.配置编号}</td>
                  <td>{item.缓存键名}</td>
                  <td><span className={statusBadge(item.失效结果)}>{item.失效结果}</span></td>
                  <td>{item.完成段数}/{item.总段数}</td>
                  <td>{item.复用段数}</td>
                  <td>{item.快照版本 ?? '—'}</td>
                  <td>{item.说明}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>分段明细</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>段序号</th><th>配置编号</th><th>缓存键名</th><th>段内序号</th><th>状态</th><th>完成位置</th><th>快照版本</th><th>错误</th>
              </tr>
            </thead>
            <tbody>
              {batch.segments.map((segment) => (
                <tr key={segment.段序号}>
                  <td>{segment.段序号}</td>
                  <td>{segment.配置编号}</td>
                  <td>{segment.缓存键名}</td>
                  <td>{segment.段内序号}</td>
                  <td><span className={statusBadge(segment.status)}>{segment.status}</span></td>
                  <td>{segment.完成位置 ?? '—'}</td>
                  <td>{segment.快照版本 ?? '—'}</td>
                  <td>{segment.error ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel">
        <h3>缓存配置清单（失效结果与完成水位）</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>配置编号</th><th>缓存键名</th><th>过期秒数</th><th>失效状态</th><th>完成水位</th><th>快照版本</th><th>重算次数</th>
            </tr>
          </thead>
          <tbody>
            {manifest.map((item) => (
              <tr key={item.配置编号}>
                <td>{item.配置编号}</td>
                <td>{item.缓存键名}</td>
                <td>{item.过期秒数}</td>
                <td><span className={statusBadge(item.失效状态)}>{item.失效状态}</span></td>
                <td>
                  {item.完成水位
                    ? `${item.完成水位.批次编号} ${item.完成水位.已完成段}/${item.完成水位.总段数} 段（${item.完成水位.完成位置}）`
                    : '—'}
                </td>
                <td>{item.快照版本}</td>
                <td>{item.重算次数}</td>
              </tr>
            ))}
            {manifest.length === 0 && (
              <tr><td className="empty-state" colSpan={7}>暂无缓存配置清单数据</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
