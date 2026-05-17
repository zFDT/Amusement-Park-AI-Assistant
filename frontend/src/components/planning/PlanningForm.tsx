import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Users, Calendar, Heart, Star } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createSession } from '@/services/api'
import { useAppStore } from '@/store/sessionStore'
import type { PlanningInfo, PreferenceTag, PartyMember, ParkId } from '@/types'

const PREFERENCE_OPTIONS: { value: PreferenceTag; label: string; emoji: string }[] = [
  { value: 'thrill_rides', label: '刺激项目', emoji: '🎢' },
  { value: 'family_rides', label: '亲子项目', emoji: '🎠' },
  { value: 'shows', label: '表演/演出', emoji: '🎭' },
  { value: 'character_meet', label: '角色见面', emoji: '🐭' },
  { value: 'photography', label: '拍照打卡', emoji: '📸' },
  { value: 'dining', label: '特色餐饮', emoji: '🍔' },
  { value: 'parades', label: '花车巡游', emoji: '🎉' },
]

interface PlanningFormProps {
  parkId: ParkId
}

export function PlanningForm({ parkId }: PlanningFormProps) {
  const navigate = useNavigate()
  const { setSession, aiConfig } = useAppStore()
  const userId = useAppStore((s) => s.userId)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const today = new Date().toISOString().split('T')[0]

  const [form, setForm] = useState({
    visitDate: today,
    entryTime: '09:00',
    exitTime: '21:00',
    adults: 2,
    children: 0,
    elderly: 0,
    preferences: [] as PreferenceTag[],
    mustDoAttractions: [] as string[],
    fitnessLevel: 3 as 1 | 2 | 3 | 4 | 5,
    experienceLevel: 'first_time' as PlanningInfo['experienceLevel'],
    specialNotes: '',
  })

  const togglePreference = (pref: PreferenceTag) => {
    setForm((f) => ({
      ...f,
      preferences: f.preferences.includes(pref)
        ? f.preferences.filter((p) => p !== pref)
        : [...f.preferences, pref],
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const party: PartyMember[] = [
      ...Array(form.adults).fill({ type: 'adult' as const }),
      ...Array(form.children).fill({ type: 'child' as const, age: 8 }),
      ...Array(form.elderly).fill({ type: 'elderly' as const }),
    ]

    const planningInfo: PlanningInfo = {
      parkId,
      visitDate: form.visitDate,
      entryTime: form.entryTime,
      exitTime: form.exitTime,
      party,
      preferences: form.preferences,
      mustDoAttractions: form.mustDoAttractions,
      fitnessLevel: form.fitnessLevel,
      experienceLevel: form.experienceLevel,
      specialNotes: form.specialNotes,
      specialNeeds: [],
    }

    try {
      const result = await createSession(planningInfo, aiConfig, userId ?? undefined)
      setSession(result.sessionId, parkId, planningInfo)
      navigate('/assistant')
    } catch (err) {
      setError((err as Error).message || '创建规划失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-lg mx-auto">
      <div className="space-y-4">
        <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800">
          <Calendar className="w-4 h-4 text-blue-600" />
          游园时间
        </h2>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-3">
            <label className="block text-xs text-gray-500 mb-1">游园日期</label>
            <input
              type="date"
              value={form.visitDate}
              min={today}
              onChange={(e) => setForm((f) => ({ ...f, visitDate: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">入园时间</label>
            <input
              type="time"
              value={form.entryTime}
              onChange={(e) => setForm((f) => ({ ...f, entryTime: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">离园时间</label>
            <input
              type="time"
              value={form.exitTime}
              onChange={(e) => setForm((f) => ({ ...f, exitTime: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800">
          <Users className="w-4 h-4 text-blue-600" />
          人员构成
        </h2>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: 'adults', label: '成人', emoji: '🧑' },
            { key: 'children', label: '儿童', emoji: '👦' },
            { key: 'elderly', label: '老人', emoji: '👴' },
          ].map(({ key, label, emoji }) => (
            <div key={key} className="text-center">
              <label className="block text-xs text-gray-500 mb-1">{emoji} {label}</label>
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, [key]: Math.max(0, (f as Record<string, number>)[key] - 1) }))}
                  className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 font-bold transition-colors"
                >
                  −
                </button>
                <span className="w-6 text-center text-sm font-medium">
                  {(form as Record<string, number>)[key]}
                </span>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, [key]: (f as Record<string, number>)[key] + 1 }))}
                  className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 font-bold transition-colors"
                >
                  +
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800">
          <Heart className="w-4 h-4 text-blue-600" />
          兴趣偏好
        </h2>
        <div className="flex flex-wrap gap-2">
          {PREFERENCE_OPTIONS.map(({ value, label, emoji }) => (
            <button
              key={value}
              type="button"
              onClick={() => togglePreference(value)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                form.preferences.includes(value)
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {emoji} {label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800">
          <Star className="w-4 h-4 text-blue-600" />
          其他信息
        </h2>
        <div>
          <label className="block text-xs text-gray-500 mb-1">游园经验</label>
          <select
            value={form.experienceLevel}
            onChange={(e) => setForm((f) => ({ ...f, experienceLevel: e.target.value as PlanningInfo['experienceLevel'] }))}
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="first_time">首次游览</option>
            <option value="visited_before">去过 1-2 次</option>
            <option value="frequent">多次游览</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-2">
            体力水平：{['很弱', '较弱', '一般', '较好', '很好'][form.fitnessLevel - 1]}
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={form.fitnessLevel}
            onChange={(e) => setForm((f) => ({ ...f, fitnessLevel: Number(e.target.value) as PlanningInfo['fitnessLevel'] }))}
            className="w-full accent-blue-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>体力有限</span>
            <span>精力充沛</span>
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">特殊需求（可选）</label>
          <textarea
            value={form.specialNotes}
            onChange={(e) => setForm((f) => ({ ...f, specialNotes: e.target.value }))}
            placeholder="例如：孩子怕黑不能进暗室项目、有人对高空项目过敏..."
            rows={2}
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none placeholder:text-gray-400"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <Button
        type="submit"
        size="lg"
        disabled={loading || form.adults + form.children + form.elderly === 0}
        className="w-full"
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            AI 正在规划路线...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            开始规划
            <ChevronRight className="w-4 h-4" />
          </span>
        )}
      </Button>

      <p className="text-xs text-center text-gray-400">
        规划完成后可随时通过对话调整
      </p>
    </form>
  )
}
