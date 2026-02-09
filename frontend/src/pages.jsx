import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, post, BASE } from './api.js'
import { PageHeader, Card, Stat, Badge, Spinner, Empty, JsonView, Field, HealthDot, useAsync } from './ui.jsx'

function Notice({ notice }) { if (!notice) return null; const tone = notice.type === 'error' ? 'border-rose-300 text-rose-700 bg-rose-50' : 'border-sage-300 text-sage-700 bg-sage-50'; return <div className={`wc-badge ${tone} mb-4`}>{notice.text}</div> }
function fmt(ts) { try { return new Date(ts).toLocaleString() } catch { return String(ts || '—') } }

// ---------------------------------------------------------------- Dashboard
export function Dashboard() {
  const d = useAsync(() => api('/dashboard'), [])
  const stats = useAsync(() => api('/stats'), [])
  return (
    <>
      <PageHeader title="Dispatch 成果产出" subtitle="Reports · Templates · Subscribers" actions={<HealthDot base={BASE} />} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="报告" value={stats.data?.reports || 0} tone="primary" />
        <Stat label="已发布" value={stats.data?.published || 0} tone="sage" />
        <Stat label="模板" value={stats.data?.templates || 0} tone="violet" />
        <Stat label="活跃订阅" value={stats.data?.active_subscribers || 0} tone="amber" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <Card title="最近报告">
          <table className="wc-table">
            <thead><tr><th>标题</th><th>状态</th><th>创建</th></tr></thead>
            <tbody>
              {(d.data?.recent_reports || []).map((r) => (
                <tr key={r.id}><td><Link className="text-water-600 underline" to={`/reports/${r.id}`}>{r.title}</Link></td><td><Badge status={r.status}>{r.status}</Badge></td><td className="text-muted">{fmt(r.created_at)}</td></tr>
              ))}
              {(d.data?.recent_reports || []).length === 0 && <tr><td colSpan="3"><Empty title="暂无报告" /></td></tr>}
            </tbody>
          </table>
        </Card>
        <Card title="报告状态分布">
          <div className="space-y-2">
            {Object.entries(d.data?.reports_by_status || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between border border-line rounded-xl px-3 py-2"><Badge status={k}>{k}</Badge><span className="font-display text-lg">{v}</span></div>
            ))}
            {(d.data?.reports_by_status && Object.keys(d.data.reports_by_status).length === 0) && <Empty title="无报告" />}
          </div>
        </Card>
      </div>
    </>
  )
}

// ---------------------------------------------------------------- Reports
export function ReportsPage() {
  const [reloadN, setReloadN] = useState(0)
  const data = useAsync(() => api('/reports'), [reloadN])
  const templates = useAsync(() => api('/templates'), [])
  const [notice, setNotice] = useState(null)
  const [form, setForm] = useState({ id: '', title: '', template_id: '', variables: '{}' })
  const create = async (e) => {
    e.preventDefault()
    let variables = {}
    try { variables = JSON.parse(form.variables || '{}') } catch { setNotice({ type: 'error', text: 'variables 不是合法 JSON' }); return }
    try { await post('/reports', { id: form.id, title: form.title, template_id: form.template_id, variables }); setNotice({ type: 'ok', text: '报告已创建' }); setForm({ id: '', title: '', template_id: '', variables: '{}' }); setReloadN((x) => x + 1) }
    catch (e) { setNotice({ type: 'error', text: e.message }) }
  }
  return (
    <>
      <PageHeader title="报告" subtitle="Reports" actions={<HealthDot base={BASE} />} />
      <Notice notice={notice} />
      <Card title="创建报告">
        <form onSubmit={create} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="wc-label">报告 ID</label><input className="wc-input" required value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} /></div>
          <div><label className="wc-label">标题</label><input className="wc-input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div><label className="wc-label">模板</label>
            <select className="wc-input" value={form.template_id} onChange={(e) => setForm({ ...form, template_id: e.target.value })}>
              <option value="">无模板（空白）</option>{(templates.data?.templates || []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="md:col-span-2"><label className="wc-label">变量 (JSON)</label><textarea className="wc-input" rows={3} value={form.variables} onChange={(e) => setForm({ ...form, variables: e.target.value })} placeholder='{"title":"每日简报","highlights":"…"}' /></div>
          <div className="md:col-span-2"><button className="wc-btn wc-btn-primary" type="submit">创建</button></div>
        </form>
      </Card>
      <Card title="报告列表" className="mt-4">
        {data.loading ? <Spinner /> : (
          <table className="wc-table">
            <thead><tr><th>标题</th><th>状态</th><th>模板</th><th>创建</th><th></th></tr></thead>
            <tbody>
              {(data.data?.reports || []).map((r) => (
                <tr key={r.id}>
                  <td className="font-medium">{r.title}</td><td><Badge status={r.status}>{r.status}</Badge></td>
                  <td className="text-muted">{r.template_id || '—'}</td><td className="text-muted">{fmt(r.created_at)}</td>
                  <td><Link to={`/reports/${r.id}`} className="wc-btn wc-btn-ghost">详情</Link></td>
                </tr>
              ))}
              {(data.data?.reports || []).length === 0 && <tr><td colSpan="5"><Empty title="暂无报告" /></td></tr>}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}

// ---------------------------------------------------------------- Report detail
export function ReportDetail() {
  const { id } = useParams()
  const [reloadN, setReloadN] = useState(0)
  const rep = useAsync(() => api(`/reports/${id}`), [id, reloadN])
  const [notice, setNotice] = useState(null)
  const publish = async () => { try { await post(`/reports/${id}/publish`, {}); setNotice({ type: 'ok', text: '已发布' }); setReloadN((x) => x + 1) } catch (e) { setNotice({ type: 'error', text: e.message }) } }
  const exportAs = async (format) => { try { const r = await post('/exports', { report_id: id, format }); setNotice({ type: 'ok', text: `已导出 ${format}` }) } catch (e) { setNotice({ type: 'error', text: e.message }) } }
  return (
    <>
      <PageHeader title={rep.data?.title || id} subtitle={id} actions={<HealthDot base={BASE} />} />
      <Notice notice={notice} />
      <div className="flex gap-2 mb-4 flex-wrap">
        <button className="wc-btn wc-btn-primary" onClick={publish}>发布</button>
        <button className="wc-btn" onClick={() => exportAs('markdown')}>导出 Markdown</button>
        <button className="wc-btn" onClick={() => exportAs('html')}>导出 HTML</button>
        <button className="wc-btn" onClick={() => exportAs('pdf')}>导出 PDF</button>
      </div>
      {rep.loading ? <Spinner /> : rep.error ? <Empty title={rep.error} /> : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card title="内容" className="lg:col-span-2">
            <pre className="whitespace-pre-wrap text-sm bg-white/70 border border-line rounded-xl p-4 max-h-[520px] overflow-auto">{rep.data.content || '（空）'}</pre>
          </Card>
          <Card title="元数据">
            <div className="grid grid-cols-1 gap-3">
              <Field label="状态"><Badge status={rep.data.status}>{rep.data.status}</Badge></Field>
              <Field label="模板">{rep.data.template_id || '—'}</Field>
              <Field label="创建">{fmt(rep.data.created_at)}</Field>
              <Field label="发布">{fmt(rep.data.published_at)}</Field>
              <Field label="变量"><JsonView value={rep.data.variables} /></Field>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------- Templates
export function TemplatesPage() {
  const [reloadN, setReloadN] = useState(0)
  const data = useAsync(() => api('/templates'), [reloadN])
  const [notice, setNotice] = useState(null)
  const [form, setForm] = useState({ id: '', name: '', description: '', body: '# {{title}}\n\n{{body}}', variables: 'title,body' })
  const create = async (e) => {
    e.preventDefault()
    try { await post('/templates', { id: form.id, name: form.name, description: form.description, body: form.body, variables: form.variables.split(',').map((s) => s.trim()).filter(Boolean) }); setNotice({ type: 'ok', text: '模板已创建' }); setForm({ id: '', name: '', description: '', body: '# {{title}}\n\n{{body}}', variables: 'title,body' }); setReloadN((x) => x + 1) }
    catch (e) { setNotice({ type: 'error', text: e.message }) }
  }
  return (
    <>
      <PageHeader title="模板" subtitle="Report templates" actions={<HealthDot base={BASE} />} />
      <Notice notice={notice} />
      <Card title="创建模板">
        <form onSubmit={create} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="wc-label">模板 ID</label><input className="wc-input" required value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} /></div>
          <div><label className="wc-label">名称</label><input className="wc-input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="wc-label">描述</label><input className="wc-input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="wc-label">{'正文 (支持 {{var}})'}</label><textarea className="wc-input" rows={4} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="wc-label">变量 (逗号)</label><input className="wc-input" value={form.variables} onChange={(e) => setForm({ ...form, variables: e.target.value })} /></div>
          <div className="md:col-span-2"><button className="wc-btn wc-btn-primary" type="submit">创建</button></div>
        </form>
      </Card>
      <Card title="模板列表" className="mt-4">
        {data.loading ? <Spinner /> : (
          <table className="wc-table">
            <thead><tr><th>名称</th><th>变量</th><th>描述</th></tr></thead>
            <tbody>
              {(data.data?.templates || []).map((t) => (
                <tr key={t.id}><td className="font-medium">{t.name}</td><td className="text-muted">{(t.variables || []).join(', ')}</td><td className="text-muted">{t.description}</td></tr>
              ))}
              {(data.data?.templates || []).length === 0 && <tr><td colSpan="3"><Empty title="暂无模板" /></td></tr>}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}

// ---------------------------------------------------------------- Subscribers
export function SubscribersPage() {
  const [reloadN, setReloadN] = useState(0)
  const data = useAsync(() => api('/subscribers'), [reloadN])
  const [notice, setNotice] = useState(null)
  const [form, setForm] = useState({ id: '', name: '', channel: 'slack', endpoint: '' })
  const create = async (e) => {
    e.preventDefault()
    try { await post('/subscribers', form); setNotice({ type: 'ok', text: '订阅者已添加' }); setForm({ id: '', name: '', channel: 'slack', endpoint: '' }); setReloadN((x) => x + 1) }
    catch (e) { setNotice({ type: 'error', text: e.message }) }
  }
  const notify = async (sid) => { try { const r = await post(`/subscribers/${sid}/notify`, {}); setNotice({ type: 'ok', text: r.message }) } catch (e) { setNotice({ type: 'error', text: e.message }) } }
  return (
    <>
      <PageHeader title="订阅者" subtitle="Subscribers & notifications" actions={<HealthDot base={BASE} />} />
      <Notice notice={notice} />
      <Card title="添加订阅者">
        <form onSubmit={create} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="wc-label">ID</label><input className="wc-input" required value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} /></div>
          <div><label className="wc-label">名称</label><input className="wc-input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><label className="wc-label">渠道</label>
            <select className="wc-input" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>
              {['slack', 'email', 'webhook'].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div><label className="wc-label">端点</label><input className="wc-input" required value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} placeholder="#intel-ops / ops@example.com" /></div>
          <div className="md:col-span-2"><button className="wc-btn wc-btn-primary" type="submit">添加</button></div>
        </form>
      </Card>
      <Card title="订阅者列表" className="mt-4">
        {data.loading ? <Spinner /> : (
          <table className="wc-table">
            <thead><tr><th>名称</th><th>渠道</th><th>端点</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {(data.data?.subscribers || []).map((s) => (
                <tr key={s.id}>
                  <td className="font-medium">{s.name}</td><td><Badge tone="violet">{s.channel}</Badge></td>
                  <td className="text-muted">{s.endpoint}</td>
                  <td>{s.active ? <Badge tone="sage">活跃</Badge> : <Badge tone="rose">停用</Badge>}</td>
                  <td><button className="wc-btn wc-btn-ghost" onClick={() => notify(s.id)}>通知</button></td>
                </tr>
              ))}
              {(data.data?.subscribers || []).length === 0 && <tr><td colSpan="5"><Empty title="暂无订阅者" /></td></tr>}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
