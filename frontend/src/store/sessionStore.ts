import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Message,
  PlanningInfo,
  RouteItem,
  WaitTimeData,
  Location,
  ParkId,
} from '@/types'

interface AppState {
  sessionId: string | null
  parkId: ParkId | null
  planningInfo: PlanningInfo | null
  messages: Message[]
  isStreaming: boolean
  waitTimes: Record<string, WaitTimeData>
  lastWaitTimeUpdate: string | null
  currentRoute: RouteItem[]
  completedAttractions: string[]
  currentLocation: Location | null

  setSession: (sessionId: string, parkId: ParkId, planningInfo: PlanningInfo) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string, route?: RouteItem[]) => void
  setStreaming: (streaming: boolean) => void
  setWaitTimes: (times: Record<string, WaitTimeData>, updatedAt: string) => void
  setCurrentRoute: (route: RouteItem[]) => void
  markAttractionComplete: (attractionId: string) => void
  setCurrentLocation: (location: Location | null) => void
  resetSession: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      sessionId: null,
      parkId: null,
      planningInfo: null,
      messages: [],
      isStreaming: false,
      waitTimes: {},
      lastWaitTimeUpdate: null,
      currentRoute: [],
      completedAttractions: [],
      currentLocation: null,

      setSession: (sessionId, parkId, planningInfo) =>
        set({ sessionId, parkId, planningInfo, messages: [], currentRoute: [], completedAttractions: [] }),

      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),

      updateLastMessage: (content, route) =>
        set((state) => {
          const messages = [...state.messages]
          const last = messages[messages.length - 1]
          if (last && last.role === 'assistant') {
            messages[messages.length - 1] = { ...last, content, route: route ?? last.route }
          }
          return { messages }
        }),

      setStreaming: (isStreaming) => set({ isStreaming }),

      setWaitTimes: (times, updatedAt) =>
        set({ waitTimes: times, lastWaitTimeUpdate: updatedAt }),

      setCurrentRoute: (currentRoute) => set({ currentRoute }),

      markAttractionComplete: (attractionId) =>
        set((state) => ({
          completedAttractions: [...state.completedAttractions, attractionId],
        })),

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
    }),
    {
      name: 'youyuan-session',
      partialize: (state) => ({
        sessionId: state.sessionId,
        parkId: state.parkId,
        planningInfo: state.planningInfo,
        messages: state.messages,
        currentRoute: state.currentRoute,
        completedAttractions: state.completedAttractions,
      }),
    }
  )
)
