import { Clock, MapPin } from 'lucide-react'
import type { Message } from '@/types'
import { cn } from '@/components/ui/utils'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold mr-2 flex-shrink-0 mt-1">
          AI
        </div>
      )}
      <div className={cn('max-w-[80%] space-y-2')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap',
            isUser
              ? 'bg-blue-600 text-white rounded-tr-sm'
              : 'bg-gray-100 text-gray-800 rounded-tl-sm'
          )}
        >
          {message.content || (
            <span className="inline-flex gap-1">
              <span className="animate-bounce">·</span>
              <span className="animate-bounce [animation-delay:0.1s]">·</span>
              <span className="animate-bounce [animation-delay:0.2s]">·</span>
            </span>
          )}
        </div>

        {message.route && message.route.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <div className="px-3 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-semibold text-blue-700">推荐路线</span>
            </div>
            <div className="divide-y divide-gray-50">
              {message.route.map((item, i) => (
                <div key={i} className="flex items-start gap-3 px-3 py-2.5">
                  <div className="flex items-center gap-1 text-xs text-gray-400 w-12 flex-shrink-0 mt-0.5">
                    <Clock className="w-3 h-3" />
                    {item.time}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{item.attractionName}</p>
                    {item.note && <p className="text-xs text-gray-500 mt-0.5">{item.note}</p>}
                  </div>
                  {item.estimatedWait > 0 && (
                    <span className="text-xs text-orange-600 font-medium flex-shrink-0">
                      约 {item.estimatedWait} 分钟
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
