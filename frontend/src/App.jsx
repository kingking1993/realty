import { useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { collect } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import ComplexDetail from './pages/ComplexDetail.jsx'
import Feed from './pages/Feed.jsx'
import Drops from './pages/Drops.jsx'

function CollectButton({ job, label }) {
  const [state, setState] = useState('idle') // idle | running | done | fail
  const texts = { idle: label, running: '실행 중…', done: '시작됨 ✓', fail: '실패' }

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
      {texts[state]}
    </button>
  )
}

export default function App() {
  return (
    <>
      <a href="#main" className="skip-link">본문 바로가기</a>
      <nav className="topnav">
        <NavLink to="/" className="brand">REALTY</NavLink>
        <NavLink to="/" end>대시보드</NavLink>
        <NavLink to="/drops">내려간 매물</NavLink>
        <NavLink to="/feed">뉴스·카페</NavLink>
        <span className="spacer" />
        <CollectButton job="listings" label="매물 수집" />
        <CollectButton job="transactions" label="실거래 수집" />
        <CollectButton job="articles" label="뉴스 수집" />
      </nav>
      <main id="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/complex/:id" element={<ComplexDetail />} />
          <Route path="/drops" element={<Drops />} />
          <Route path="/feed" element={<Feed />} />
        </Routes>
      </main>
    </>
  )
}
