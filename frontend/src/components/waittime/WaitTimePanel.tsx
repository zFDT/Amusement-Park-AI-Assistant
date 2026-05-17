import { RefreshCw, Clock } from 'lucide-react'
import { useWaitTimes } from '@/hooks/useWaitTimes'
import { Badge } from '@/components/ui/Badge'
import type { WaitStatus } from '@/types'

function waitBadgeVariant(status: WaitStatus, minutes: number | null): 'green' | 'yellow' | 'red' | 'gray' {
  if (status === 'closed' || status === 'down') return 'gray'
  if (minutes === null) return 'gray'
  if (minutes < 30) return 'green'
  if (minutes < 60) return 'yellow'
  return 'red'
}

function waitLabel(status: WaitStatus, minutes: number | null): string {
  if (status === 'closed') return '关闭'
  if (status === 'down') return '故障'
  if (minutes === null) return '未知'
  if (minutes === 0) return '无需等待'
  return `${minutes} 分钟`
}

export function WaitTimePanel() {
  const { waitTimes, lastWaitTimeUpdate, refresh } = useWaitTimes()

  const entries = Object.values(waitTimes)

  const formatTime = (iso: string | null) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">实时排队</h2>
          <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
            <Clock className="w-3 h-3" />
            更新于 {formatTime(lastWaitTimeUpdate)}
          </p>
        </div>
        <button
          onClick={refresh}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          aria-label="刷新排队时间"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {entries.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">
            加载中...
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {entries
              .sort((a, b) => {
                if (a.status !== 'open' && b.status === 'open') return 1
                if (a.status === 'open' && b.status !== 'open') return -1
                return (a.waitMinutes ?? 999) - (b.waitMinutes ?? 999)
              })
              .map((item) => (
                <div key={item.attractionId} className="flex items-center justify-between px-4 py-3">
                  <span className="text-sm text-gray-700 flex-1 min-w-0 truncate pr-2">
                    {item.attractionId}
                  </span>
                  <Badge variant={waitBadgeVariant(item.status, item.waitMinutes)}>
                    {waitLabel(item.status, item.waitMinutes)}
                  </Badge>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  )
}
