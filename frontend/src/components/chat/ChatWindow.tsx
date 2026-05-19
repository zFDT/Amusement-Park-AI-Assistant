import { useRef, useEffect } from 'react'
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
  const { sendMessage, stopStreaming, isStreaming } = useChat()
  const parkId = useAppStore((s) => s.parkId)
  const aiConfig = useAppStore((s) => s.aiConfig)
  const currentLocation = useAppStore((s) => s.currentLocation)
  const completedAttractions = useAppStore((s) => s.completedAttractions)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
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
