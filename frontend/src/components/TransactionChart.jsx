import { useEffect, useRef } from 'react'
import {
  Chart, ScatterController, LineController, LineElement, PointElement,
  TimeScale, CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js'
import { fmtPrice } from '../format.js'
import { CHART_DEFAULTS } from './TrendChart.jsx'

Chart.register(ScatterController, LineController, LineElement, PointElement,
  TimeScale, CategoryScale, LinearScale, Legend, Tooltip)

const PRIMARY = '#6750A4'
const TERTIARY = '#7D5260'
const ON_SURFACE_VARIANT = '#49454F'
const GRID = '#E7E0EC'

/** 실거래가 변화 — 개별 거래 산점 + 월평균 추세선. */
export default function TransactionChart({ transactions }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current) return
    const valid = transactions
      .filter((t) => !t.is_canceled && t.price > 0)
      .sort((a, b) => a.deal_date.localeCompare(b.deal_date))
    if (!valid.length) return

    // 월별 평균
    const byMonth = new Map()
    for (const t of valid) {
      const m = t.deal_date.slice(0, 7)
      if (!byMonth.has(m)) byMonth.set(m, [])
      byMonth.get(m).push(t.price)
    }
    const months = [...byMonth.keys()].sort()
    const avgSeries = months.map((m) => {
      const arr = byMonth.get(m)
      return { x: `${m}-15`, y: Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) }
    })

    const instance = new Chart(canvasRef.current, {
      data: {
        datasets: [
          {
            type: 'scatter',
            label: '개별 거래',
            data: valid.map((t) => ({ x: t.deal_date, y: t.price })),
            backgroundColor: `${PRIMARY}59`, /* 35% */
            borderColor: PRIMARY,
            borderWidth: 1,
            pointRadius: 5,
            pointHoverRadius: 7,
          },
          {
            type: 'line',
            label: '월평균',
            data: avgSeries,
            borderColor: TERTIARY,
            backgroundColor: TERTIARY,
            borderWidth: 2.5,
            pointRadius: 3,
            tension: 0.35,
            borderCapStyle: 'round',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: true,
        plugins: {
          legend: {
            labels: {
              color: ON_SURFACE_VARIANT, usePointStyle: true,
              pointStyle: 'circle', boxWidth: 8, boxHeight: 8,
              font: { size: 12, weight: 500 },
            },
          },
          tooltip: {
            ...CHART_DEFAULTS.tooltip,
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${fmtPrice(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            type: 'category',
            labels: [...new Set([...valid.map((t) => t.deal_date), ...avgSeries.map((p) => p.x)])].sort(),
            ticks: {
              color: ON_SURFACE_VARIANT, maxTicksLimit: 10, font: { size: 11 },
              callback: function (v) { return String(this.getLabelForValue(v)).slice(0, 7) },
            },
            grid: { color: GRID, drawTicks: false }, border: { display: false },
          },
          y: {
            ticks: {
              color: ON_SURFACE_VARIANT, font: { size: 11 },
              callback: (v) => fmtPrice(v),
            },
            grid: { color: GRID, drawTicks: false }, border: { display: false },
          },
        },
      },
    })
    return () => instance.destroy()
  }, [transactions])

  const hasData = transactions.some((t) => !t.is_canceled && t.price > 0)
  if (!hasData) return <div className="empty">아직 실거래 데이터가 없습니다.</div>

  return (
    <div className="chart-box">
      <canvas ref={canvasRef} />
    </div>
  )
}
