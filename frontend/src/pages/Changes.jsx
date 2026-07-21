import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  PackagePlus, TrendingDown, TrendingUp, PackageX, CheckCheck,
  ArrowUp, ArrowDown, RefreshCw,
} from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort } from '../format.js'

const DAY_OPTIONS = [7, 30, 90]

function H2Icon({ icon: Icon }) {
  return (
    <span className="h2-icon">
      <Icon size={16} strokeWidth={2.2} aria-hidden="true" />
    </span>
  )
}

/** 중개사 중복 게재 수 표시. */
function DupBadge({ count }) {
  if (!count || count <= 1) return null
  return <span className="muted"> ·중개 {count}곳</span>
}

/** 재등록 추정 배지 — 소멸됐던 같은 세대가 다시 올라온 것으로 보일 때. */
function RelistBadge({ from }) {
  if (!from) return null
  return (
    <span className="tag relist" title="이전에 내려갔던 같은 세대 매물이 다시 등록된 것으로 추정">
      <RefreshCw size={11} strokeWidth={2.2} aria-hidden="true" />재등록 추정
    </span>
  )
}

/** 매물 변동 추적 — 신규 등록 / 가격 변동(인하·인상) / 소멸(실거래 매칭). */
export default function Changes() {
  const [params, setParams] = useSearchParams()
  const days = Number(params.get('days')) || 30
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJSON(`/api/changes?days=${days}`).then(setData).catch(setError)
  }, [days])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const { stats } = data

  return (
    <>
      <div className="page-head">
        <h1>매물 변동</h1>
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
          <span className="label">
            <PackagePlus size={13} strokeWidth={2} aria-hidden="true" />신규
          </span>
          <span className="value">{stats.new}</span>
        </div>
        <div className="stat">
          <span className="label">
            <TrendingDown size={13} strokeWidth={2} aria-hidden="true" />인하
          </span>
          <span className="value">{stats.cut}</span>
        </div>
        <div className="stat">
          <span className="label">
            <TrendingUp size={13} strokeWidth={2} aria-hidden="true" />인상
          </span>
          <span className="value">{stats.raised}</span>
        </div>
        <div className="stat">
          <span className="label">
            <PackageX size={13} strokeWidth={2} aria-hidden="true" />소멸
          </span>
          <span className="value">{stats.removed}</span>
        </div>
        <div className="stat">
          <span className="label">
            <RefreshCw size={13} strokeWidth={2} aria-hidden="true" />재등록
          </span>
          <span className="value">{stats.relisted ?? 0}</span>
        </div>
        <div className="stat">
          <span className="label">
            <CheckCheck size={13} strokeWidth={2} aria-hidden="true" />매칭
          </span>
          <span className="value">{stats.matched}</span>
        </div>
      </div>

      <h2><H2Icon icon={PackagePlus} />신규 등록 매물</h2>
      {data.news.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>등록일</th><th>상태</th><th>동/층</th><th className="num">호가</th>
              </tr>
            </thead>
            <tbody>
              {data.news.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.confirm_date || ev.occurred_at)}</td>
                  <td>
                    {ev.relisted_from
                      ? <RelistBadge from={ev.relisted_from} />
                      : ev.status === 'removed'
                        ? <span className="tag REMOVED">소멸</span>
                        : <span className="tag">유지 중</span>}
                  </td>
                  <td>{ev.dong || '-'} {ev.floor_info}<DupBadge count={ev.dup_count} /></td>
                  <td className="num">{fmtPrice(ev.new_price ?? ev.price, ev.price_monthly)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">최근 {days}일 동안 신규 등록된 매물이 없습니다.</div>
      )}

      <h2><H2Icon icon={TrendingDown} />가격 변동 매물</h2>
      {data.price_changes.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th><th>상태</th><th>동/층</th>
                <th className="num">호가 변동</th><th className="num">변동폭</th>
              </tr>
            </thead>
            <tbody>
              {data.price_changes.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td>
                    {ev.status === 'removed'
                      ? <span className="tag REMOVED">소멸</span>
                      : <span className="tag">유지 중</span>}
                  </td>
                  <td>{ev.dong || '-'} {ev.floor_info}<DupBadge count={ev.dup_count} /></td>
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
      ) : (
        <div className="empty">최근 {days}일 동안 가격이 변동된 매물이 없습니다.</div>
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
                <th>시각</th><th>실거래/재등록</th><th>동/층</th>
                <th className="num">마지막 호가</th>
              </tr>
            </thead>
            <tbody>
              {data.removed.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td>
                    {ev.match ? (
                      <span className="match-note">
                        <span className={`tag ${ev.match.confidence}`}>{ev.match.confidence}</span>{' '}
                        {fmtDateShort(ev.match.deal_date)} {fmtPrice(ev.match.price)}에 거래 추정
                      </span>
                    ) : ev.relisted_as ? (
                      <span className="match-note">
                        <span className="tag relist">
                          <RefreshCw size={11} strokeWidth={2.2} aria-hidden="true" />재등록됨
                        </span>{' '}
                        {fmtDateShort(ev.relisted_as.confirm_date || ev.relisted_as.first_seen)}에 다시 등록
                      </span>
                    ) : ev.trade_type === '매매' ? (
                      <span className="muted">매칭 대기 (신고 지연 최대 30일)</span>
                    ) : (
                      <span className="muted">-</span>
                    )}
                  </td>
                  <td>{ev.dong || '-'} {ev.floor_info}<DupBadge count={ev.dup_count} /></td>
                  <td className="num">{fmtPrice(ev.old_price ?? ev.price, ev.price_monthly)}</td>
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
