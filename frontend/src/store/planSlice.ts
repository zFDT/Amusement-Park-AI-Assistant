import type { StateCreator } from 'zustand'
import type { RouteItem, Location, PlanningInfo } from '@/types'
import { updateSession } from '@/services/api'
import type { AppState } from './sessionStore'

export interface PlanSlice {
  currentRoute: RouteItem[]
  completedAttractions: string[]
  currentLocation: Location | null

  setCurrentRoute: (route: RouteItem[]) => void
  markAttractionComplete: (attractionId: string) => Promise<void>
  setCurrentLocation: (location: Location | null) => void
  resetPlan: () => void
}

export const createPlanSlice: StateCreator<AppState, [], [], PlanSlice> = (set, get) => ({
  currentRoute: [],
  completedAttractions: [],
  currentLocation: null,

  setCurrentRoute: (currentRoute) => set({ currentRoute }),

  markAttractionComplete: async (attractionId) => {
    set((state) => ({
      completedAttractions: [...state.completedAttractions, attractionId],
    }))
    // Fire-and-forget API sync
    const { sessionId, completedAttractions } = get()
    if (sessionId) {
      updateSession(sessionId, { completedAttractions }).catch(() => {})
    }
  },

  setCurrentLocation: (currentLocation) => set({ currentLocation }),

  resetPlan: () =>
    set({
      currentRoute: [],
      completedAttractions: [],
      currentLocation: null,
    }),
})
