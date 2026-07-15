/** 표시용 포맷터 — 서버 필터(price, d)를 프론트로 이전. */

/** 만원 → '12.5억' 표기 (한 줄 고정용 축약형). */
export function fmtPrice(price, monthly = 0) {
  if (!price || price <= 0) return '-'
  let s = price >= 10000
    ? `${parseFloat((price / 10000).toFixed(4))}억`
    : price.toLocaleString()
  if (monthly) s += `/${monthly.toLocaleString()}`
  return s
}

/** ISO 날짜/일시 → '7/13' 표기. */
export function fmtDateShort(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** ISO → 'YYYY-MM-DD'. */
export function fmtDate(iso) {
  return iso ? iso.slice(0, 10) : '-'
}

/** ISO → 'YYYY-MM-DD HH:MM'. */
export function fmtDateTime(iso) {
  return iso ? iso.slice(0, 16).replace('T', ' ') : '-'
}

export const EVENT_LABELS = { NEW: '신규', PRICE_CHANGED: '가격변동', REMOVED: '소멸' }
export const SOURCE_LABELS = { news: '뉴스', cafe: '카페', blind: 'Blind' }
