import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Activity, Newspaper, ArrowUp, ArrowDown, Minus,
  ArrowRight, Clock, Inbox,
} from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort, fmtDateTime, EVENT_LABELS, SOURCE_LABELS } from '../format.js'
import SourceTag from '../components/SourceTag.jsx'

const TRADE_TYPES = ['매매', '전세', '월세']
const JOB_LABELS = { listings: '매물', transactions: '실거래', articles: '뉴스·카페' }

function Delta({ today, prev }) {
  if (prev === null || prev === undefined) return null
  const diff = today - prev
  if (diff > 0) {
    return (
      <span className="delta up">
        <ArrowUp size={12} strokeWidth={2.5} aria-hidden="true" />{diff}
      </span>
    )
  }
  if (diff < 0) {
    return (
      <span className="delta down">
        <ArrowDown size={12} strokeWidth={2.5} aria-hidden="true" />{-diff}
      </span>
    )
  }
  return (
    <span className="delta flat">
      <Minus size={12} strokeWidth={2.5} aria-hidden="true" />
    </span>
  )
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams()
  const src = params.get('src') || ''
  const topic = params.get('topic') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJSON(`/api/dashboard?src=${src}&topic=${topic}`).then(setData).catch(setError)
  }, [src, topic])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const setFilter = (next) => {
    const p = {}
    const merged = { src, topic, ...next }
    if (merged.src) p.src = merged.src
    if (merged.topic) p.topic = merged.topic
    setParams(p)
  }

  return (
    <>
      <div className="page-head">
        <h1>대시보드</h1>
      </div>

      {data.cards.length === 0 && (
        <div className="empty">
          <Inbox size={22} strokeWidth={1.8} aria-hidden="true" /><br />
          등록된 단지가 없습니다. <code>complexes.yaml</code>에 단지를 추가한 뒤
          상단의 "매물 수집" 버튼을 누르거나 <code>python scripts/collect_now.py</code>를 실행하세요.
        </div>
      )}

      <div className="cards">
        {data.cards.map((c) => (
          <div className="card" key={c.id}>
            <Link className="name" to={`/complex/${c.id}`}>{c.name}</Link>
            {c.as_of && <span className="asof">{c.as_of} 기준</span>}
            <div className="countrow">
              {TRADE_TYPES.map((tt) => {
                const [today, prev] = c.counts[tt]
                return (
                  <div className="item" key={tt}>
                    <div className="label">{tt}</div>
                    <div className="value">
                      {today}
                      <Delta today={today} prev={prev} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <h2>
        <span className="h2-icon"><Activity size={18} strokeWidth={2.2} aria-hidden="true" /></span>
        최근 매물 변동
      </h2>
      {data.events.length ? (
        <>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th><th>단지</th><th>변동</th><th>유형</th><th>동/층</th>
                <th className="num">가격</th>
              </tr>
            </thead>
            <tbody>
              {data.events.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td><Link to={`/complex/${ev.complex.id}`}>{ev.complex.name}</Link></td>
                  <td><span className={`tag ${ev.event}`}>{EVENT_LABELS[ev.event]}</span></td>
                  <td>{ev.trade_type}</td>
                  <td>{ev.dong || '-'} {ev.floor_info}</td>
                  <td className="num">
                    {ev.event === 'PRICE_CHANGED'
                      ? `${fmtPrice(ev.old_price)} → ${fmtPrice(ev.new_price)}`
                      : fmtPrice(ev.new_price ?? ev.old_price ?? ev.price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          <Link className="more-link" to="/changes">
            매물 변동 전체 보기
            <ArrowRight size={16} strokeWidth={2} aria-hidden="true" />
          </Link>
        </p>
        </>
      ) : (
        <div className="empty">아직 수집된 매물 변동이 없습니다.</div>
      )}

      <h2>
        <span className="h2-icon"><Newspaper size={18} strokeWidth={2.2} aria-hidden="true" /></span>
        최신 소식
      </h2>
      <div className="filter-row">
        <div className="filters">
          <button className={!src ? 'active' : ''} onClick={() => setFilter({ src: '' })}>전체</button>
          {Object.entries(SOURCE_LABELS).map(([k, label]) => (
            <button key={k} className={src === k ? 'active' : ''} onClick={() => setFilter({ src: k })}>
              {label}
            </button>
          ))}
        </div>
        <div className="filters">
          <button className={!topic ? 'active' : ''} onClick={() => setFilter({ topic: '' })}>전체</button>
          <button className={topic === 'complex' ? 'active' : ''} onClick={() => setFilter({ topic: 'complex' })}>
            {data.topic_labels.complex}
          </button>
          <button className={topic === 'area' ? 'active' : ''} onClick={() => setFilter({ topic: 'area' })}>
            {data.topic_labels.area}
          </button>
        </div>
      </div>

      {data.articles.length ? (
        <>
          {data.articles.map((a) => (
            <div className="feeditem" key={a.id}>
              <SourceTag source={a.source} />
              <a className="title" href={a.link} target="_blank" rel="noopener noreferrer">{a.title}</a>
              <div className="meta">
                {a.keyword} · {a.pub_date ? a.pub_date.slice(0, 10) : `수집 ${fmtDateShort(a.fetched_at)}`}
              </div>
            </div>
          ))}
          <p>
            <Link className="more-link" to={`/feed?source=${src}&topic=${topic}`}>
              전체 보기
              <ArrowRight size={16} strokeWidth={2} aria-hidden="true" />
            </Link>
          </p>
        </>
      ) : (
        <div className="empty">이 조건의 글이 아직 없습니다.</div>
      )}

      <div className="joblog">
        {Object.entries(data.logs).map(([job, log]) => (
          <div key={job}>
            <Clock size={13} strokeWidth={2} aria-hidden="true" />
            {JOB_LABELS[job]} 마지막 수집:{' '}
            {log ? (
              <>
                {fmtDateTime(log.started_at)}
                {!log.ok && <span className="fail"> (일부 실패)</span>}
              </>
            ) : '없음'}
          </div>
        ))}
      </div>
    </>
  )
}
