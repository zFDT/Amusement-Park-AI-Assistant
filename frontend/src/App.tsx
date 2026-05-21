import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from '@/store/sessionStore'

// Lazy-loaded pages for code splitting
const LoginPage = lazy(() => import('@/pages/LoginPage').then(m => ({ default: m.LoginPage })))
const VisitListPage = lazy(() => import('@/pages/VisitListPage').then(m => ({ default: m.VisitListPage })))
const PlanPage = lazy(() => import('@/pages/PlanPage').then(m => ({ default: m.PlanPage })))
const AssistantPage = lazy(() => import('@/pages/AssistantPage').then(m => ({ default: m.AssistantPage })))
const StrategiesPage = lazy(() => import('@/pages/StrategiesPage').then(m => ({ default: m.StrategiesPage })))

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-3">
        <span className="w-8 h-8 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
        <span className="text-sm text-gray-400">加载中…</span>
      </div>
    </div>
  )
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const userId = useAppStore((s) => s.userId)
  if (!userId) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route path="/visits" element={<RequireAuth><VisitListPage /></RequireAuth>} />
          <Route path="/plan" element={<RequireAuth><PlanPage /></RequireAuth>} />
          <Route path="/assistant" element={<RequireAuth><AssistantPage /></RequireAuth>} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
