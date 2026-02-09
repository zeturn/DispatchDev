import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './ui.jsx'
import { Dashboard, ReportsPage, ReportDetail, TemplatesPage, SubscribersPage } from './pages.jsx'

const nav = [
  { to: '/', label: '仪表盘', end: true },
  { to: '/reports', label: '报告' },
  { to: '/templates', label: '模板' },
  { to: '/subscribers', label: '订阅者' },
]

export default function App() {
  return (
    <Layout brand="Dispatch" nav={nav}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:id" element={<ReportDetail />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/subscribers" element={<SubscribersPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
