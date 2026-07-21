import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort, fmtFloor, sortListings } from '../format.js'
import SortTh from '../components/SortTh.jsx'
import { ChangeTag } from './Dashboard.jsx'

// 1행: 신규·유지·재등록·소멸 / 2행: 인상·인하
const ROW1 = ['신규', '유지', '재등록', '소멸']
const ROW2 = ['인상', '인하']

/** 변동 컬럼 셀 — 소멸은 실거래/재등록 부가정보까지 표시. */
function ChangeCell({ r }) {
  if (r.change === '소멸') {
    if (r.match) {
      return (
        <span className="match-note">
          <span className={`tag ${r.match.confidence}`}>{r.match.confidence}</span>{' '}
          {fmtDateShort(r.match.deal_date)} {fmtPrice(r.match.price)} 거래
        </span>
      )
    }
    if (r.relisted_as) {
      return (
        <span className="tag relist">
          <RefreshCw size={11} strokeWidth={2.2} aria-hidden="true" />
          {fmtDateShort(r.relisted_as.confirm_date || r.relisted_as.first_seen)} 재등록
        </span>
      )
    }
    return <span className="tag REMOVED">소멸</span>
  }
  if (r.change === '재등록') return <span className="tag relist"><RefreshCw size={11} strokeWidth={2.2} aria-hidden="true" />재등록</span>
  if (r.change === '유지') return <span className="muted">유지</span>
  return <ChangeTag change={r.change} />
}

/** 매물 변동 — 전체 매물 목록 + 변동 컬럼. 버튼으로 카테고리 온오프 필터. */
export default function Changes() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState(null) // null=전체, 아니면 해당 카테고리만
  const [sort, setSort] = useState({ col: '등록', dir: 'desc' })

  useEffect(() => {
    getJSON('/api/changes').then(setData).catch(setError)
  }, [])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const { stats, rows } = data
  const shown = sortListings(filter ? rows.filter((r) => r.change === filter) : rows,
    sort.col, sort.dir)

  const Btn = ({ name }) => (
    <button
      className={`catbtn${filter === name ? ' active' : ''}`}
      onClick={() => setFilter((f) => (f === name ? null : name))}
    >
      {name}<span className="n">{stats[name] ?? 0}</span>
    </button>
  )

  return (
    <>
      <div className="page-head"><h1>매물 변동</h1></div>

      <div className="catbtns">
        <div className="catrow">{ROW1.map((n) => <Btn key={n} name={n} />)}</div>
        <div className="catrow">{ROW2.map((n) => <Btn key={n} name={n} />)}</div>
      </div>

      {shown.length === 0 ? (
        <div className="empty">해당 매물이 없습니다.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <SortTh label="등록" col="등록" sort={sort} setSort={setSort} defaultDir="desc" />
                <SortTh label="동/층" col="동층" sort={sort} setSort={setSort} />
                <SortTh label="호가" col="호가" sort={sort} setSort={setSort} num defaultDir="desc" />
                <th>변동</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <td className="muted">{fmtDateShort(r.confirm_date)}</td>
                  <td>{r.dong || '-'} {fmtFloor(r.floor_info)}</td>
                  <td className="num">{fmtPrice(r.price, r.price_monthly)}</td>
                  <td><ChangeCell r={r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
