import type { PlanningInfo, WaitTimesResponse, RouteItem } from '@/types'

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

export interface CreateSessionResponse {
  sessionId: string
  initialPlan: string
  route: RouteItem[]
}

export function createSession(planningInfo: PlanningInfo): Promise<CreateSessionResponse> {
  return request('/sessions', {
    method: 'POST',
    body: JSON.stringify(planningInfo),
  })
}

export function getWaitTimes(parkId: string): Promise<WaitTimesResponse> {
  return request(`/waittimes/${parkId}`)
}

export function getAttractions(parkId: string) {
  return request(`/parks/${parkId}/attractions`)
}
