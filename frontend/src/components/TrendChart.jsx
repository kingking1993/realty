import { useEffect, useRef } from 'react'
import {
  Chart, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip)

// MD3 토널 팔레트 — 매매=primary, 전세=tertiary, 월세=teal(보조 하모니)
const SERIES_COLORS = ['#6750A4', '#7D5260', '#006A6A']
const ON_SURFACE_VARIANT = '#49454F'
const GRID = '#E7E0EC'

export const CHART_DEFAULTS = {
  tooltip: {
    backgroundColor: '#1C1B1F',
    titleColor: '#F3EDF7',
    bodyColor: '#F3EDF7',
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
