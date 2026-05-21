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
  let res: Response
  try {
    res = await fetch('/api/chat/stream', {
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
  } catch (err: unknown) {
    if (err instanceof TypeError && err.message === 'Failed to fetch') {
      throw new Error('网络连接失败，请检查网络后重试')
    }
    throw err
  }

  if (!res.ok) {
    let detail = `服务器错误 (${res.status})`
    try {
      const error = await res.json()
      detail = error.detail ?? error.message ?? detail
    } catch {
      // Response body is not JSON, use status text
      if (res.statusText) detail = res.statusText
    }
    throw new Error(detail)
  }

  if (!res.body) {
    throw new Error('响应体为空，无法接收流式数据')
  }

  const reader = res.body.getReader()
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
