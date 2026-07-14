import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  TrendingDown, Percent, PackageX, CheckCheck,
} from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort } from '../format.js'

const DAY_OPTIONS = [7, 30, 90]

function H2Icon({ icon: Icon }) {
  return (
    <span className="h2-icon">
      <Icon size={18} strokeWidth={2.2} aria-hidden="true" />
    </span>
  )
}

/** 내려간 매물 추적 — 가격 인하 + 소멸(실거래 매칭). */
export default function Drops() {
  const [params, setParams] = useSearchParams()
  const days = Number(params.get('days')) || 30
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJSON(`/api/drops?days=${days}`).then(setData).catch(setError)
  }, [days])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const totalCut = data.cuts.length
  const avgCutPct = totalCut
    ? (data.cuts.reduce((a, c) => a + (c.cut_pct || 0), 0) / totalCut).toFixed(1)
    : null
  const matchedCount = data.removed.filter((r) => r.match).length

  return (
    <>
      <div className="page-head">
        <div className="kicker">Realty · 하락 신호 추적</div>
        <h1>내려간 매물</h1>
      </div>

      <div className="filters">
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            className={days === d ? 'active' : ''}
            onClick={() => setParams({ days: String(d) })}
          >
            최근 {d}일
          </button>
        ))}
      </div>

      <div className="stats">
        <div className="stat hero">
          <div className="label">
            <TrendingDown size={14} strokeWidth={2} aria-hidden="true" />가격 인하
          </div>
          <div className="value">{totalCut}건</div>
        </div>
        <div className="stat">
          <div className="label">
            <Percent size={14} strokeWidth={2} aria-hidden="true" />평균 인하율
          </div>
          <div className="value">{avgCutPct !== null ? `-${avgCutPct}%` : '-'}</div>
        </div>
        <div className="stat">
          <div className="label">
            <PackageX size={14} strokeWidth={2} aria-hidden="true" />소멸 매물
          </div>
          <div className="value">{data.removed.length}건</div>
        </div>
        <div className="stat">
          <div className="label">
            <CheckCheck size={14} strokeWidth={2} aria-hidden="true" />실거래 매칭
          </div>
          <div className="value">{matchedCount}건</div>
        </div>
      </div>

      <h2><H2Icon icon={TrendingDown} />가격 인하 매물</h2>
      {data.cuts.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th><th>단지</th><th>유형</th><th>동/층</th>
                <th className="num">호가 변동</th><th className="num">인하폭</th><th>상태</th>
              </tr>
            </thead>
            <tbody>
              {data.cuts.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td><Link to={`/complex/${ev.complex.id}`}>{ev.complex.name}</Link></td>
                  <td>{ev.trade_type}</td>
                  <td>{ev.dong || '-'} {ev.floor_info}</td>
                  <td className="num">{fmtPrice(ev.old_price)} → {fmtPrice(ev.new_price)}</td>
                  <td className="num">
                    <span className="delta down">
                      -{fmtPrice(ev.cut)}{ev.cut_pct != null ? ` (-${ev.cut_pct}%)` : ''}
                    </span>
                  </td>
                  <td>
                    {ev.status === 'removed'
                      ? <span className="tag REMOVED">소멸</span>
                      : <span className="tag">유지 중</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">최근 {days}일 동안 가격이 내려간 매물이 없습니다.</div>
      )}

      <h2><H2Icon icon={PackageX} />소멸 매물</h2>
      <p className="muted">
        호가에서 사라진 매물입니다. 매매의 경우 실거래 신고와 매칭해 실제 거래 여부를 추정합니다.
      </p>
      {data.removed.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th><th>단지</th><th>유형</th><th>동/층</th>
                <th className="num">마지막 호가</th><th>실거래 매칭</th>
              </tr>
            </thead>
            <tbody>
              {data.removed.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td><Link to={`/complex/${ev.complex.id}`}>{ev.complex.name}</Link></td>
                  <td>{ev.trade_type}</td>
                  <td>{ev.dong || '-'} {ev.floor_info}</td>
                  <td className="num">{fmtPrice(ev.old_price ?? ev.price)}</td>
                  <td>
                    {ev.match ? (
                      <span className="match-note">
                        <span className={`tag ${ev.match.confidence}`}>{ev.match.confidence}</span>{' '}
                        {fmtDateShort(ev.match.deal_date)} {fmtPrice(ev.match.price)}에 거래 추정
                      </span>
                    ) : ev.trade_type === '매매' ? (
                      <span className="muted">매칭 대기 (신고 지연 최대 30일)</span>
                    ) : (
                      <span className="muted">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">최근 {days}일 동안 소멸된 매물이 없습니다.</div>
      )}
    </>
  )
}
