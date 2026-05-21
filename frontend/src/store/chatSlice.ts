import type { StateCreator } from 'zustand'
import type { Message, RouteItem } from '@/types'

export interface ChatSlice {
  messages: Message[]
  isStreaming: boolean

  addMessage: (message: Message) => void
  updateLastMessage: (content: string, route?: RouteItem[], isError?: boolean) => void
  removeLastMessage: () => void
  setStreaming: (streaming: boolean) => void
  clearMessages: () => void
}

export const createChatSlice: StateCreator<ChatSlice, [], [], ChatSlice> = (set) => ({
  messages: [],
  isStreaming: false,

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

  clearMessages: () => set({ messages: [] }),
})
