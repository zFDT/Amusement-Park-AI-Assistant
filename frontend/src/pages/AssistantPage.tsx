import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RotateCcw, Map, List } from 'lucide-react'
import { useAppStore } from '@/store/sessionStore'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { WaitTimePanel } from '@/components/waittime/WaitTimePanel'
import { useState } from 'react'

type Tab = 'chat' | 'waittimes'

export function AssistantPage() {
  const navigate = useNavigate()
  const { sessionId, parkId, planningInfo, messages, resetSession } = useAppStore()
  const [activeTab, setActiveTab] = useState<Tab>('chat')

  useEffect(() => {
    if (!sessionId || !parkId) {
      navigate('/')
    }
  }, [sessionId, parkId, navigate])

  const handleReset = () => {
    if (confirm('确定要重新开始规划吗？当前对话记录将被清除。')) {
      resetSession()
      navigate('/')
    }
  }

  if (!sessionId || !planningInfo) return null

  const parkName = parkId === 'shanghai_disney' ? '上海迪士尼乐园' : '香港迪士尼乐园'

  return (
    <div className="flex flex-col h-screen bg-white">
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
        <div>
          <h1 className="text-sm font-semibold text-gray-900">游园助理</h1>
          <p className="text-xs text-gray-400">{parkName} · {planningInfo.visitDate}</p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          重新规划
        </button>
      </header>

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
