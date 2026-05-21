import { Loader2, AlertCircle, Inbox, RefreshCw } from 'lucide-react'

interface StateWrapperProps {
  loading: boolean
  error: string | null
  empty: boolean
  emptyMessage?: string
  emptyIcon?: React.ReactNode
  onRetry?: () => void
  children: React.ReactNode
}

/** 统一的三态（Loading / Error / Empty）包裹组件 */
export function StateWrapper({
  loading,
  error,
  empty,
  emptyMessage = '暂无数据',
  emptyIcon,
  onRetry,
  children,
}: StateWrapperProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin" />
          <span className="text-sm">加载中...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3 max-w-xs text-center">
          <AlertCircle className="w-10 h-10 text-red-400" />
          <p className="text-sm text-red-500">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-xl hover:bg-red-600 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              重试
            </button>
          )}
        </div>
      </div>
    )
  }

  if (empty) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          {emptyIcon || <Inbox className="w-10 h-10" />}
          <span className="text-sm">{emptyMessage}</span>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
