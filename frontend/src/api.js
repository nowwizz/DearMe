export async function api(path, options) {
  const response = await fetch('/api' + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (response.status === 204) return
  const payload = await response.json()
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '요청을 처리하지 못했어요.')
  return payload
}

export function formatClock(value) {
  return value?.slice(0, 5) || '—'
}

export function formatEndClock(value) {
  const clock = formatClock(value)
  return clock === '00:00' ? '24:00' : clock
}

export function formatWalk(seconds) {
  if (seconds == null) return '확인 필요'
  const minutes = Math.floor(seconds / 60)
  return minutes + '분' + (seconds % 60 ? ' ' + (seconds % 60) + '초' : '')
}

export function formatStamp(value) {
  return value ? new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Seoul',
  }).format(new Date(value)) : '—'
}
