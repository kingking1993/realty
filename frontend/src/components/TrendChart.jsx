import { useEffect, useRef } from 'react'
import {
  Chart, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip)

const INK = '#000000'
const INK2 = '#525252'
const GRID = '#e5e5e5'
// 색 대신 선 패턴으로 시리즈 구분 (매매=실선, 전세=파선, 월세=점선)
const DASHES = [[], [7, 4], [2, 4]]
const WIDTHS = [2.5, 2, 2]

export default function TrendChart({ chart }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current || !chart) return
    Chart.defaults.font.family = "'JetBrains Mono', monospace"

    const instance = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: chart.labels,
        datasets: chart.series.map((s, i) => ({
          label: s.label,
          data: s.data,
          borderColor: INK,
          backgroundColor: INK,
          borderWidth: WIDTHS[i],
          borderDash: DASHES[i],
          pointRadius: chart.labels.length > 30 ? 0 : 2.5,
          pointHoverRadius: 5,
          pointBackgroundColor: INK,
          spanGaps: true,
          tension: 0,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: {
              color: INK, usePointStyle: false, boxWidth: 28, boxHeight: 0,
              font: { size: 11 },
            },
          },
          tooltip: {
            mode: 'index', intersect: false,
            backgroundColor: INK, titleColor: '#fff', bodyColor: '#fff',
            cornerRadius: 0, borderWidth: 0, padding: 10,
            titleFont: { family: "'JetBrains Mono', monospace" },
            bodyFont: { family: "'JetBrains Mono', monospace" },
          },
        },
        scales: {
          x: { ticks: { color: INK2, maxTicksLimit: 12, font: { size: 10 } },
               grid: { color: GRID, drawTicks: false }, border: { color: INK } },
          y: { beginAtZero: true, ticks: { color: INK2, precision: 0, font: { size: 10 } },
               grid: { color: GRID, drawTicks: false }, border: { color: INK } },
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
