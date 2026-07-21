import { useEffect, useState } from 'react'
import { RefreshCw, ArrowUp, ArrowDown } from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort, fmtFloor } from '../format.js'

// 1행: 신규·유지·재등록·소멸 / 2행: 인상·인하
const ROW1 = ['신규', '유지', '재등록', '소멸']
const ROW2 = ['인상', '인하']

/** 중개사 중복 게재 수. */
function Dup({ n }) {
  if (!n || n <= 1) return null
  return <span className="muted"> ·중개 {n}곳</span>
}

/** 매물 변동 — 카테고리 버튼으로 한 번에 한 종류 확인. */
export default function Changes() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [cat, setCat] = useState('신규')

  useEffect(() => {
    getJSON('/api/changes').then(setData).catch(setError)
  }, [])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const { stats, categories } = data
  const rows = categories[cat] || []

  const Btn = ({ name }) => (
    <button className={`catbtn${cat === name ? ' active' : ''}`} onClick={() => setCat(name)}>
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

      {rows.length === 0 ? (
        <div className="empty">해당 매물이 없습니다.</div>
      ) : cat === '소멸' ? (
        <RemovedTable rows={rows} />
      ) : cat === '인상' || cat === '인하' ? (
        <PriceTable rows={rows} />
      ) : (
        <ListingTable rows={rows} showRelist={cat === '재등록'} />
      )}
    </>
  )
}

/** 신규·유지·재등록 — 현재 매물 목록. */
function ListingTable({ rows, showRelist }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>등록일</th><th>동/층</th><th className="num">호가</th>
            {showRelist && <th>이전</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="muted">{fmtDateShort(r.confirm_date)}</td>
              <td>{r.dong || '-'} {fmtFloor(r.floor_info)}<Dup n={r.dup_count} /></td>
              <td className="num">{fmtPrice(r.price, r.price_monthly)}</td>
              {showRelist && (
                <td className="muted">
                  {r.relisted_from
                    ? `${fmtDateShort(r.relisted_from.removed_at)} 소멸분`
                    : '-'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 소멸 — 실거래 매칭 / 재등록 표시. */
function RemovedTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>시각</th><th>실거래/재등록</th><th>동/층</th><th className="num">마지막 호가</th></tr>
        </thead>
        <tbody>
          {rows.map((ev) => (
            <tr key={ev.id}>
              <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
              <td>
                {ev.match ? (
                  <span className="match-note">
                    <span className={`tag ${ev.match.confidence}`}>{ev.match.confidence}</span>{' '}
                    {fmtDateShort(ev.match.deal_date)} {fmtPrice(ev.match.price)} 거래 추정
                  </span>
                ) : ev.relisted_as ? (
                  <span className="match-note">
                    <span className="tag relist">
                      <RefreshCw size={11} strokeWidth={2.2} aria-hidden="true" />
                      {fmtDateShort(ev.relisted_as.confirm_date || ev.relisted_as.first_seen)} 재등록
                    </span>
                  </span>
                ) : ev.trade_type === '매매' ? (
                  <span className="muted">매칭 대기</span>
                ) : (
                  <span className="muted">-</span>
                )}
              </td>
              <td>{ev.dong || '-'} {fmtFloor(ev.floor_info)}<Dup n={ev.dup_count} /></td>
              <td className="num">{fmtPrice(ev.old_price ?? ev.price, ev.price_monthly)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 인상·인하 — 가격 변동. */
function PriceTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>시각</th><th>동/층</th><th className="num">호가 변동</th><th className="num">변동폭</th></tr>
        </thead>
        <tbody>
          {rows.map((ev) => (
            <tr key={ev.id}>
              <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
              <td>{ev.dong || '-'} {fmtFloor(ev.floor_info)}<Dup n={ev.dup_count} /></td>
              <td className="num">{fmtPrice(ev.old_price)} → {fmtPrice(ev.new_price)}</td>
              <td className="num">
                {ev.diff < 0 ? (
                  <span className="delta down">
                    <ArrowDown size={12} strokeWidth={2.5} aria-hidden="true" />
                    {fmtPrice(-ev.diff)} ({ev.diff_pct}%)
                  </span>
                ) : (
                  <span className="delta up">
                    <ArrowUp size={12} strokeWidth={2.5} aria-hidden="true" />
                    {fmtPrice(ev.diff)} (+{ev.diff_pct}%)
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
