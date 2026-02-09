import { fetchJson } from './ui.jsx'

// Real Dispatch API. In dev, /api is proxied to :8203.
export const BASE = import.meta.env.VITE_API_BASE || '/api'
export const api = (path, options) => fetchJson(BASE + path, options)
export const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) })
