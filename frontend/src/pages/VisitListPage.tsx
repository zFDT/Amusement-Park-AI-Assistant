import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, ChevronRight, Archive, LogOut, CheckCircle2, Clock, BookOpen } from 'lucide-react'
import { useAppStore } from '@/store/sessionStore'
import { getVisits, archiveVisit } from '@/services/api'
import type { VisitSummary } from '@/services/api'
import type { PlanningInfo, ParkId } from '@/types'

const PARK_NAMES: Record<string, string> = {
  hongkong_disney: '香港迪士尼乐园',
  shanghai_disney: '上海迪士尼乐园',
}

const PARK_EMOJIS: Record<string, string> = {
  hongkong_disney: '✨',
  shanghai_disney: '🏰',
}

export function VisitListPage() {
  const navigate = useNavigate()
  const { userId, resumeSession, resetSession, logout } = useAppStore()
  const [visits, setVisits] = useState<VisitSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [archiving, setArchiving] = useState<string | null>(null)

  useEffect(() => {
    if (!userId) {
      navigate('/')
      return
    }
    loadVisits()
  }, [userId])

  const loadVisits = async () => {
    if (!userId) return
    setLoading(true)
    try {
      const res = await getVisits(userId)
      setVisits(res.visits)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleResume = (visit: VisitSummary) => {
    if (visit.status === 'archived') return
    const snap = visit.planningSnapshot
    const planningInfo: PlanningInfo | null = snap ? {
      parkId: snap.park_id as ParkId,
      visitDate: snap.visit_date as string,
      entryTime: snap.entry_time as string,
      exitTime: snap.exit_time as string,
      party: snap.party as PlanningInfo['party'],
      preferences: (snap.preferences ?? []) as PlanningInfo['preferences'],
      mustDoAttractions: (snap.must_do_attractions ?? []) as string[],
      fitnessLevel: (snap.fitness_level ?? 3) as PlanningInfo['fitnessLevel'],
      experienceLevel: (snap.experience_level ?? 'first_time') as PlanningInfo['experienceLevel'],
      specialNotes: (snap.special_notes ?? '') as string,
      specialNeeds: (snap.special_needs ?? []) as PlanningInfo['specialNeeds'],
    } : null
    resumeSession(
      visit.visitId,
      visit.parkId as ParkId,
      planningInfo ?? ({} as PlanningInfo),
      [],
    )
    navigate('/assistant')
  }

  const handleArchive = async (visit: VisitSummary) => {
    if (!userId || archiving) return
    if (!confirm(`确定归档「${PARK_NAMES[visit.parkId] ?? visit.parkId} ${visit.visitDate}」？归档后不再提供 AI 对话，但记录永久保留。`)) return
    setArchiving(visit.visitId)
    try {
      await archiveVisit(userId, visit.visitId)
      setVisits((prev) => prev.map((v) => v.visitId === visit.visitId ? { ...v, status: 'archived' } : v))
    } catch {
      // ignore
    } finally {
      setArchiving(null)
    }
  }

  const handleNewVisit = () => {
    resetSession()
    navigate('/plan')
  }

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const activeVisits = visits.filter((v) => v.status === 'active')
  const archivedVisits = visits.filter((v) => v.status === 'archived')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-gray-900">我的游园</h1>
            <p className="text-xs text-gray-400 mt-0.5">{userId}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/strategies')}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-3 py-2 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              攻略库
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-3 py-2 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              切换账号
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-5 space-y-5">
        {/* New visit button */}
        <button
          onClick={handleNewVisit}
          className="w-full flex items-center gap-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-2xl p-5 shadow-sm active:scale-[0.98] transition-transform"
        >
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center shrink-0">
            <Plus className="w-5 h-5" />
          </div>
          <div className="text-left">
            <p className="font-semibold text-base">开始新的游园</p>
            <p className="text-sm text-white/80 mt-0.5">选择乐园，AI 为你规划路线</p>
          </div>
          <ChevronRight className="w-5 h-5 ml-auto shrink-0 text-white/70" />
        </button>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <span className="w-6 h-6 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Active visits */}
            {activeVisits.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
                  进行中
                </h2>
                <div className="space-y-2">
                  {activeVisits.map((visit) => (
                    <VisitCard
                      key={visit.visitId}
                      visit={visit}
                      onResume={() => handleResume(visit)}
                      onArchive={() => handleArchive(visit)}
                      archiving={archiving === visit.visitId}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Archived visits */}
            {archivedVisits.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
                  已归档
                </h2>
                <div className="space-y-2">
                  {archivedVisits.map((visit) => (
                    <VisitCard
                      key={visit.visitId}
                      visit={visit}
                      onResume={() => {}}
                      onArchive={() => {}}
                      archiving={false}
                      readonly
                    />
                  ))}
                </div>
              </section>
            )}

            {visits.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <div className="text-4xl mb-3">🎢</div>
                <p className="text-sm">还没有游园记录</p>
                <p className="text-xs mt-1">点击上方按钮开始你的第一次游园</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

interface VisitCardProps {
  visit: VisitSummary
  onResume: () => void
  onArchive: () => void
  archiving: boolean
  readonly?: boolean
}

function VisitCard({ visit, onResume, onArchive, archiving, readonly }: VisitCardProps) {
  const parkName = PARK_NAMES[visit.parkId] ?? visit.parkId
  const emoji = PARK_EMOJIS[visit.parkId] ?? '🎡'
  const isArchived = visit.status === 'archived'

  return (
    <div
      className={`bg-white rounded-2xl border overflow-hidden transition-all ${
        isArchived ? 'border-gray-100 opacity-70' : 'border-gray-100 shadow-sm'
      }`}
    >
      <div
        className={`flex items-center gap-4 p-4 ${!isArchived ? 'cursor-pointer active:bg-gray-50' : ''}`}
        onClick={!isArchived ? onResume : undefined}
      >
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0 ${
          isArchived ? 'bg-gray-100' : 'bg-blue-50'
        }`}>
          {emoji}
        </div>
        <div className="flex-1 min-w-0">
          <p className={`font-semibold text-sm truncate ${isArchived ? 'text-gray-500' : 'text-gray-900'}`}>
            {parkName}
          </p>
          <div className="flex items-center gap-3 mt-1">
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <Clock className="w-3 h-3" />
              {visit.visitDate}
            </span>
            {visit.completedCount > 0 && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <CheckCircle2 className="w-3 h-3" />
                已游玩 {visit.completedCount} 项
              </span>
            )}
          </div>
        </div>
        {!isArchived && (
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-xs text-blue-600 font-medium">继续</span>
            <ChevronRight className="w-4 h-4 text-blue-600" />
          </div>
        )}
        {isArchived && (
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full shrink-0">已归档</span>
        )}
      </div>

      {!isArchived && !readonly && (
        <div className="border-t border-gray-50 px-4 py-2.5 flex justify-end">
          <button
            onClick={(e) => { e.stopPropagation(); onArchive() }}
            disabled={archiving}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            {archiving ? (
              <span className="w-3.5 h-3.5 border border-gray-400/30 border-t-gray-400 rounded-full animate-spin" />
            ) : (
              <Archive className="w-3.5 h-3.5" />
            )}
            归档此次游园
          </button>
        </div>
      )}
    </div>
  )
}
