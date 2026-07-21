import { useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import {
  Building2, LayoutDashboard, ArrowUpDown, Newspaper,
  House, Receipt, Loader2, Check, X,
} from 'lucide-react'
import { collect } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import ComplexDetail from './pages/ComplexDetail.jsx'
import Feed from './pages/Feed.jsx'
import Changes from './pages/Changes.jsx'

const JOB_ICONS = { listings: House, transactions: Receipt, articles: Newspaper }

function CollectButton({ job, label }) {
  const [state, setState] = useState('idle') // idle | running | done | fail
  const texts = { idle: label, running: '실행 중…', done: '시작됨', fail: '실패' }
  const Idle = JOB_ICONS[job]
  const icons = {
    idle: <Idle size={16} strokeWidth={2} aria-hidden="true" />,
    running: <Loader2 size={16} strokeWidth={2} className="spin" aria-hidden="true" />,
    done: <Check size={16} strokeWidth={2} aria-hidden="true" />,
    fail: <X size={16} strokeWidth={2} aria-hidden="true" />,
  }

  async function run() {
    setState('running')
    try {
      await collect(job)
      setState('done')
    } catch {
      setState('fail')
    }
    setTimeout(() => setState('idle'), 4000)
  }

  return (
    <button className="btn" disabled={state !== 'idle'} onClick={run}>
      {icons[state]}
      {texts[state]}
    </button>
  )
}

export default function App() {
  return (
    <>
      <a href="#main" className="skip-link">본문 바로가기</a>
      <nav className="topnav">
        <div className="nav-tabs">
          <NavLink to="/" className="brand">
            <Building2 size={18} strokeWidth={2.2} aria-hidden="true" />
            REALTY
          </NavLink>
          <NavLink to="/" end>
            <LayoutDashboard size={14} strokeWidth={2} aria-hidden="true" />
            대시보드
          </NavLink>
          <NavLink to="/changes">
            <ArrowUpDown size={14} strokeWidth={2} aria-hidden="true" />
            매물 변동
          </NavLink>
          <NavLink to="/feed">
            <Newspaper size={14} strokeWidth={2} aria-hidden="true" />
            뉴스·카페
          </NavLink>
        </div>
        <div className="nav-actions">
          <CollectButton job="listings" label="매물 수집" />
          <CollectButton job="transactions" label="실거래 수집" />
          <CollectButton job="articles" label="뉴스 수집" />
        </div>
      </nav>
      <main id="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/complex/:id" element={<ComplexDetail />} />
          <Route path="/changes" element={<Changes />} />
          <Route path="/drops" element={<Navigate to="/changes" replace />} />
          <Route path="/feed" element={<Feed />} />
        </Routes>
      </main>
    </>
  )
}
