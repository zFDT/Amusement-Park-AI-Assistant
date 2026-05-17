import { useState } from 'react'
import { Settings, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react'
import { useAppStore } from '@/store/sessionStore'
import type { AIConfig } from '@/types'

const PRESET_CONFIGS = [
  {
    label: 'Anthropic 官方',
    baseUrl: 'https://api.anthropic.com',
    model: 'claude-sonnet-4-6',
  },
  {
    label: '自定义代理',
    baseUrl: '',
    model: 'claude-sonnet-4-6',
  },
]

const MODEL_OPTIONS = [
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6（推荐）' },
  { value: 'claude-opus-4-6', label: 'Claude Opus 4.6（更强）' },
  { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5（更快）' },
]

export function AIConfigPanel() {
  const { aiConfig, setAIConfig } = useAppStore()
  const [expanded, setExpanded] = useState(!aiConfig)
  const [form, setForm] = useState<AIConfig>(
    aiConfig ?? { authToken: '', baseUrl: 'https://api.anthropic.com', model: 'claude-sonnet-4-6' }
  )
  const [saved, setSaved] = useState(!!aiConfig)

  const handleSave = () => {
    if (!form.authToken.trim()) return
    setAIConfig({ ...form })
    setSaved(true)
    setExpanded(false)
  }

  const handleClear = () => {
    setAIConfig(null)
    setForm({ authToken: '', baseUrl: 'https://api.anthropic.com', model: 'claude-sonnet-4-6' })
    setSaved(false)
    setExpanded(true)
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">AI 配置</span>
          {saved && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle className="w-3.5 h-3.5" />
              已配置
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
          <p className="text-xs text-gray-500">
            填入你的 Anthropic API Key，支持自定义代理地址。配置保存在本地，不会上传到服务器。
          </p>

          <div>
            <label className="block text-xs text-gray-500 mb-1">API Key</label>
            <input
              type="password"
              value={form.authToken}
              onChange={(e) => setForm((f) => ({ ...f, authToken: e.target.value }))}
              placeholder="sk-ant-..."
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Base URL</label>
            <input
              type="url"
              value={form.baseUrl}
              onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))}
              placeholder="https://api.anthropic.com"
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-2 mt-1.5">
              {PRESET_CONFIGS.filter(p => p.baseUrl).map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, baseUrl: preset.baseUrl }))}
                  className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">模型</label>
            <select
              value={form.model}
              onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {MODEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={!form.authToken.trim()}
              className="flex-1 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              保存配置
            </button>
            {saved && (
              <button
                onClick={handleClear}
                className="px-4 py-2 rounded-xl bg-gray-100 text-gray-600 text-sm hover:bg-gray-200 transition-colors"
              >
                清除
              </button>
            )}
          </div>

          <p className="text-xs text-gray-400">
            未配置时使用服务端默认 Key（如有）。
          </p>
        </div>
      )}
    </div>
  )
}
