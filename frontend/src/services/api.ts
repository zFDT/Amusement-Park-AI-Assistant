import type { PlanningInfo, WaitTimesResponse, RouteItem, AIConfig } from '@/types'
import { toServerAIConfig } from '@/services/aiConfig'

const BASE_URL = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail ?? 'Request failed')
  }
  return res.json()
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
      ...planningInfo,
      user_id: userId,
      ai_config: toServerAIConfig(aiConfig),
    }),
  })
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
  return request(`/waittimes/${parkId}`)
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
      collectedAt: s.collected_at as string,
      mentionedAttractions: (s.mentioned_attractions ?? []) as string[],
    })),
  }))
}
