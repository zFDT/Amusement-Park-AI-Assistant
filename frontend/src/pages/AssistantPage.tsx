import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RotateCcw, Map, List, Share2, Copy, Check, ChevronLeft, MapPin } from 'lucide-react'
import { useAppStore } from '@/store/sessionStore'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { WaitTimePanel } from '@/components/waittime/WaitTimePanel'
import { shareSession } from '@/services/api'

type Tab = 'chat' | 'waittimes'

export function AssistantPage() {
  const navigate = useNavigate()
  const {
    sessionId, parkId, planningInfo, messages, resetSession,
    currentLocation,
  } = useAppStore()
  const [activeTab, setActiveTab] = useState<Tab>('chat')
  const [shareCode, setShareCode] = useState<string | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [sharing, setSharing] = useState(false)

  useEffect(() => {
    if (!sessionId || !parkId) {
      navigate('/visits')
    }
  }, [sessionId, parkId, navigate])

  const handleReset = () => {
    if (confirm('确定要重新开始规划吗？当前对话记录将被清除。')) {
      resetSession()
      navigate('/plan')
    }
  }

  const handleShare = async () => {
    if (!sessionId) return
    setSharing(true)
    setShareError(null)
    setShareCode(null)
    try {
      const res = await shareSession(sessionId)
      setShareCode(res.code)
    } catch {
      setShareError('生成恢复码失败，请重试')
    } finally {
      setSharing(false)
    }
  }

  const handleCopy = () => {
    if (!shareCode) return
    navigator.clipboard.writeText(shareCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (!sessionId || !planningInfo) return null

  const parkName = parkId === 'shanghai_disney' ? '上海迪士尼乐园' : '香港迪士尼乐园'

  return (
    <div className="flex flex-col h-screen bg-white">
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => navigate('/visits')}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors shrink-0"
            aria-label="返回游园列表"
          >
            <ChevronLeft className="w-4 h-4 text-gray-500" />
          </button>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-gray-900 truncate">游园助理</h1>
            <p className="text-xs text-gray-400 truncate">{parkName} · {planningInfo.visitDate}</p>
            {currentLocation && (currentLocation.label || currentLocation.areaName) && (
              <p className="text-xs text-blue-600 flex items-center gap-1 truncate mt-0.5">
                <MapPin className="w-3 h-3 flex-shrink-0" />
                {currentLocation.label || currentLocation.areaName}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleShare}
            disabled={sharing}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            title="生成换机恢复码"
          >
            <Share2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">换机继续</span>
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">重新规划</span>
          </button>
        </div>
      </header>

      {shareError && (
        <div className="mx-4 mt-3 p-3 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-xs text-red-600 text-center">{shareError}</p>
        </div>
      )}

      {shareCode && (
        <div className="mx-4 mt-3 p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-blue-600 font-medium">换机恢复码（7天有效）</p>
            <p className="text-lg font-mono font-bold text-blue-800 tracking-widest mt-0.5">{shareCode}</p>
            <p className="text-xs text-blue-500 mt-0.5">在新设备首页输入此码即可继续游园</p>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 px-3 py-2 rounded-lg hover:bg-blue-100 transition-colors shrink-0"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      )}

      <div className="flex border-b border-gray-100">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'chat'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Map className="w-4 h-4" />
          AI 助理
        </button>
        <button
          onClick={() => setActiveTab('waittimes')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'waittimes'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <List className="w-4 h-4" />
          排队时间
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? (
          <ChatWindow messages={messages} />
        ) : (
          <WaitTimePanel />
        )}
      </div>
    </div>
  )
}
