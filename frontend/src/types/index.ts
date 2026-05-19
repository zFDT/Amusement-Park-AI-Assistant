export type ParkId = 'shanghai_disney' | 'hongkong_disney'

export interface Park {
  id: ParkId
  name: string
  nameEn: string
  location: string
  timezone: string
}

export type AttractionCategory =
  | 'thrill_ride'
  | 'family_ride'
  | 'show'
  | 'character_meet'
  | 'dining'
  | 'shopping'
  | 'parade'

export interface Attraction {
  id: string
  parkId: ParkId
  name: string
  nameEn: string
  category: AttractionCategory
  areaName: string
  description: string
  durationMinutes: number
  minHeightCm?: number
  coordinates: { lat: number; lng: number }
  isLightningLane: boolean
  suitableFor: string[]
  notSuitableFor: string[]
  tips?: string
}

export type WaitStatus = 'open' | 'closed' | 'down' | 'unknown'

export interface WaitTimeData {
  attractionId: string
  attractionName?: string
  waitMinutes: number | null
  status: WaitStatus
  lastUpdated: string
}

export interface WaitTimesResponse {
  parkId: ParkId
  lastUpdated: string
  attractions: WaitTimeData[]
}

export type PreferenceTag =
  | 'thrill_rides'
  | 'family_rides'
  | 'shows'
  | 'character_meet'
  | 'photography'
  | 'dining'
  | 'parades'

export type SpecialNeed = 'wheelchair' | 'pregnant' | 'heart_condition' | 'fear_of_dark' | 'fear_of_heights'

export interface PartyMember {
  type: 'adult' | 'child' | 'elderly'
  age?: number
}

export interface PlanningInfo {
  parkId: ParkId
  visitDate: string
  entryTime: string
  exitTime: string
  party: PartyMember[]
  preferences: PreferenceTag[]
  mustDoAttractions: string[]
  fitnessLevel: 1 | 2 | 3 | 4 | 5
  experienceLevel: 'first_time' | 'visited_before' | 'frequent'
  specialNotes: string
  specialNeeds: SpecialNeed[]
}

export interface RouteItem {
  time: string
  attractionId: string
  attractionName: string
  estimatedWait: number
  note?: string
  type: 'attraction' | 'dining' | 'show' | 'break'
  areaName?: string
}

export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  role: MessageRole
  content: string
  route?: RouteItem[]
  createdAt: string
  isError?: boolean
}

export interface SessionData {
  sessionId: string
  parkId: ParkId
  planningInfo: PlanningInfo
  createdAt: string
  expiresAt: string
}

export interface Location {
  areaName?: string
  attractionId?: string
  attractionName?: string
  lat?: number
  lng?: number
  label?: string
}

export type APIMode = 'openai' | 'openai-responses' | 'ollama' | 'anthropic' | 'gemini' | 'deepseek'
export type AIConfigSource = 'custom' | 'internal'

export interface AIConfig {
  source?: AIConfigSource
  apiKey?: string
  baseUrl?: string
  apiMode?: APIMode
  modelId?: string
  internalCode?: string | null

  // legacy fields for backward compatibility
  authToken?: string
  model?: string
}

export interface ChatRequest {
  sessionId: string
  message: string
  currentLocation?: Location
  aiConfig?: AIConfig
}
