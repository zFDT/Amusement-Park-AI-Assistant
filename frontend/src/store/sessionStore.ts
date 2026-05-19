import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Message,
  PlanningInfo,
  RouteItem,
  WaitTimeData,
  Location,
  ParkId,
  AIConfig,
} from '@/types'
import { updateSession } from '@/services/api'

interface AppState {
  userId: string | null
  sessionId: string | null
  parkId: ParkId | null
  planningInfo: PlanningInfo | null
  aiConfig: AIConfig | null
  messages: Message[]
  isStreaming: boolean
  waitTimes: Record<string, WaitTimeData>
  lastWaitTimeUpdate: string | null
  currentRoute: RouteItem[]
  completedAttractions: string[]
  currentLocation: Location | null

  setUserId: (userId: string) => void
  setSession: (sessionId: string, parkId: ParkId, planningInfo: PlanningInfo) => void
  resumeSession: (sessionId: string, parkId: ParkId, planningInfo: PlanningInfo, completedAttractions: string[], initialMessages?: Message[]) => void
  setAIConfig: (config: AIConfig | null) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string, route?: RouteItem[], isError?: boolean) => void
  removeLastMessage: () => void
  setStreaming: (streaming: boolean) => void
  setWaitTimes: (times: Record<string, WaitTimeData>, updatedAt: string) => void
  setCurrentRoute: (route: RouteItem[]) => void
  markAttractionComplete: (attractionId: string) => Promise<void>
  setCurrentLocation: (location: Location | null) => void
  resetSession: () => void
  logout: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      sessionId: null,
      parkId: null,
      planningInfo: null,
      aiConfig: null,
      messages: [],
      isStreaming: false,
      waitTimes: {},
      lastWaitTimeUpdate: null,
      currentRoute: [],
      completedAttractions: [],
      currentLocation: null,

      setUserId: (userId) => set({ userId }),

      setSession: (sessionId, parkId, planningInfo) =>
        set({ sessionId, parkId, planningInfo, messages: [], currentRoute: [], completedAttractions: [] }),

      resumeSession: (sessionId, parkId, planningInfo, completedAttractions, initialMessages = []) =>
        set({ sessionId, parkId, planningInfo, completedAttractions, messages: initialMessages, currentRoute: [] }),

      setAIConfig: (aiConfig) => set({ aiConfig }),

      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),

      updateLastMessage: (content, route, isError) =>
        set((state) => {
          const messages = [...state.messages]
          const last = messages[messages.length - 1]
          if (last && last.role === 'assistant') {
            messages[messages.length - 1] = {
              ...last,
              content,
              route: route ?? last.route,
              ...(isError !== undefined ? { isError } : {}),
            }
          }
          return { messages }
        }),

      removeLastMessage: () =>
        set((state) => {
          const messages = [...state.messages]
          if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
            messages.pop()
          }
          return { messages }
        }),

      setStreaming: (isStreaming) => set({ isStreaming }),

      setWaitTimes: (times, updatedAt) =>
        set({ waitTimes: times, lastWaitTimeUpdate: updatedAt }),

      setCurrentRoute: (currentRoute) => set({ currentRoute }),

      markAttractionComplete: async (attractionId) => {
        set((state) => ({
          completedAttractions: [...state.completedAttractions, attractionId],
        }))
        // Fire-and-forget API sync; failure is non-critical (local state already updated)
        const { sessionId, completedAttractions } = useAppStore.getState()
        if (sessionId) {
          updateSession(sessionId, { completedAttractions }).catch(() => {})
        }
      },

      setCurrentLocation: (currentLocation) => set({ currentLocation }),

      resetSession: () =>
        set({
          sessionId: null,
          parkId: null,
          planningInfo: null,
          messages: [],
          currentRoute: [],
          completedAttractions: [],
          currentLocation: null,
        }),

      logout: () =>
        set({
          userId: null,
          sessionId: null,
          parkId: null,
          planningInfo: null,
          messages: [],
          currentRoute: [],
          completedAttractions: [],
          currentLocation: null,
        }),
    }),
    {
      name: 'youyuan-session',
      partialize: (state) => ({
        userId: state.userId,
        sessionId: state.sessionId,
        parkId: state.parkId,
        planningInfo: state.planningInfo,
        aiConfig: state.aiConfig,
        messages: state.messages,
        currentRoute: state.currentRoute,
        completedAttractions: state.completedAttractions,
      }),
    }
  )
)
