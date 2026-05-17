import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, ArrowRight } from 'lucide-react'
import { login } from '@/services/api'
import { useAppStore } from '@/store/sessionStore'

export function LoginPage() {
  const navigate = useNavigate()
  const { userId, setUserId } = useAppStore()
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Already logged in — skip to visits
  useEffect(() => {
    if (userId) navigate('/visits', { replace: true })
  }, [userId, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const uid = value.trim()
    if (!uid) return
    setError(null)
    setLoading(true)
    try {
      const res = await login(uid)
      setUserId(res.userId)
      navigate('/visits')
    } catch (err) {
      setError((err as Error).message || '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 mb-4 shadow-lg">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">游园助理</h1>
            <p className="text-sm text-gray-500 mt-2 leading-relaxed">
              输入你的专属昵称，开始规划游园之旅
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                你的昵称 / 专属口令
              </label>
              <input
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="例如：小明的迪士尼之旅"
                maxLength={50}
                autoFocus
                className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3.5 text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder:text-gray-400"
              />
              <p className="text-xs text-gray-400 mt-2">
                相同昵称视为同一用户，可跨设备查看历史记录
              </p>
            </div>

            {error && (
              <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !value.trim()}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-blue-600 text-white py-3.5 text-base font-semibold hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  进入游园助理
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>

          <p className="text-xs text-center text-gray-400 mt-6">
            无需注册，昵称即身份，数据永久保留
          </p>
        </div>
      </div>
    </div>
  )
}
