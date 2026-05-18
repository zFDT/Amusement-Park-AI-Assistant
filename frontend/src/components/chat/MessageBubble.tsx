import { Clock, MapPin, Star, UtensilsCrossed, Coffee, Zap } from 'lucide-react'
import type { Message, RouteItem } from '@/types'
import { cn } from '@/components/ui/utils'

interface MessageBubbleProps {
  message: Message
}

function RouteItemTypeIcon({ type }: { type: RouteItem['type'] }) {
  switch (type) {
    case 'show':
      return <Star className="w-3 h-3 text-purple-500 flex-shrink-0" />
    case 'dining':
      return <UtensilsCrossed className="w-3 h-3 text-amber-500 flex-shrink-0" />
    case 'break':
      return <Coffee className="w-3 h-3 text-gray-400 flex-shrink-0" />
    default:
      return <Zap className="w-3 h-3 text-blue-500 flex-shrink-0" />
  }
}

function routeItemNameColor(type: RouteItem['type']): string {
  switch (type) {
    case 'show': return 'text-purple-700'
    case 'dining': return 'text-amber-700'
    case 'break': return 'text-gray-500'
    default: return 'text-gray-800'
  }
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  if (parts.length === 1) return text
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
          : <span key={i}>{part}</span>
      )}
    </>
  )
}

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      i++
      continue
    }

    // ## / ### heading
    if (/^#{1,3}\s/.test(line)) {
      const content = line.replace(/^#{1,3}\s+/, '')
      nodes.push(
        <p key={i} className="font-semibold text-sm mt-2 mb-0.5 text-gray-900">
          {renderInline(content)}
        </p>
      )
      i++
      continue
    }

    // bullet list — collect consecutive items
    if (/^[-*•]\s/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^[-*•]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*•]\s+/, ''))
        i++
      }
      nodes.push(
        <ul key={`ul-${i}`} className="my-1 space-y-0.5">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-sm">
              <span className="mt-2 w-1 h-1 rounded-full bg-gray-500 flex-shrink-0" />
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    }

    // numbered list
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ''))
        i++
      }
      nodes.push(
        <ol key={`ol-${i}`} className="my-1 space-y-0.5">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-sm">
              <span className="flex-shrink-0 text-xs text-gray-400 mt-0.5 w-4">{idx + 1}.</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      )
      continue
    }

    nodes.push(
      <p key={i} className="text-sm leading-relaxed">
        {renderInline(line)}
      </p>
    )
    i++
  }

  return <div className="space-y-1">{nodes}</div>
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
            'rounded-2xl px-4 py-3',
            isUser
              ? 'bg-blue-600 text-white rounded-tr-sm text-sm leading-relaxed whitespace-pre-wrap'
              : 'bg-gray-100 text-gray-800 rounded-tl-sm'
          )}
        >
          {!message.content ? (
            <span className="inline-flex gap-1">
              <span className="animate-bounce">·</span>
              <span className="animate-bounce [animation-delay:0.1s]">·</span>
              <span className="animate-bounce [animation-delay:0.2s]">·</span>
            </span>
          ) : isUser ? (
            message.content
          ) : (
            renderMarkdown(message.content)
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
                <div
                  key={`${item.attractionId}-${i}`}
                  className={cn(
                    'flex items-start gap-3 px-3 py-2.5',
                    item.type === 'break' && 'bg-gray-50/60',
                    item.type === 'show' && 'bg-purple-50/40',
                    item.type === 'dining' && 'bg-amber-50/40',
                  )}
                >
                  <div className="flex items-center gap-1 text-xs text-gray-400 w-12 flex-shrink-0 mt-0.5">
                    <Clock className="w-3 h-3" />
                    {item.time}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <RouteItemTypeIcon type={item.type} />
                      <p className={cn('text-sm font-medium truncate', routeItemNameColor(item.type))}>
                        {item.attractionName}
                      </p>
                    </div>
                    {item.note && <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{item.note}</p>}
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
