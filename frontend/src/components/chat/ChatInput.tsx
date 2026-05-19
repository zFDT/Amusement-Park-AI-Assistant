import { useState, useRef, useCallback } from 'react'
import { Send, Square, Camera } from 'lucide-react'
import { cn } from '@/components/ui/utils'
import { useAppStore } from '@/store/sessionStore'
import { visionLocate } from '@/services/api'
import type { ParkId, AIConfig, Location } from '@/types'

/** Generate contextual quick prompts based on user's current state */
function buildQuickPrompts(
  currentLocation: Location | null,
  completedAttractions: string[],
): string[] {
  const prompts: string[] = []
  const locLabel = currentLocation?.label || currentLocation?.areaName

  if (locLabel) {
    prompts.push(`从${locLabel}出发，下一个去哪？`)
    prompts.push(`${locLabel}附近有什么项目？`)
  } else {
    prompts.push('我现在在哪里，下一个去哪？')
  }
  if (completedAttractions.length > 0) {
    prompts.push('帮我重新规划剩余行程')
  }
  prompts.push('还有哪些项目排队短？')
  prompts.push('附近有什么好吃的？')
  return prompts
}

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
  parkId?: ParkId | null
  aiConfig?: AIConfig | null
  currentLocation?: Location | null
  completedAttractions?: string[]
}

/** Compress an image file to base64, limiting width to maxWidth px */
function compressImage(file: File, maxWidth = 1024, quality = 0.7): Promise<{ base64: string; type: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let w = img.width
        let h = img.height
        if (w > maxWidth) {
          h = Math.round((h * maxWidth) / w)
          w = maxWidth
        }
        canvas.width = w
        canvas.height = h
        const ctx = canvas.getContext('2d')
        if (!ctx) { reject(new Error('Canvas not supported')); return }
        ctx.drawImage(img, 0, 0, w, h)
        const base64 = canvas.toDataURL(file.type || 'image/jpeg', quality).split(',')[1]
        resolve({ base64, type: file.type || 'image/jpeg' })
      }
      img.onerror = () => reject(new Error('Image load failed'))
      img.src = reader.result as string
    }
    reader.onerror = () => reject(new Error('File read failed'))
    reader.readAsDataURL(file)
  })
}

export function ChatInput({ onSend, onStop, isStreaming, parkId, aiConfig, currentLocation, completedAttractions }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [locating, setLocating] = useState(false)
  const [locateError, setLocateError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const setCurrentLocation = useAppStore((s) => s.setCurrentLocation)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue('')
    setLocateError(null)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  const handleCameraClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !parkId) return

    setLocating(true)
    setLocateError(null)
    try {
      const { base64, type } = await compressImage(file)
      const result = await visionLocate(base64, type, parkId, aiConfig)
      const label = result.attractionName || result.label
      setCurrentLocation({
        areaName: result.areaName ?? undefined,
        attractionName: result.attractionName ?? undefined,
        label,
      })
      setValue(`我现在在${label}附近，`)
      // clear the input so the same file can be re-selected if needed
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setLocateError((err as Error).message || '识别失败，请重试')
    } finally {
      setLocating(false)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap">
        {buildQuickPrompts(currentLocation ?? null, completedAttractions ?? []).map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSend(prompt)}
            disabled={isStreaming}
            className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600 transition-colors disabled:opacity-40"
          >
            {prompt}
          </button>
        ))}
      </div>
      {locateError && (
        <div className="text-xs text-red-500 px-1">{locateError}</div>
      )}
      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileChange}
          className="hidden"
          aria-label="拍照识别位置"
        />
        <button
          onClick={handleCameraClick}
          disabled={isStreaming || locating || !parkId}
          className={cn(
            'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors',
            locating
              ? 'bg-blue-100 text-blue-500 animate-pulse'
              : 'bg-gray-100 text-gray-500 hover:bg-blue-50 hover:text-blue-600',
            'disabled:opacity-40 disabled:cursor-not-allowed'
          )}
          aria-label="拍照识别位置"
          title="拍照识别当前位置"
        >
          <Camera className="w-4 h-4" />
        </button>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="告诉我你的情况，或者问任何游园问题..."
          rows={1}
          className={cn(
            'flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder:text-gray-400 leading-relaxed'
          )}
        />
        <button
          onClick={isStreaming ? onStop : handleSend}
          disabled={!isStreaming && !value.trim()}
          className={cn(
            'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors',
            isStreaming
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 disabled:cursor-not-allowed'
          )}
          aria-label={isStreaming ? '停止' : '发送'}
        >
          {isStreaming ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}
