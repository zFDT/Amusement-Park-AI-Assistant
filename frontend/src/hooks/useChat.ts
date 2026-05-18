import { useCallback, useRef } from 'react'
import { useAppStore } from '@/store/sessionStore'
import { streamChat } from '@/services/sse'
import type { Message, RouteItem } from '@/types'

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function useChat() {
  const {
    sessionId,
    currentLocation,
    aiConfig,
    addMessage,
    updateLastMessage,
    removeLastMessage,
    setStreaming,
    setCurrentRoute,
    isStreaming,
  } = useAppStore()

  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || isStreaming) return

      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content,
        createdAt: new Date().toISOString(),
      }
      addMessage(userMessage)

      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        createdAt: new Date().toISOString(),
      }
      addMessage(assistantMessage)
      setStreaming(true)

      abortRef.current = new AbortController()
      let accumulated = ''
      let latestRoute: RouteItem[] | undefined

      try {
        await streamChat(
          { sessionId, message: content, currentLocation: currentLocation ?? undefined, aiConfig: aiConfig ?? undefined },
          (chunk) => {
            if (chunk.type === 'text') {
              accumulated += chunk.content
              updateLastMessage(accumulated, latestRoute)
            } else if (chunk.type === 'route_update') {
              latestRoute = chunk.route
              updateLastMessage(accumulated, latestRoute)
              setCurrentRoute(chunk.route)
            } else if (chunk.type === 'error') {
              updateLastMessage(chunk.message || '抱歉，AI 返回了错误，请重试。', undefined, true)
            }
          },
          abortRef.current.signal
        )
      } catch (err) {
        const error = err as Error
        if (error.name === 'AbortError') {
          // user stopped — remove empty placeholder, keep partial content if any
          if (!accumulated) {
            removeLastMessage()
          }
        } else {
          const msg = error.message?.includes('fetch')
            ? '网络连接失败，请检查网络后重试。'
            : (error.message || '抱歉，出现了一些问题，请重试。')
          updateLastMessage(accumulated || msg, undefined, !accumulated)
        }
      } finally {
        setStreaming(false)
        abortRef.current = null
      }
    },
    [sessionId, isStreaming, currentLocation, aiConfig, addMessage, updateLastMessage, removeLastMessage, setStreaming, setCurrentRoute]
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { sendMessage, stopStreaming, isStreaming }
}
