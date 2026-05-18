import type { ChatRequest, RouteItem } from '@/types'
import { toServerAIConfig } from '@/services/aiConfig'

type SSEChunk =
  | { type: 'text'; content: string }
  | { type: 'route_update'; route: RouteItem[] }
  | { type: 'done' }
  | { type: 'error'; message: string }

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
          const chunk = JSON.parse(data) as SSEChunk
          onChunk(chunk)
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }
}
