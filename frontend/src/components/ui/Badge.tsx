import { cn } from './utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'green' | 'yellow' | 'red' | 'gray' | 'blue'
  className?: string
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        {
          'bg-gray-100 text-gray-700': variant === 'default',
          'bg-green-100 text-green-700': variant === 'green',
          'bg-yellow-100 text-yellow-700': variant === 'yellow',
          'bg-red-100 text-red-700': variant === 'red',
          'bg-gray-200 text-gray-500': variant === 'gray',
          'bg-blue-100 text-blue-700': variant === 'blue',
        },
        className
      )}
    >
      {children}
    </span>
  )
}
