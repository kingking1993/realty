/** 클릭 정렬 헤더. 같은 컬럼 재클릭 시 방향 토글, 다른 컬럼은 기본 방향으로. */
export default function SortTh({ label, col, sort, setSort, num, defaultDir = 'asc' }) {
  const active = sort.col === col
  const arrow = active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''
  const onClick = () =>
    setSort((s) =>
      s.col === col
        ? { col, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { col, dir: defaultDir },
    )
  return (
    <th className={`sortable${num ? ' num' : ''}${active ? ' active' : ''}`} onClick={onClick}>
      {label}{arrow}
    </th>
  )
}
