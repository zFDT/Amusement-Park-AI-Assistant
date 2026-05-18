import { RefreshCw, Clock, AlertCircle, Loader2 } from 'lucide-react'
import { useWaitTimes } from '@/hooks/useWaitTimes'
import { Badge } from '@/components/ui/Badge'
import type { WaitStatus } from '@/types'

function waitBadgeVariant(status: WaitStatus, minutes: number | null | undefined): 'green' | 'yellow' | 'red' | 'gray' {
  if (status === 'closed' || status === 'down') return 'gray'
  if (minutes == null) return 'gray'
  if (minutes < 30) return 'green'
  if (minutes < 60) return 'yellow'
  return 'red'
}

function waitLabel(status: WaitStatus, minutes: number | null | undefined): string {
  if (status === 'closed') return '关闭'
  if (status === 'down') return '故障'
  if (minutes == null) return '未知'
  if (minutes === 0) return '无需等待'
  return `${minutes} 分钟`
}

export function WaitTimePanel() {
  const { waitTimes, lastWaitTimeUpdate, loading, error, refresh } = useWaitTimes()

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
          disabled={loading}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors disabled:opacity-40"
          aria-label="刷新排队时间"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-3 flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {loading && entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-sm text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            加载中...
          </div>
        ) : entries.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">
            暂无排队数据
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
                    {item.attractionName ?? item.attractionId}
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
