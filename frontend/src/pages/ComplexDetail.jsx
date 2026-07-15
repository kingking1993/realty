import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  LineChart, Tag, History, TrendingUp, Receipt,
  Layers, ArrowDownToLine, ArrowUpToLine, Sigma,
} from 'lucide-react'
import { getJSON } from '../api.js'
import { fmtPrice, fmtDateShort, EVENT_LABELS } from '../format.js'
import TrendChart from '../components/TrendChart.jsx'
import TransactionChart from '../components/TransactionChart.jsx'

const TRADE_TYPES = ['매매', '전세', '월세']

function H2Icon({ icon: Icon }) {
  return (
    <span className="h2-icon">
      <Icon size={18} strokeWidth={2.2} aria-hidden="true" />
    </span>
  )
}

/** 호가현황 요약 — 현재 매물의 최저/평균/최고 호가. */
function AskingStats({ listings, tradeType }) {
  const prices = listings.map((l) => l.price).filter((p) => p > 0)
  if (!prices.length) return null
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const avg = Math.round(prices.reduce((a, b) => a + b, 0) / prices.length)
  return (
    <div className="stats">
      <div className="stat hero">
        <div className="label">
          <Layers size={14} strokeWidth={2} aria-hidden="true" />{tradeType} 매물
        </div>
        <div className="value">{listings.length}건</div>
      </div>
      <div className="stat">
        <div className="label">
          <ArrowDownToLine size={14} strokeWidth={2} aria-hidden="true" />최저 호가
        </div>
        <div className="value">{fmtPrice(min)}</div>
      </div>
      <div className="stat">
        <div className="label">
          <Sigma size={14} strokeWidth={2} aria-hidden="true" />평균 호가
        </div>
        <div className="value">{fmtPrice(avg)}</div>
      </div>
      <div className="stat">
        <div className="label">
          <ArrowUpToLine size={14} strokeWidth={2} aria-hidden="true" />최고 호가
        </div>
        <div className="value">{fmtPrice(max)}</div>
      </div>
    </div>
  )
}

export default function ComplexDetail() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const tradeType = params.get('trade_type') || '매매'
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJSON(`/api/complex/${id}?trade_type=${encodeURIComponent(tradeType)}`)
      .then(setData).catch(setError)
  }, [id, tradeType])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  return (
    <>
      <div className="page-head">
        <div className="kicker"><Link to="/">대시보드</Link> · 단지 상세</div>
        <h1>{data.complex.name}</h1>
      </div>

      <h2><H2Icon icon={LineChart} />매물 수 추이 (최근 90일)</h2>
      <TrendChart chart={data.chart} />

      <h2><H2Icon icon={Tag} />호가현황 · 현재 매물</h2>
      <div className="filters">
        {TRADE_TYPES.map((tt) => (
          <button
            key={tt}
            className={tradeType === tt ? 'active' : ''}
            onClick={() => setParams({ trade_type: tt })}
          >
            {tt}
          </button>
        ))}
      </div>
      <AskingStats listings={data.listings} tradeType={tradeType} />
      {data.listings.length ? (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>동</th><th>층</th><th className="num">가격(호가)</th>
                  <th>설명</th><th className="num">중개</th><th className="num">등록</th>
                </tr>
              </thead>
              <tbody>
                {data.listings.map((l) => (
                  <tr key={l.id}>
                    <td>{l.dong || '-'}</td>
                    <td>{l.floor_info || '-'}</td>
                    <td className="num">{fmtPrice(l.price, l.price_monthly)}</td>
                    <td className="muted desc">{(l.description || '').slice(0, 40)}</td>
                    <td className="num muted">{l.dup_count > 1 ? `${l.dup_count}곳` : '-'}</td>
                    <td className="num muted">{fmtDateShort(l.first_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">{tradeType} {data.listings.length}건</p>
        </>
      ) : (
        <div className="empty">{tradeType} 매물이 없습니다 (또는 아직 수집 전).</div>
      )}

      <h2><H2Icon icon={History} />매물 변동 로그</h2>
      {data.events.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th><th>변동</th><th>유형</th><th>동/층</th>
                <th className="num">가격</th><th>실거래 매칭</th>
              </tr>
            </thead>
            <tbody>
              {data.events.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{fmtDateShort(ev.occurred_at)}</td>
                  <td><span className={`tag ${ev.event}`}>{EVENT_LABELS[ev.event]}</span></td>
                  <td>{ev.trade_type}</td>
                  <td>{ev.dong || '-'} {ev.floor_info}</td>
                  <td className="num">
                    {ev.event === 'PRICE_CHANGED'
                      ? `${fmtPrice(ev.old_price)} → ${fmtPrice(ev.new_price)}`
                      : fmtPrice(ev.new_price ?? ev.old_price ?? ev.price)}
                  </td>
                  <td>
                    {ev.match ? (
                      <span className="match-note">
                        <span className={`tag ${ev.match.confidence}`}>{ev.match.confidence}</span>{' '}
                        {fmtDateShort(ev.match.deal_date)} {fmtPrice(ev.match.price)}에 거래 추정
                        ({ev.match.floor}층{ev.match.apt_dong ? `, ${ev.match.apt_dong}동` : ''})
                      </span>
                    ) : ev.event === 'REMOVED' && ev.trade_type === '매매' ? (
                      <span className="muted">매칭 대기 (신고 지연 최대 30일)</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">아직 변동 로그가 없습니다.</div>
      )}

      <h2><H2Icon icon={TrendingUp} />실거래가 변화 (매매)</h2>
      <TransactionChart transactions={data.transactions} />

      <h2><H2Icon icon={Receipt} />실거래 내역 (매매)</h2>
      {data.transactions.length ? (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>계약일</th><th>동</th><th className="num">층</th>
                  <th className="num">거래가</th><th>비고</th>
                </tr>
              </thead>
              <tbody>
                {data.transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{fmtDateShort(t.deal_date)}</td>
                    <td>{t.apt_dong || '-'}</td>
                    <td className="num">{t.floor}</td>
                    <td className="num">{fmtPrice(t.price)}</td>
                    <td>
                      {t.is_canceled && <span className="tag REMOVED">해제</span>}
                      {t.matched && <span className="muted"> 소멸 매물과 매칭됨</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            ※ 소멸 매물↔실거래 매칭은 면적·층·동·시기·가격 기반의 <strong>추정</strong>입니다.
          </p>
        </>
      ) : (
        <div className="empty">아직 실거래 데이터가 없습니다.</div>
      )}
    </>
  )
}
