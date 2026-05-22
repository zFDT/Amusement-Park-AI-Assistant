import { useState } from 'react'
import { Settings, ChevronDown, ChevronUp, CheckCircle, ShieldCheck, KeyRound } from 'lucide-react'
import { useAppStore } from '@/store/sessionStore'
import type { AIConfig, APIMode } from '@/types'
import { API_MODE_HELPERS, inferAPIConfigMode, normalizeAIConfig } from '@/services/aiConfig'

const PROVIDER_PRESETS: Record<string, { label: string; baseUrl: string; apiMode: APIMode; modelId: string }> = {
  deepseek: { label: 'DeepSeek', baseUrl: 'https://api.deepseek.com', apiMode: 'deepseek', modelId: 'deepseek-v4-flash' },
  qwen: { label: 'Qwen', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', apiMode: 'openai', modelId: 'qwen-plus' },
  openai: { label: 'OpenAI (GPT)', baseUrl: 'https://api.openai.com/v1', apiMode: 'openai', modelId: 'gpt-4.1-mini' },
  claude: { label: 'Claude', baseUrl: 'https://api.anthropic.com', apiMode: 'anthropic', modelId: 'claude-sonnet-4-6' },
  gemini: { label: 'Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta', apiMode: 'gemini', modelId: 'gemini-2.5-pro' },
  grok: { label: 'Grok', baseUrl: 'https://api.x.ai/v1', apiMode: 'openai', modelId: 'grok-4' },
  kimi: { label: 'Kimi', baseUrl: 'https://api.moonshot.cn/v1', apiMode: 'openai', modelId: 'kimi-k2' },
  minimax: { label: 'MiniMax', baseUrl: 'https://api.minimax.chat/v1', apiMode: 'openai', modelId: 'abab6.5-chat' },
}

const API_MODE_OPTIONS: { value: APIMode; label: string }[] = [
  { value: 'openai', label: 'openai' },
  { value: 'openai-responses', label: 'openai-responses' },
  { value: 'ollama', label: 'ollama' },
  { value: 'anthropic', label: 'anthropic' },
  { value: 'gemini', label: 'gemini' },
  { value: 'deepseek', label: 'deepseek' },
]

const EMPTY_CONFIG: AIConfig = {
  source: 'custom',
  apiKey: '',
  baseUrl: 'https://api.anthropic.com',
  apiMode: 'anthropic',
  modelId: 'claude-sonnet-4-6',
  internalCode: '',
}

export function AIConfigPanel() {
  const { aiConfig, setAIConfig } = useAppStore()
  const [expanded, setExpanded] = useState(!aiConfig)
  const [saved, setSaved] = useState(!!aiConfig)
  const [error, setError] = useState<string | null>(null)
  const [selectedProvider, setSelectedProvider] = useState<keyof typeof PROVIDER_PRESETS>('claude')
  const [form, setForm] = useState<AIConfig>(normalizeAIConfig(aiConfig) || EMPTY_CONFIG)

  const handleSave = () => {
    setError(null)

    if (form.source === 'internal') {
      const code = (form.internalCode ?? '').trim()
      if (!code) {
        setError('请输入内测码')
        return
      }

      setAIConfig({
        source: 'internal',
        internalCode: code,
      })
      setSaved(true)
      setExpanded(false)
      return
    }

    if ((form.apiMode ?? 'anthropic') !== 'ollama' && !(form.apiKey ?? '').trim()) {
      setError('请填写 API Key')
      return
    }
    if (!(form.baseUrl ?? '').trim()) {
      setError('请填写 Base URL')
      return
    }
    if (!(form.modelId ?? '').trim()) {
      setError('请填写 Model ID')
      return
    }

    setAIConfig({
      source: 'custom',
      apiKey: form.apiKey ?? '',
      baseUrl: form.baseUrl ?? '',
      apiMode: form.apiMode ?? inferAPIConfigMode(form),
      modelId: form.modelId ?? '',
      internalCode: null,
    })
    setSaved(true)
    setExpanded(false)
  }

  const handleClear = () => {
    setAIConfig(null)
    setForm(EMPTY_CONFIG)
    setSaved(false)
    setExpanded(true)
    setError(null)
  }

  const applyProviderPreset = (provider: keyof typeof PROVIDER_PRESETS) => {
    setSelectedProvider(provider)
    const preset = PROVIDER_PRESETS[provider]
    setForm((f) => ({
      ...f,
      source: 'custom',
      baseUrl: preset.baseUrl,
      apiMode: preset.apiMode,
      modelId: preset.modelId,
    }))
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
            支持 DeepSeek、Qwen、OpenAI、Claude、Gemini、Grok、Kimi、MiniMax；也可切换到内测码模式使用服务端预置配置。
          </p>

          <div className="grid grid-cols-2 gap-2 rounded-2xl bg-gray-50 p-1">
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, source: 'custom' }))}
              className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                (form.source ?? 'custom') === 'custom' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
              }`}
            >
              <KeyRound className="w-4 h-4" />
              自定义配置
            </button>
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, source: 'internal', apiKey: '', baseUrl: '', modelId: '' }))}
              className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                form.source === 'internal' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              内测码
            </button>
          </div>

          {form.source !== 'internal' ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">预设提供商</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => applyProviderPreset(e.target.value as keyof typeof PROVIDER_PRESETS)}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Object.entries(PROVIDER_PRESETS).map(([value, preset]) => (
                    <option key={value} value={value}>{preset.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">API Key</label>
                <input
                  type="password"
                  value={form.apiKey ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, apiKey: e.target.value }))}
                  placeholder="请输入 API Key"
                  className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Base URL</label>
                <input
                  type="url"
                  value={form.baseUrl ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))}
                  placeholder="https://api.example.com/v1"
                  className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div className="flex flex-wrap gap-2 mt-1.5">
                  {Object.values(PROVIDER_PRESETS).map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, baseUrl: preset.baseUrl, apiMode: preset.apiMode, modelId: preset.modelId }))}
                      className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">API Mode</label>
                <select
                  value={form.apiMode ?? 'anthropic'}
                  onChange={(e) => setForm((f) => ({ ...f, apiMode: e.target.value as APIMode }))}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {API_MODE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-400">{API_MODE_HELPERS[form.apiMode ?? 'anthropic']}</p>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Model ID</label>
                <input
                  type="text"
                  value={form.modelId ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, modelId: e.target.value }))}
                  placeholder="例如：gpt-4.1-mini / claude-sonnet-4-6"
                  className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-xs text-gray-500 mb-1">内测码</label>
              <input
                type="password"
                value={form.internalCode ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, internalCode: e.target.value }))}
                placeholder="请输入内测码，例如 vip666"
                className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              />
              <p className="mt-1 text-xs text-gray-400">若内测码正确，后端将从 `AI_INTERNAL_PROFILES` 中读取配置。</p>
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={form.source !== 'internal' && !(form.apiKey ?? '').trim() && (form.apiMode ?? 'anthropic') !== 'ollama'}
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
            未配置时使用服务端默认 Key/内测配置（如有）。
          </p>
        </div>
      )}
    </div>
  )
}
