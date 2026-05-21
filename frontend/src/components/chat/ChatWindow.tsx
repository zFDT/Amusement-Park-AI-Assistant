import { useRef, useEffect, useState, useCallback } from 'react'
import { ArrowDown } from 'lucide-react'
import type { Message } from '@/types'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { useChat } from '@/hooks/useChat'
import { useAppStore } from '@/store/sessionStore'

interface ChatWindowProps {
  messages: Message[]
}

export function ChatWindow({ messages }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const { sendMessage, stopStreaming, isStreaming } = useChat()
  const parkId = useAppStore((s) => s.parkId)
  const aiConfig = useAppStore((s) => s.aiConfig)
  const currentLocation = useAppStore((s) => s.currentLocation)
  const completedAttractions = useAppStore((s) => s.completedAttractions)

  const scrollToBottom = useCallback((smooth = true) => {
    bottomRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' })
  }, [])

  // Auto-scroll to bottom on new messages (only if user is near bottom)
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150
    if (isNearBottom || isStreaming) {
      scrollToBottom(true)
    }
  }, [messages, isStreaming, scrollToBottom])

  // Track scroll position to show/hide "scroll to bottom" button
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const handleScroll = () => {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150
      setShowScrollButton(!isNearBottom)
    }
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <div className="flex flex-col h-full relative">
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 space-y-3">
            <div className="text-5xl">🎢</div>
            <p className="text-lg font-medium text-gray-600">游园助理已就绪</p>
            <p className="text-sm max-w-xs">
              告诉我你的游园计划，我来帮你规划最优路线，减少排队时间！
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          onClick={() => scrollToBottom(true)}
          className="absolute bottom-20 right-4 z-10 p-2 bg-white border border-gray-200 rounded-full shadow-lg hover:shadow-xl transition-all"
          aria-label="滚动到最新消息"
        >
          <ArrowDown className="w-4 h-4 text-gray-600" />
        </button>
      )}

      <div className="border-t border-gray-100 bg-white px-4 py-3">
        <ChatInput
          onSend={sendMessage}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          parkId={parkId}
          aiConfig={aiConfig}
          currentLocation={currentLocation}
          completedAttractions={completedAttractions}
        />
      </div>
    </div>
  )
}
