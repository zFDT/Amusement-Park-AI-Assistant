import { useEffect, useCallback } from 'react'
import { useAppStore } from '@/store/sessionStore'
import { getWaitTimes } from '@/services/api'
import type { WaitTimeData } from '@/types'

const REFRESH_INTERVAL_MS = 5 * 60 * 1000

export function useWaitTimes() {
  const { parkId, setWaitTimes, waitTimes, lastWaitTimeUpdate } = useAppStore()

  const refresh = useCallback(async () => {
    if (!parkId) return
    try {
      const data = await getWaitTimes(parkId)
      const map: Record<string, WaitTimeData> = {}
      for (const item of data.attractions) {
        map[item.attractionId] = item
      }
      setWaitTimes(map, data.lastUpdated)
    } catch {
      // silently fail — stale data is better than crashing
    }
  }, [parkId, setWaitTimes])

  useEffect(() => {
    if (!parkId) return
    refresh()
    const timer = setInterval(refresh, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [parkId, refresh])

  return { waitTimes, lastWaitTimeUpdate, refresh }
}
