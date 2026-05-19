import type { ChatRequest, RouteItem } from '@/types'
import { toServerAIConfig } from '@/services/aiConfig'

type SSEChunkRaw =
  | { type: 'text'; content: string }
  | { type: 'route_update'; route: Array<Record<string, unknown>> }
  | { type: 'done' }
  | { type: 'error'; message: string }

type SSEChunk =
  | { type: 'text'; content: string }
  | { type: 'route_update'; route: RouteItem[] }
  | { type: 'done' }
  | { type: 'error'; message: string }

/** Convert snake_case keys from backend SSE to camelCase for frontend */
function normalizeRouteItem(raw: Record<string, unknown>): RouteItem {
  return {
    time: raw.time as string,
    attractionId: raw.attraction_id as string,
    attractionName: raw.attraction_name as string,
    estimatedWait: raw.estimated_wait as number,
    note: raw.note as string | undefined,
    type: (raw.type as RouteItem['type']) ?? 'attraction',
    areaName: raw.area_name as string | undefined,
  }
}

export async function streamChat(
  request: ChatRequest,
  onChunk: (chunk: SSEChunk) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      message: request.message,
      current_location: request.currentLocation,
      ai_config: toServerAIConfig(request.aiConfig),
    }),
    signal,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail ?? 'Chat request failed')
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (!data) continue
        try {
          const raw = JSON.parse(data) as SSEChunkRaw
          if (raw.type === 'route_update') {
            onChunk({ type: 'route_update', route: raw.route.map(normalizeRouteItem) })
          } else {
            onChunk(raw as SSEChunk)
          }
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }
}
