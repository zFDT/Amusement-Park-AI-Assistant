import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { PlanningForm } from '@/components/planning/PlanningForm'
import { AIConfigPanel } from '@/components/settings/AIConfigPanel'
import { useAppStore } from '@/store/sessionStore'
import { PARKS } from '@/constants/parks'
import type { ParkId } from '@/types'

export function PlanPage() {
  const navigate = useNavigate()
  const { userId } = useAppStore()
  const [selectedPark, setSelectedPark] = useState<ParkId | null>(null)

  // Guard: must be logged in
  if (!userId) {
    navigate('/')
    return null
  }

  if (selectedPark) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-lg mx-auto px-4 py-6">
          <button
            onClick={() => setSelectedPark(null)}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6"
          >
            <ChevronLeft className="w-4 h-4" />
            重新选择乐园
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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-lg mx-auto px-4 py-6">
        <button
          onClick={() => navigate('/visits')}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6"
        >
          <ChevronLeft className="w-4 h-4" />
          返回
        </button>

        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">选择乐园</h1>
          <p className="text-sm text-gray-500 mt-1">选择你要游玩的乐园</p>
        </div>

        <div className="space-y-3">
          {PARKS.map((park) => (
            <button
              key={park.id}
              onClick={() => !park.disabled && setSelectedPark(park.id)}
              disabled={park.disabled}
              className={`w-full text-left rounded-2xl p-5 transition-all ${
                park.disabled
                  ? 'bg-gray-100 opacity-60 cursor-not-allowed'
                  : 'bg-white shadow-sm hover:shadow-md active:scale-[0.98] border border-gray-100'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${park.color} flex items-center justify-center text-2xl shrink-0`}>
                  {park.emoji}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900">{park.name}</p>
                  <p className="text-sm text-gray-500 mt-0.5">{park.description}</p>
                </div>
                {park.disabled ? (
                  <span className="text-xs bg-gray-200 text-gray-500 px-2 py-1 rounded-full shrink-0">即将上线</span>
                ) : (
                  <ChevronLeft className="w-5 h-5 text-gray-400 rotate-180 shrink-0" />
                )}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
