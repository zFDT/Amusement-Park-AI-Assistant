import { useState, useRef, useCallback } from 'react'
import { Send, Square } from 'lucide-react'
import { cn } from '@/components/ui/utils'

const QUICK_PROMPTS = [
  '我现在在哪里，下一个去哪？',
  '帮我重新规划剩余行程',
  '附近有什么好吃的？',
  '还有哪些项目排队短？',
]

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
}

export function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSend(prompt)}
            disabled={isStreaming}
            className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600 transition-colors disabled:opacity-40"
          >
            {prompt}
          </button>
        ))}
      </div>
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="告诉我你的情况，或者问任何游园问题..."
          rows={1}
          className={cn(
            'flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder:text-gray-400 leading-relaxed'
          )}
        />
        <button
          onClick={isStreaming ? onStop : handleSend}
          disabled={!isStreaming && !value.trim()}
          className={cn(
            'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors',
            isStreaming
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 disabled:cursor-not-allowed'
          )}
          aria-label={isStreaming ? '停止' : '发送'}
        >
          {isStreaming ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}
