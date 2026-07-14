/** FastAPI JSON API 클라이언트. */

export async function getJSON(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function collect(job) {
  return fetch(`/collect/${job}`, { method: 'POST' })
}
