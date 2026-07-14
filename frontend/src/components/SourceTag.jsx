import { Newspaper, Coffee, MessageSquare } from 'lucide-react'
import { SOURCE_LABELS } from '../format.js'

const SOURCE_ICONS = { news: Newspaper, cafe: Coffee, blind: MessageSquare }

/** 출처 칩 — lucide 아이콘 + 토널 컨테이너. */
export default function SourceTag({ source }) {
  const Icon = SOURCE_ICONS[source]
  return (
    <span className={`tag ${source}`}>
      {Icon && <Icon size={12} strokeWidth={2} aria-hidden="true" />}
      {SOURCE_LABELS[source] ?? source}
    </span>
  )
}
