import { Clock, MapPin, Star, UtensilsCrossed, Coffee, Zap, Circle, CheckCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message, RouteItem } from '@/types'
import { cn } from '@/components/ui/utils'
import { useAppStore } from '@/store/sessionStore'

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

/** 过滤掉 route 代码块——路线数据已通过卡片单独展示 */
function cleanRouteBlock(text: string): string {
  return text
    .replace(/```route\s*\n[\s\S]*?\n```/g, '')
    .replace(/```route[\s\S]*?```/g, '')
    .trim()
}

/** Tailwind 样式化的 Markdown 渲染组件 */
function MarkdownRenderer({ content }: { content: string }) {
  const cleaned = cleanRouteBlock(content)
  if (!cleaned) return null

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // ----- 标题 -----
        h1: ({ children, ...props }) => (
          <h1 className="text-base font-bold text-gray-900 mt-3 mb-1.5 first:mt-0" {...props}>{children}</h1>
        ),
        h2: ({ children, ...props }) => (
          <h2 className="text-sm font-bold text-gray-900 mt-2.5 mb-1 first:mt-0 flex items-center gap-1.5" {...props}>{children}</h2>
        ),
        h3: ({ children, ...props }) => (
          <h3 className="text-sm font-semibold text-gray-800 mt-2 mb-0.5 first:mt-0" {...props}>{children}</h3>
        ),

        // ----- 段落 -----
        p: ({ children, ...props }) => (
          <p className="text-sm leading-relaxed text-gray-700 my-1 first:mt-0 last:mb-0" {...props}>{children}</p>
        ),

        // ----- 加粗 / 斜体 -----
        strong: ({ children, ...props }) => (
          <strong className="font-semibold text-gray-900" {...props}>{children}</strong>
        ),
        em: ({ children, ...props }) => (
          <em className="italic text-gray-600" {...props}>{children}</em>
        ),

        // ----- 行内代码 -----
        code: ({ className, children, ...props }) => {
          // 代码块由 pre 处理，这里只处理行内代码
          const isInline = !className
          if (isInline) {
            return (
              <code className="px-1.5 py-0.5 bg-gray-200 text-gray-800 rounded text-xs font-mono" {...props}>
                {children}
              </code>
            )
          }
          return <code className={cn('text-xs font-mono', className)} {...props}>{children}</code>
        },
        pre: ({ children, ...props }) => (
          <pre className="bg-gray-800 text-gray-100 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono leading-relaxed" {...props}>
            {children}
          </pre>
        ),

        // ----- 引用块 -----
        blockquote: ({ children, ...props }) => (
          <blockquote className="border-l-3 border-amber-400 bg-amber-50/60 rounded-r-lg pl-3 pr-3 py-2 my-2 text-sm text-gray-700" {...props}>
            {children}
          </blockquote>
        ),

        // ----- 分割线 -----
        hr: (props) => (
          <hr className="my-3 border-0 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200" {...props} />
        ),

        // ----- 无序列表 -----
        ul: ({ children, ...props }) => (
          <ul className="my-1.5 space-y-0.5 list-none pl-1" {...props}>{children}</ul>
        ),
        // ----- 有序列表 -----
        ol: ({ children, ...props }) => (
          <ol className="my-1.5 space-y-0.5 pl-1 list-none" {...props}>{children}</ol>
        ),
        li: ({ children, ...props }) => {
          // 从 children 中提取序号或标记符号
          const ordered = (props as Record<string, unknown>).ordered as boolean | undefined
          const index = (props as Record<string, unknown>).index as number | undefined
          return (
            <li className="flex items-start gap-2 text-sm text-gray-700" {...props}>
              {ordered && index !== undefined ? (
                <span className="flex-shrink-0 text-xs text-gray-400 mt-0.5 w-4 text-right tabular-nums">
                  {index + 1}.
                </span>
              ) : (
                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-gray-400 flex-shrink-0" />
              )}
              <span className="flex-1">{children}</span>
            </li>
          )
        },

        // ----- 表格 -----
        table: ({ children, ...props }) => (
          <div className="my-2 overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
            <table className="w-full text-sm border-collapse" {...props}>{children}</table>
          </div>
        ),
        thead: ({ children, ...props }) => (
          <thead className="bg-blue-50/60" {...props}>{children}</thead>
        ),
        tbody: ({ children, ...props }) => (
          <tbody className="divide-y divide-gray-100" {...props}>{children}</tbody>
        ),
        tr: ({ children, ...props }) => (
          <tr className="even:bg-gray-50/50 transition-colors hover:bg-blue-50/30" {...props}>{children}</tr>
        ),
        th: ({ children, ...props }) => (
          <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700 whitespace-nowrap border-b border-blue-100" {...props}>{children}</th>
        ),
        td: ({ children, ...props }) => (
          <td className="px-3 py-2 text-gray-700 align-top leading-relaxed" {...props}>{children}</td>
        ),

        // ----- 链接 -----
        a: ({ children, href, ...props }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 underline underline-offset-2 hover:text-blue-800 transition-colors"
            {...props}
          >
            {children}
          </a>
        ),

        // ----- 删除线 -----
        del: ({ children, ...props }) => (
          <del className="text-gray-400 line-through" {...props}>{children}</del>
        ),
      }}
    >
      {cleaned}
    </ReactMarkdown>
  )
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const completedAttractions = useAppStore((s) => s.completedAttractions)
  const markAttractionComplete = useAppStore((s) => s.markAttractionComplete)

  const routeItems = message.route
  const completedCount = routeItems
    ? routeItems.filter((item) => completedAttractions.includes(item.attractionId)).length
    : 0
  const totalCount = routeItems?.length ?? 0
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold mr-2 flex-shrink-0 mt-1 shadow-sm">
          AI
        </div>
      )}
      <div className={cn('max-w-[85%] space-y-2')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3',
            isUser
              ? 'bg-blue-600 text-white rounded-tr-sm text-sm leading-relaxed whitespace-pre-wrap'
              : message.isError
              ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-sm text-sm leading-relaxed'
              : 'bg-white border border-gray-200 rounded-tl-sm shadow-sm'
          )}
        >
          {!message.content ? (
            <span className="inline-flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.1s]" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]" />
            </span>
          ) : isUser ? (
            message.content
          ) : message.isError ? (
            message.content
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>

        {message.route && message.route.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-md">
            {/* 卡片标题 */}
            <div className="px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-700 flex-1">推荐路线</span>
              {totalCount > 0 && (
                <span className="text-xs text-blue-500 bg-blue-100/60 px-2 py-0.5 rounded-full font-medium">
                  {completedCount}/{totalCount} 已完成
                </span>
              )}
            </div>
            {/* 进度条 */}
            {totalCount > 0 && (
              <div className="h-1.5 bg-gray-100">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500 ease-out rounded-r"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            )}
            {/* 路线列表 */}
            <div className="divide-y divide-gray-50">
              {message.route.map((item, i) => {
                const completed = completedAttractions.includes(item.attractionId)
                return (
                <div
                  key={`${item.attractionId}-${i}`}
                  className={cn(
                    'flex items-start gap-3 px-4 py-3 transition-all duration-200',
                    completed && 'opacity-50 bg-gray-50/30',
                    !completed && item.type === 'break' && 'bg-gray-50/40',
                    !completed && item.type === 'show' && 'bg-purple-50/30',
                    !completed && item.type === 'dining' && 'bg-amber-50/30',
                  )}
                >
                  {/* 完成状态按钮 */}
                  <button
                    onClick={() => markAttractionComplete(item.attractionId)}
                    disabled={completed}
                    className={cn(
                      'flex-shrink-0 mt-0.5 transition-all duration-200',
                      completed
                        ? 'text-green-500 cursor-default scale-110'
                        : 'text-gray-300 hover:text-green-500 hover:scale-110 cursor-pointer active:scale-95'
                    )}
                    aria-label={completed ? '已完成' : '标记为已完成'}
                    title={completed ? '已完成' : '点击标记为已完成'}
                  >
                    {completed
                      ? <CheckCircle className="w-5 h-5 drop-shadow-sm" />
                      : <Circle className="w-5 h-5" />
                    }
                  </button>

                  {/* 时间 */}
                  <div className="flex items-center gap-1 text-xs text-gray-400 w-12 flex-shrink-0 mt-0.5 font-mono">
                    <Clock className="w-3 h-3" />
                    {item.time}
                  </div>

                  {/* 详细信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <RouteItemTypeIcon type={item.type} />
                      <p className={cn(
                        'text-sm font-medium truncate',
                        completed ? 'text-gray-400 line-through decoration-2' : routeItemNameColor(item.type)
                      )}>
                        {item.attractionName}
                      </p>
                      {item.estimatedWait > 0 && (
                        <span className="text-xs text-orange-500 font-medium flex-shrink-0 ml-auto bg-orange-50 px-1.5 py-0.5 rounded">
                          ~{item.estimatedWait}分
                        </span>
                      )}
                    </div>
                    {item.areaName && (
                      <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-0.5">
                        <MapPin className="w-3 h-3" />
                        {item.areaName}
                      </p>
                    )}
                    {item.note && (
                      <p className="text-xs text-gray-500 mt-1 leading-relaxed">{item.note}</p>
                    )}
                  </div>
                </div>
              )})}
            </div>
            {/* 底部提示 */}
            {totalCount > 0 && (
              <div className="px-4 py-2 bg-gray-50/50 border-t border-gray-100 text-xs text-gray-400 text-center">
                💡 点击圆圈标记已完成项目，跟踪游玩进度
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
