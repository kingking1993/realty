import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Newspaper, ArrowUp, ArrowDown, Minus, ArrowRight, Clock, Inbox,
} from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort, fmtFloor, fmtDateTime, SOURCE_LABELS } from '../format.js'
import SourceTag from '../components/SourceTag.jsx'

const TRADE_TYPES = ['매매', '전세', '월세']
const JOB_LABELS = { listings: '매물', transactions: '실거래', articles: '뉴스·카페' }

function Delta({ today, prev }) {
  if (prev === null || prev === undefined) return null
  const diff = today - prev
  if (diff > 0) {
    return <span className="delta up"><ArrowUp size={11} strokeWidth={2.5} aria-hidden="true" />{diff}</span>
  }
  if (diff < 0) {
    return <span className="delta down"><ArrowDown size={11} strokeWidth={2.5} aria-hidden="true" />{-diff}</span>
  }
  return <span className="delta flat"><Minus size={11} strokeWidth={2.5} aria-hidden="true" /></span>
}

function ChangeTag({ change }) {
  if (change === '신규') return <span className="tag NEW">신규</span>
  if (change === '인하') return <span className="tag cut">인하</span>
  if (change === '인상') return <span className="tag raise">인상</span>
  return null
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams()
  const src = params.get('src') || ''
  const topic = params.get('topic') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [sel, setSel] = useState(null) // {cid, tt}

  useEffect(() => {
    getJSON(`/api/dashboard?src=${src}&topic=${topic}`).then(setData).catch(setError)
  }, [src, topic])

  useEffect(() => {
    if (data && data.cards.length && !sel) setSel({ cid: data.cards[0].id, tt: '매매' })
  }, [data, sel])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const setFilter = (next) => {
    const p = {}
    const merged = { src, topic, ...next }
    if (merged.src) p.src = merged.src
    if (merged.topic) p.topic = merged.topic
    setParams(p)
  }

  const card = data.cards.find((c) => c.id === sel?.cid) || data.cards[0]
  const listings = card ? (card.listings[sel?.tt || '매매'] || []) : []

  return (
    <>
      <div className="page-head"><h1>대시보드</h1></div>

      {data.cards.length === 0 && (
        <div className="empty">
          <Inbox size={22} strokeWidth={1.8} aria-hidden="true" /><br />
          등록된 단지가 없습니다. <code>complexes.yaml</code>에 단지를 추가한 뒤
          상단의 "매물 수집" 버튼을 누르세요.
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
                const active = sel?.cid === c.id && sel?.tt === tt
                return (
                  <button
                    className={`item${active ? ' active' : ''}`}
                    key={tt}
                    onClick={() => setSel({ cid: c.id, tt })}
                  >
                    <span className="label">{tt}</span>
                    <span className="value">{today}<Delta today={today} prev={prev} /></span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {card && (
        <>
          <h2>{card.name} · {sel?.tt || '매매'} 현황 <span className="muted">{listings.length}건</span></h2>
          {listings.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>동/층</th><th className="num">호가</th><th>변동</th></tr>
                </thead>
                <tbody>
                  {listings.map((l) => (
                    <tr key={l.id}>
                      <td>{l.dong || '-'} {fmtFloor(l.floor_info)}
                        {l.dup_count > 1 && <span className="muted"> ·중개 {l.dup_count}곳</span>}
                      </td>
                      <td className="num">{fmtPrice(l.price, l.price_monthly)}</td>
                      <td><ChangeTag change={l.change} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">현재 {sel?.tt || '매매'} 매물이 없습니다.</div>
          )}
        </>
      )}

      <h2>
        <span className="h2-icon"><Newspaper size={16} strokeWidth={2.2} aria-hidden="true" /></span>
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
              전체 보기<ArrowRight size={16} strokeWidth={2} aria-hidden="true" />
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
              <>{fmtDateTime(log.started_at)}{!log.ok && <span className="fail"> (일부 실패)</span>}</>
            ) : '없음'}
          </div>
        ))}
      </div>
    </>
  )
}
