import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import { PlanningForm } from '@/components/planning/PlanningForm'
import { AIConfigPanel } from '@/components/settings/AIConfigPanel'
import type { ParkId } from '@/types'

const PARKS = [
  {
    id: 'hongkong_disney' as ParkId,
    name: '香港迪士尼乐园',
    emoji: '✨',
    description: '亚洲经典迪士尼，独家项目众多',
    color: 'from-pink-500 to-orange-500',
  },
  {
    id: 'shanghai_disney' as ParkId,
    name: '上海迪士尼乐园',
    emoji: '🏰',
    description: '中国大陆首座迪士尼乐园',
    color: 'from-blue-500 to-purple-600',
    disabled: true,
  },
]

export function HomePage() {
  const [selectedPark, setSelectedPark] = useState<ParkId | null>(null)

  if (selectedPark) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-lg mx-auto px-4 py-8">
          <button
            onClick={() => setSelectedPark(null)}
            className="text-sm text-gray-500 hover:text-gray-700 mb-6 flex items-center gap-1"
          >
            ← 重新选择乐园
          </button>
          <div className="mb-6">
            <h1 className="text-xl font-bold text-gray-900">游前规划</h1>
            <p className="text-sm text-gray-500 mt-1">
              填写信息后，AI 将为你生成个性化游园路线
            </p>
          </div>
          <div className="mb-6">
            <AIConfigPanel />
          </div>
          <PlanningForm parkId={selectedPark} />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <div className="max-w-lg mx-auto px-4 py-12">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-700 rounded-full px-4 py-1.5 text-sm font-medium mb-4">
            <Sparkles className="w-4 h-4" />
            AI 智能游园助理
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            游园助理
          </h1>
          <p className="text-gray-500 text-base leading-relaxed">
            实时排队数据 + AI 路线规划<br />
            让每一分钟都值得
          </p>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium text-gray-600 text-center mb-4">选择目标乐园</p>
          {PARKS.map((park) => (
            <button
              key={park.id}
              onClick={() => !park.disabled && setSelectedPark(park.id)}
              disabled={park.disabled}
              className={`w-full text-left rounded-2xl p-5 transition-all ${
                park.disabled
                  ? 'bg-gray-100 opacity-60 cursor-not-allowed'
                  : 'bg-white shadow-sm hover:shadow-md hover:-translate-y-0.5 border border-gray-100'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${park.color} flex items-center justify-center text-2xl`}>
                  {park.emoji}
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-gray-900">{park.name}</p>
                  <p className="text-sm text-gray-500 mt-0.5">{park.description}</p>
                </div>
                {park.disabled ? (
                  <span className="text-xs bg-gray-200 text-gray-500 px-2 py-1 rounded-full">即将上线</span>
                ) : (
                  <span className="text-gray-400">→</span>
                )}
              </div>
            </button>
          ))}
        </div>

        <div className="mt-10 grid grid-cols-3 gap-4 text-center">
          {[
            { emoji: '⚡', label: '实时排队', desc: '5分钟更新' },
            { emoji: '🤖', label: 'AI 规划', desc: '个性化路线' },
            { emoji: '💬', label: '对话调整', desc: '随时重规划' },
          ].map(({ emoji, label, desc }) => (
            <div key={label} className="space-y-1">
              <div className="text-2xl">{emoji}</div>
              <p className="text-sm font-medium text-gray-700">{label}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
