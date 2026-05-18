import type { AIConfig, APIMode } from '@/types'

export interface ServerAIConfig {
  source: 'custom' | 'internal'
  api_key: string
  base_url: string
  api_mode: APIMode
  model_id: string
  internal_code?: string | null
}

export const API_MODE_HELPERS: Record<APIMode, string> = {
  openai: 'OpenAI 兼容聊天接口：/chat/completions',
  'openai-responses': 'OpenAI Responses API：/responses',
  ollama: 'Ollama 原生聊天接口：/api/chat',
  anthropic: 'Anthropic Messages API：/v1/messages',
  gemini: 'Gemini SSE 接口：/v1beta/models/{model}:streamGenerateContent?alt=sse',
  deepseek: 'DeepSeek 兼容 OpenAI 聊天接口：/chat/completions（支持思考模式）',
}

export function inferAPIConfigMode(aiConfig?: AIConfig | null): APIMode {
  const hint = [aiConfig?.apiMode, aiConfig?.baseUrl, aiConfig?.modelId, aiConfig?.model]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()

  if (hint.includes('anthropic') || hint.includes('claude')) return 'anthropic'
  if (hint.includes('googleapis') || hint.includes('gemini')) return 'gemini'
  if (hint.includes('ollama')) return 'ollama'
  if (hint.includes('responses')) return 'openai-responses'
  return 'openai'
}

export function normalizeAIConfig(aiConfig: AIConfig | null | undefined): AIConfig {
  return {
    source: aiConfig?.source ?? 'custom',
    apiMode: aiConfig?.apiMode ?? inferAPIConfigMode(aiConfig),
    apiKey: aiConfig?.apiKey ?? aiConfig?.authToken ?? '',
    baseUrl: aiConfig?.baseUrl ?? '',
    modelId: aiConfig?.modelId ?? aiConfig?.model ?? '',
    internalCode: aiConfig?.internalCode ?? null,
    authToken: aiConfig?.authToken,
    model: aiConfig?.model,
  }
}

export function toServerAIConfig(aiConfig: AIConfig | null | undefined): ServerAIConfig | undefined {
  if (!aiConfig) return undefined
  const normalized = normalizeAIConfig(aiConfig)
  return {
    source: normalized.source ?? 'custom',
    api_key: normalized.apiKey ?? '',
    base_url: normalized.baseUrl ?? '',
    api_mode: normalized.apiMode ?? 'openai',
    model_id: normalized.modelId ?? '',
    internal_code: normalized.internalCode ?? null,
  }
}