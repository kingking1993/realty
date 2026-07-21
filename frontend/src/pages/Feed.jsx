import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getJSON } from '../api.js'
import { fmtDateShort, SOURCE_LABELS } from '../format.js'
import SourceTag from '../components/SourceTag.jsx'

export default function Feed() {
  const [params, setParams] = useSearchParams()
  const source = params.get('source') || ''
  const topic = params.get('topic') || ''
  const complexId = params.get('complex_id') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJSON(`/api/feed?source=${source}&topic=${topic}&complex_id=${complexId || 0}`)
      .then(setData).catch(setError)
  }, [source, topic, complexId])

  if (error) return <div className="empty">불러오기 실패: {String(error.message || error)}</div>
  if (!data) return <div className="empty">불러오는 중…</div>

  const setFilter = (next) => {
    const merged = { source, topic, complex_id: complexId, ...next }
    const p = {}
    if (merged.source) p.source = merged.source
    if (merged.topic) p.topic = merged.topic
    if (merged.complex_id) p.complex_id = merged.complex_id
    setParams(p)
  }

  return (
    <>
      <div className="page-head">
        <h1>뉴스·카페</h1>
      </div>

      <div className="filters">
        <button className={!source ? 'active' : ''} onClick={() => setFilter({ source: '' })}>전체</button>
        {Object.entries(SOURCE_LABELS).map(([k, label]) => (
          <button key={k} className={source === k ? 'active' : ''} onClick={() => setFilter({ source: k })}>
            {label}
          </button>
        ))}
      </div>
      <div className="filters">
        <button className={!topic ? 'active' : ''} onClick={() => setFilter({ topic: '' })}>전체 주제</button>
        <button className={topic === 'complex' ? 'active' : ''} onClick={() => setFilter({ topic: 'complex' })}>
          {data.topic_labels.complex}
        </button>
        <button className={topic === 'area' ? 'active' : ''} onClick={() => setFilter({ topic: 'area' })}>
          {data.topic_labels.area}
        </button>
      </div>
      <div className="filters">
        <button className={!complexId ? 'active' : ''} onClick={() => setFilter({ complex_id: '' })}>
          모든 단지
        </button>
        {data.complexes.map((cx) => (
          <button
            key={cx.id}
            className={complexId === String(cx.id) ? 'active' : ''}
            onClick={() => setFilter({ complex_id: String(cx.id) })}
          >
            {cx.name}
          </button>
        ))}
      </div>

      {data.articles.length ? (
        data.articles.map((a) => (
          <div className="feeditem" key={a.id}>
            <SourceTag source={a.source} />
            <a className="title" href={a.link} target="_blank" rel="noopener noreferrer">{a.title}</a>
            {a.description && <div className="desc">{a.description}</div>}
            <div className="meta">
              키워드: {a.keyword} · {a.pub_date ? a.pub_date.slice(0, 10) : `수집 ${fmtDateShort(a.fetched_at)}`}
            </div>
          </div>
        ))
      ) : (
        <div className="empty">수집된 글이 없습니다. 상단의 "뉴스 수집" 버튼을 눌러보세요.</div>
      )}
    </>
  )
}
