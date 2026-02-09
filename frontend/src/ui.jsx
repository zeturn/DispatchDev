import React, { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'

export function fetchJson(url, options) {
  return fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  }).then(async (r) => {
    let body = null
    try { body = await r.json() } catch { /* no body */ }
    if (!r.ok) throw new Error((body && (body.error || body.detail)) || `${r.status} ${r.statusText}`)
    return body
  })
}

export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    Promise.resolve(fn())
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((e) => alive && setState({ loading: false, data: null, error: e?.message || String(e) }))
    return () => { alive = false }
    // eslint-disable-next-line
  }, deps)
  return state
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3 text-muted py-10 justify-center">
      <span className="h-4 w-4 rounded-full border-2 border-water-400 border-t-transparent animate-spin" />
      <span className="text-sm">{label || '加载中…'}</span>
    </div>
  )
}

export function Empty({ title, hint, children }) {
  return (
    <div className="wc-card text-center py-12">
      <div className="text-muted text-sm">{title || '暂无数据'}</div>
      {hint && <div className="text-muted/70 text-xs mt-1">{hint}</div>}
      {children && <div className="mt-4 flex justify-center gap-2">{children}</div>}
    </div>
  )
}

const STATUS_COLORS = {
  ok: 'border-sage-300 text-sage-700 bg-sage-50',
  ready: 'border-sage-300 text-sage-700 bg-sage-50',
  success: 'border-sage-300 text-sage-700 bg-sage-50',
  succeeded: 'border-sage-300 text-sage-700 bg-sage-50',
  published: 'border-sage-300 text-sage-700 bg-sage-50',
  active: 'border-water-300 text-water-700 bg-water-50',
  running: 'border-water-300 text-water-700 bg-water-50',
  monitoring: 'border-water-300 text-water-700 bg-water-50',
  planned: 'border-water-300 text-water-700 bg-water-50',
  pending: 'border-amber-300 text-amber-700 bg-amber-50',
  waiting: 'border-amber-300 text-amber-700 bg-amber-50',
  needs_repair: 'border-amber-300 text-amber-700 bg-amber-50',
  warn: 'border-amber-300 text-amber-700 bg-amber-50',
  failed: 'border-rose-300 text-rose-700 bg-rose-50',
  error: 'border-rose-300 text-rose-700 bg-rose-50',
  rejected: 'border-rose-300 text-rose-700 bg-rose-50',
  quarantined: 'border-rose-300 text-rose-700 bg-rose-50',
  cancelled: 'border-rose-300 text-rose-700 bg-rose-50',
  draft: 'border-line text-muted bg-white/60',
}

export function Badge({ children, tone, status }) {
  const cls = status
    ? STATUS_COLORS[String(status).toLowerCase()] || STATUS_COLORS.draft
    : tone === 'primary' ? 'border-water-300 text-water-700 bg-water-50'
    : tone === 'rose' ? 'border-rose-300 text-rose-700 bg-rose-50'
    : tone === 'sage' ? 'border-sage-300 text-sage-700 bg-sage-50'
    : tone === 'amber' ? 'border-amber-300 text-amber-700 bg-amber-50'
    : tone === 'violet' ? 'border-violet-300 text-violet-700 bg-violet-50'
    : 'border-line text-muted bg-white/60'
  return <span className={`wc-badge ${cls}`}>{children}</span>
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-6 flex-wrap">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        {subtitle && <p className="text-muted text-sm mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2 flex-wrap">{actions}</div>}
    </div>
  )
}

export function Card({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`wc-card ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="text-muted text-xs mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, hint, tone }) {
  const ring = tone === 'primary' ? 'border-water-200'
    : tone === 'sage' ? 'border-sage-200'
    : tone === 'amber' ? 'border-amber-200'
    : tone === 'rose' ? 'border-rose-200'
    : tone === 'violet' ? 'border-violet-200' : 'border-line'
  return (
    <div className={`wc-card border ${ring}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="text-3xl font-display font-semibold mt-2 text-ink">{value}</div>
      {hint && <div className="text-xs text-muted mt-1">{hint}</div>}
    </div>
  )
}

export function JsonView({ value }) {
  return (
    <pre className="text-xs leading-relaxed bg-ink text-paper rounded-xl p-4 overflow-auto max-h-[460px] border border-line">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="text-sm text-ink mt-0.5 break-words">{children}</div>
    </div>
  )
}

export function HealthDot({ base }) {
  const { data, error } = useAsync(() => fetchJson(base + '/health'), [])
  const ok = data && data.status === 'ok'
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <span className={`h-2.5 w-2.5 rounded-full border ${error ? 'bg-rose-400 border-rose-500' : ok ? 'bg-sage-400 border-sage-500' : 'bg-amber-400 border-amber-500'}`} />
      {error ? '离线' : ok ? '在线' : '检测中'}
    </span>
  )
}

export function Layout({ brand, nav, children }) {
  return (
    <div className="min-h-full flex">
      <aside className="w-64 shrink-0 border-r border-line bg-white/60 backdrop-blur p-4 sticky top-0 h-screen overflow-y-auto">
        <div className="font-display text-xl font-semibold text-ink px-2 mb-1">{brand}</div>
        <div className="px-2 text-xs text-muted mb-6">Control Plane</div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              className={({ isActive }) => `wc-nav ${isActive ? 'wc-nav-active' : ''}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <main className="flex-1 p-6 w-full">{children}</main>
      </div>
    </div>
  )
}
