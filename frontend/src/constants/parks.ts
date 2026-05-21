import type { ParkId } from '@/types'

export interface ParkInfo {
  id: ParkId
  name: string
  emoji: string
  description: string
  color: string
  disabled?: boolean
}

export const PARKS: ParkInfo[] = [
  {
    id: 'hongkong_disney' as ParkId,
    name: '香港迪士尼乐园',
    emoji: '✨',
    description: '亚洲经典迪士尼，独家项目众多',
    color: 'from-pink-500 to-orange-500',
  },
  {
    id: 'shanghai_disney' as ParkId,
    name: '上海迪士尼乐园',
    emoji: '🏰',
    description: '中国大陆首座迪士尼乐园',
    color: 'from-blue-500 to-purple-600',
    disabled: true,
  },
]
