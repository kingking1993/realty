import { useEffect, useRef } from 'react'
import {
  Chart, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip)

// 클린 화이트 팔레트 — 매매=블루, 전세=슬레이트, 월세=앰버
const SERIES_COLORS = ['#2563EB', '#64748B', '#D97706']
const ON_SURFACE_VARIANT = '#6B7280'
const GRID = '#EEF0F2'

export const CHART_DEFAULTS = {
  tooltip: {
    backgroundColor: '#191B1E',
    titleColor: '#F3F4F6',
    bodyColor: '#F3F4F6',
    cornerRadius: 12,
    borderWidth: 0,
    padding: 12,
  },
}

export default function TrendChart({ chart }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current || !chart) return
    Chart.defaults.font.family =
      "Roboto, 'Pretendard Variable', Pretendard, sans-serif"

    const instance = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: chart.labels,
        datasets: chart.series.map((s, i) => ({
          label: s.label,
          data: s.data,
          borderColor: SERIES_COLORS[i],
          backgroundColor: SERIES_COLORS[i],
          borderWidth: 2.5,
          pointRadius: chart.labels.length > 30 ? 0 : 3,
          pointHoverRadius: 5,
          spanGaps: true,
          tension: 0.35,
          borderCapStyle: 'round',
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: {
              color: ON_SURFACE_VARIANT, usePointStyle: true,
              pointStyle: 'circle', boxWidth: 8, boxHeight: 8,
              font: { size: 12, weight: 500 },
            },
          },
          tooltip: { mode: 'index', intersect: false, ...CHART_DEFAULTS.tooltip },
        },
        scales: {
          x: { ticks: { color: ON_SURFACE_VARIANT, maxTicksLimit: 12, font: { size: 11 } },
               grid: { color: GRID, drawTicks: false }, border: { display: false } },
          y: { beginAtZero: true,
               ticks: { color: ON_SURFACE_VARIANT, precision: 0, font: { size: 11 } },
               grid: { color: GRID, drawTicks: false }, border: { display: false } },
        },
      },
    })
    return () => instance.destroy()
  }, [chart])

  return (
    <div className="chart-box">
      <canvas ref={canvasRef} />
    </div>
  )
}
