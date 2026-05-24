import type { PlanningInfo, WaitTimesResponse, RouteItem, AIConfig, WaitStatus, ParkId } from '@/types'
import { toServerAIConfig } from '@/services/aiConfig'

const BASE_URL = '/api'
const REQUEST_TIMEOUT_MS = 30_000 // 30s timeout for regular requests
const SESSION_TIMEOUT_MS = 300_000 // 5min timeout for AI session creation (v4-pro thinking + large prompt)

async function request<T>(
  path: string, 
  options?: RequestInit, 
  timeoutMs?: number, 
  maxRetries: number = 0
): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs ?? REQUEST_TIMEOUT_MS)

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      ...options,
    })
    
    if (!res.ok) {
      // 对 5xx 错误执行重试（如果是 GET 请求或幂等请求）
      const isIdempotent = options?.method === 'GET' || !options?.method
      if (res.status >= 500 && maxRetries > 0 && isIdempotent) {
        console.warn(`API 请求失败 ${res.status}，准备重试... 剩余次数: ${maxRetries}`)
        return request<T>(path, options, timeoutMs, maxRetries - 1)
      }

      let detail = '请求失败'
      try {
        const error = await res.json()
        detail = error.detail ?? error.message ?? `HTTP ${res.status}`
      } catch {
        detail = `服务器错误 (${res.status})`
      }
      throw new Error(detail)
    }
    return res.json()
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接后重试')
    }
    
    // 网络错误（fetch 失败）重试
    const isIdempotent = options?.method === 'GET' || !options?.method
    if (maxRetries > 0 && isIdempotent) {
      return request<T>(path, options, timeoutMs, maxRetries - 1)
    }
    
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

function snakeToCamelPlanningInfo(raw: Record<string, unknown>): PlanningInfo {
  return {
    parkId: raw.park_id as PlanningInfo['parkId'],
    visitDate: raw.visit_date as string,
    entryTime: raw.entry_time as string,
    exitTime: raw.exit_time as string,
    party: raw.party as PlanningInfo['party'],
    preferences: (raw.preferences ?? []) as PlanningInfo['preferences'],
    mustDoAttractions: (raw.must_do_attractions ?? []) as string[],
    fitnessLevel: (raw.fitness_level ?? 3) as PlanningInfo['fitnessLevel'],
    experienceLevel: (raw.experience_level ?? 'first_time') as PlanningInfo['experienceLevel'],
    specialNotes: (raw.special_notes ?? '') as string,
    specialNeeds: (raw.special_needs ?? []) as PlanningInfo['specialNeeds'],
  }
}

export interface CreateSessionResponse {
  sessionId: string
  initialPlan: string
  route: RouteItem[]
}

/** 获取会话消息历史（刷新恢复用） */
export async function getSessionMessages(sessionId: string): Promise<{ role: string; content: string; created_at?: string }[]> {
  const res = await request<{ messages: { role: string; content: string; created_at?: string }[] }>(`/sessions/${sessionId}/messages`)
  return res.messages || []
}

export interface ResumeSessionResponse {
  sessionId: string
  planning: PlanningInfo
  completedAttractions: string[]
  currentLocation: Record<string, unknown> | null
}

export interface ShareSessionResponse {
  code: string
  expiresInSeconds: number
}

export function createSession(planningInfo: PlanningInfo, aiConfig?: AIConfig | null, userId?: string): Promise<CreateSessionResponse> {
  return request('/sessions', {
    method: 'POST',
    body: JSON.stringify({
      park_id: planningInfo.parkId,
      visit_date: planningInfo.visitDate,
      entry_time: planningInfo.entryTime,
      exit_time: planningInfo.exitTime,
      party: planningInfo.party,
      preferences: planningInfo.preferences,
      must_do_attractions: planningInfo.mustDoAttractions,
      fitness_level: planningInfo.fitnessLevel,
      experience_level: planningInfo.experienceLevel,
      special_notes: planningInfo.specialNotes,
      special_needs: planningInfo.specialNeeds,
      user_id: userId,
      ai_config: toServerAIConfig(aiConfig),
    }),
  }, SESSION_TIMEOUT_MS)
}

/** 流式创建会话：通过 SSE 实时获取 AI 路线生成进度，无超时限制。
 *  - onSession: 收到 session_id 时立即回调（用于提前保存，刷新可恢复）
 *  - onProgress: 收到文本增量时回调
 */
export async function createSessionStream(
  planningInfo: PlanningInfo,
  aiConfig: AIConfig | null | undefined,
  userId: string | undefined,
  onProgress: (text: string) => void,
  onSession?: (sessionId: string) => void,
): Promise<CreateSessionResponse> {
  const body = JSON.stringify({
    park_id: planningInfo.parkId,
    visit_date: planningInfo.visitDate,
    entry_time: planningInfo.entryTime,
    exit_time: planningInfo.exitTime,
    party: planningInfo.party,
    preferences: planningInfo.preferences,
    must_do_attractions: planningInfo.mustDoAttractions,
    fitness_level: planningInfo.fitnessLevel,
    experience_level: planningInfo.experienceLevel,
    special_notes: planningInfo.specialNotes,
    special_needs: planningInfo.specialNeeds,
    user_id: userId,
    ai_config: toServerAIConfig(aiConfig),
  })

  const res = await fetch('/api/sessions/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })

  if (!res.ok) {
    let detail = '创建会话失败'
    try { const err = await res.json(); detail = err.detail || detail } catch {}
    throw new Error(detail)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('无法读取响应流')

  const decoder = new TextDecoder()
  let sessionId = ''
  let initialPlan = ''
  let route: RouteItem[] | undefined

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value, { stream: true })
    for (const line of text.split('\n')) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') continue

      try {
        const event = JSON.parse(data)
        if (event.type === 'session') {
          sessionId = event.session_id
          onSession?.(sessionId)
        } else if (event.type === 'text') {
          initialPlan += event.content
          onProgress(initialPlan)
        } else if (event.type === 'route') {
          route = event.route as RouteItem[]
        } else if (event.type === 'error') {
          throw new Error(event.message || 'AI 生成失败')
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue // skip non-JSON lines
        throw e
      }
    }
  }

  if (!sessionId) throw new Error('未收到会话ID')
  return { sessionId, initialPlan, route }
}

export function updateSession(
  sessionId: string,
  data: { completedAttractions?: string[]; currentLocation?: Record<string, unknown> | null }
): Promise<{ sessionId: string; completedAttractions: string[] }> {
  return request(`/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      completed_attractions: data.completedAttractions,
      current_location: data.currentLocation,
    }),
  })
}

export function shareSession(sessionId: string): Promise<ShareSessionResponse> {
  return request(`/sessions/${sessionId}/share`, { method: 'POST' })
}

export function resumeByCode(code: string): Promise<ResumeSessionResponse> {
  return request<{
    session_id: string
    planning: Record<string, unknown>
    completed_attractions: string[]
    current_location: Record<string, unknown> | null
  }>(`/sessions/resume/${code}`).then((raw) => ({
    sessionId: raw.session_id,
    planning: snakeToCamelPlanningInfo(raw.planning),
    completedAttractions: raw.completed_attractions,
    currentLocation: raw.current_location,
  }))
}

export function getWaitTimes(parkId: string): Promise<WaitTimesResponse> {
  return request<{
    park_id: string
    last_updated: string
    attractions: Array<{
      attraction_id: string
      attraction_name: string | null
      wait_minutes: number | null
      status: string
      last_updated: string
    }>
  }>(`/waittimes/${parkId}`).then((r) => ({
    parkId: r.park_id as WaitTimesResponse['parkId'],
    lastUpdated: r.last_updated,
    attractions: r.attractions.map((a) => ({
      attractionId: a.attraction_id,
      attractionName: a.attraction_name ?? undefined,
      waitMinutes: a.wait_minutes,
      status: a.status as WaitStatus,
      lastUpdated: a.last_updated,
    })),
  }))
}

export function getAttractions(parkId: string) {
  return request(`/parks/${parkId}/attractions`)
}

// ── User / Visit ──────────────────────────────────────────────────────────────

export interface LoginResponse {
  userId: string
  isNew: boolean
}

export interface VisitSummary {
  visitId: string
  parkId: string
  visitDate: string
  status: 'active' | 'archived'
  completedCount: number
  createdAt: string
  planningSnapshot: Record<string, unknown> | null
}

export interface VisitListResponse {
  userId: string
  visits: VisitSummary[]
}

export function login(userId: string): Promise<LoginResponse> {
  return request<{ user_id: string; is_new: boolean }>('/users/login', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  }).then((r) => ({ userId: r.user_id, isNew: r.is_new }))
}

export function getVisits(userId: string): Promise<VisitListResponse> {
  return request<{ user_id: string; visits: Array<Record<string, unknown>> }>(`/users/${userId}/visits`)
    .then((r) => ({
      userId: r.user_id,
      visits: r.visits.map((v) => ({
        visitId: v.visit_id as string,
        parkId: v.park_id as string,
        visitDate: v.visit_date as string,
        status: v.status as 'active' | 'archived',
        completedCount: v.completed_count as number,
        createdAt: v.created_at as string,
        planningSnapshot: (v.planning_snapshot as Record<string, unknown>) ?? null,
      })),
    }))
}

export function archiveVisit(userId: string, visitId: string): Promise<{ visitId: string; status: string }> {
  return request<{ visit_id: string; status: string }>(`/users/${userId}/visits/${visitId}/archive`, {
    method: 'PATCH',
  }).then((r) => ({ visitId: r.visit_id, status: r.status }))
}

// ── Strategies ────────────────────────────────────────────────────────────────

export interface StructuredSummary {
  is_useful: boolean
  mentioned_attractions: string[]
  suggested_route: string | null
  tips: string | null
  summary: string | null
}

export interface StrategySummary {
  strategyId: string
  parkId: string
  platform: string
  sourceUrl: string
  title: string
  contentExcerpt: string
  author: string
  likes: number
  collects: number
  comments: number
  imageUrls: string[]
  aiSummary: string | null
  structuredSummary: StructuredSummary | null
  collectedAt: string
  mentionedAttractions: string[]
}

export interface StrategyListResponse {
  total: number
  strategies: StrategySummary[]
}

export function getStrategies(params?: {
  parkId?: string
  platform?: string
  q?: string
  limit?: number
  offset?: number
}): Promise<StrategyListResponse> {
  const qs = new URLSearchParams()
  if (params?.parkId) qs.set('park_id', params.parkId)
  if (params?.platform) qs.set('platform', params.platform)
  if (params?.q) qs.set('q', params.q)
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return request<{
    total: number
    strategies: Array<Record<string, unknown>>
  }>(`/strategies${query ? `?${query}` : ''}`).then((r) => ({
    total: r.total,
    strategies: r.strategies.map((s) => ({
      strategyId: s.strategy_id as string,
      parkId: s.park_id as string,
      platform: s.platform as string,
      sourceUrl: s.source_url as string,
      title: s.title as string,
      contentExcerpt: s.content_excerpt as string,
      author: s.author as string,
      likes: s.likes as number,
      collects: s.collects as number,
      comments: s.comments as number,
      imageUrls: (s.image_urls ?? []) as string[],
      aiSummary: (s.ai_summary ?? null) as string | null,
      structuredSummary: (s.structured_summary ?? null) as StructuredSummary | null,
      collectedAt: s.collected_at as string,
      mentionedAttractions: (s.mentioned_attractions ?? []) as string[],
    })),
  }))
}

// ── Vision ────────────────────────────────────────────────────────────────────

export interface VisionLocateResponse {
  areaName: string | null
  attractionName: string | null
  label: string
  confidence: string
}

export function visionLocate(
  imageBase64: string,
  imageType: string,
  parkId: ParkId,
  aiConfig?: AIConfig | null,
): Promise<VisionLocateResponse> {
  return request<{
    area_name: string | null
    attraction_name: string | null
    label: string
    confidence: string
  }>('/vision/locate', {
    method: 'POST',
    body: JSON.stringify({
      image_base64: imageBase64,
      image_type: imageType,
      park_id: parkId,
      ai_config: toServerAIConfig(aiConfig),
    }),
  }).then((r) => ({
    areaName: r.area_name,
    attractionName: r.attraction_name,
    label: r.label,
    confidence: r.confidence,
  }))
}
