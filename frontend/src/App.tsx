import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { VisitListPage } from '@/pages/VisitListPage'
import { PlanPage } from '@/pages/PlanPage'
import { AssistantPage } from '@/pages/AssistantPage'
import { StrategiesPage } from '@/pages/StrategiesPage'
import { useAppStore } from '@/store/sessionStore'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const userId = useAppStore((s) => s.userId)
  if (!userId) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/visits" element={<RequireAuth><VisitListPage /></RequireAuth>} />
        <Route path="/plan" element={<RequireAuth><PlanPage /></RequireAuth>} />
        <Route path="/assistant" element={<RequireAuth><AssistantPage /></RequireAuth>} />
        <Route path="/strategies" element={<StrategiesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
