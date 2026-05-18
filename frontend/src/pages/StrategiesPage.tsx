import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Search, Heart, Bookmark, MessageCircle, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'
import { getStrategies } from '@/services/api'
import type { StrategySummary } from '@/services/api'

const PARK_NAMES: Record<string, string> = {
  hongkong_disney: '香港迪士尼',
  shanghai_disney: '上海迪士尼',
}

const PAGE_SIZE = 20

export function StrategiesPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const parkId = searchParams.get('park') ?? ''
  const q = searchParams.get('q') ?? ''
  const page = parseInt(searchParams.get('page') ?? '1', 10)

  const [inputQ, setInputQ] = useState(q)
  const [strategies, setStrategies] = useState<StrategySummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<StrategySummary | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getStrategies({
        parkId: parkId || undefined,
        q: q || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      setStrategies(res.strategies)
      setTotal(res.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [parkId, q, page])

  useEffect(() => { load() }, [load])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (inputQ) next.set('q', inputQ); else next.delete('q')
      next.set('page', '1')
      return next
    })
  }

  const handleParkFilter = (id: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (id) next.set('park', id); else next.delete('park')
      next.set('page', '1')
      return next
    })
  }

  const handlePage = (p: number) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('page', String(p))
      return next
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-xl hover:bg-gray-100 transition-colors text-gray-500"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-base font-bold text-gray-900">攻略库</h1>
            <p className="text-xs text-gray-400 mt-0.5">共 {total} 条采集攻略</p>
          </div>
        </div>

        {/* Filters */}
        <div className="max-w-2xl mx-auto px-4 pb-3 space-y-2">
          {/* Park tabs */}
          <div className="flex gap-2">
            {[{ id: '', label: '全部' }, { id: 'hongkong_disney', label: '香港迪士尼' }, { id: 'shanghai_disney', label: '上海迪士尼' }].map((opt) => (
              <button
                key={opt.id}
                onClick={() => handleParkFilter(opt.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  parkId === opt.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={inputQ}
                onChange={(e) => setInputQ(e.target.value)}
                placeholder="搜索标题、内容、AI 摘要…"
                className="w-full pl-9 pr-3 py-2 text-sm bg-gray-100 rounded-xl border-0 outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-xl font-medium hover:bg-blue-700 transition-colors"
            >
              搜索
            </button>
          </form>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-4">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="w-6 h-6 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
          </div>
        ) : strategies.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <div className="text-4xl mb-3">📖</div>
            <p className="text-sm">暂无攻略</p>
            <p className="text-xs mt-1">可先运行采集脚本导入数据</p>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {strategies.map((s) => (
                <StrategyCard key={s.strategyId} strategy={s} onClick={() => setSelected(s)} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => handlePage(page - 1)}
                  disabled={page <= 1}
                  className="p-2 rounded-xl hover:bg-gray-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-600">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => handlePage(page + 1)}
                  disabled={page >= totalPages}
                  className="p-2 rounded-xl hover:bg-gray-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail modal */}
      {selected && (
        <StrategyDetail strategy={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function StrategyCard({ strategy: s, onClick }: { strategy: StrategySummary; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 cursor-pointer hover:shadow-md transition-shadow active:scale-[0.99]"
    >
      <div className="flex items-start gap-3">
        {/* Thumbnail */}
        {s.imageUrls.length > 0 ? (
          <img
            src={s.imageUrls[0]}
            alt=""
            className="w-16 h-16 rounded-xl object-cover shrink-0 bg-gray-100"
            loading="lazy"
          />
        ) : (
          <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-blue-50 to-purple-50 shrink-0 flex items-center justify-center text-2xl">
            📝
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
              {PARK_NAMES[s.parkId] ?? s.parkId}
            </span>
            <span className="text-xs text-gray-400">{s.platform}</span>
          </div>
          <p className="text-sm font-semibold text-gray-900 line-clamp-2 leading-snug">{s.title || '（无标题）'}</p>
          <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
            {s.aiSummary || s.contentExcerpt || '暂无内容'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-50">
        <span className="text-xs text-gray-400 flex-1 truncate">@{s.author || '匿名'}</span>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <Heart className="w-3 h-3" /> {s.likes}
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <Bookmark className="w-3 h-3" /> {s.collects}
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <MessageCircle className="w-3 h-3" /> {s.comments}
        </span>
      </div>
    </div>
  )
}

function StrategyDetail({ strategy: s, onClose }: { strategy: StrategySummary; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-gray-100 shrink-0">
        <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-100 transition-colors text-gray-500">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">{s.title || '攻略详情'}</p>
          <p className="text-xs text-gray-400 mt-0.5">@{s.author || '匿名'} · {s.collectedAt.slice(0, 10)}</p>
        </div>
        {s.sourceUrl && (
          <a
            href={s.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-xl hover:bg-gray-100 transition-colors text-gray-500"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* Tags */}
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full font-medium">
            {PARK_NAMES[s.parkId] ?? s.parkId}
          </span>
          <span className="text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">{s.platform}</span>
          {s.mentionedAttractions.slice(0, 5).map((a) => (
            <span key={a} className="text-xs text-purple-600 bg-purple-50 px-2.5 py-1 rounded-full">{a}</span>
          ))}
        </div>

        {/* Stats */}
        <div className="flex gap-5">
          <span className="flex items-center gap-1.5 text-sm text-gray-500">
            <Heart className="w-4 h-4 text-red-400" /> {s.likes} 赞
          </span>
          <span className="flex items-center gap-1.5 text-sm text-gray-500">
            <Bookmark className="w-4 h-4 text-yellow-400" /> {s.collects} 收藏
          </span>
          <span className="flex items-center gap-1.5 text-sm text-gray-500">
            <MessageCircle className="w-4 h-4 text-blue-400" /> {s.comments} 评论
          </span>
        </div>

        {/* Images */}
        {s.imageUrls.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {s.imageUrls.map((url, i) => (
              <img
                key={i}
                src={url}
                alt=""
                className="h-40 w-auto rounded-xl object-cover shrink-0 bg-gray-100"
                loading="lazy"
              />
            ))}
          </div>
        )}

        {/* AI Summary */}
        {s.aiSummary && (
          <div className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl p-4">
            <p className="text-xs font-semibold text-blue-700 mb-2">AI 提炼摘要</p>
            <p className="text-sm text-gray-700 leading-relaxed">{s.aiSummary}</p>
          </div>
        )}

        {/* Full content */}
        {s.contentExcerpt && (
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-2">原文节选</p>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{s.contentExcerpt}</p>
          </div>
        )}
      </div>
    </div>
  )
}
