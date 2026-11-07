import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/app/AppShell'
import { NotFound, RequireAuth, RequireRole } from '@/components/app/guards'
import { Skeleton } from '@/components/ui/skeleton'
import CatalogPage from '@/pages/CatalogPage'
import FavoritesPage from '@/pages/FavoritesPage'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import LoginPage from '@/pages/LoginPage'
import MaterialDetailPage from '@/pages/MaterialDetailPage'
import ResetPasswordPage from '@/pages/ResetPasswordPage'

// Разделы преподавателя и администратора грузятся по требованию: студентам они не нужны.
const ManagePage = lazy(() => import('@/pages/ManagePage'))
const EditMaterialPage = lazy(() => import('@/pages/EditMaterialPage'))
const UsersPage = lazy(() => import('@/pages/UsersPage'))
const EventsPage = lazy(() => import('@/pages/EventsPage'))

export default function App() {
  return (
    <Suspense fallback={<Skeleton className="m-4 h-40" />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<CatalogPage />} />
          <Route path="materials/:id" element={<MaterialDetailPage />} />
          <Route path="favorites" element={<FavoritesPage />} />
          <Route
            path="manage"
            element={
              <RequireRole roles={['teacher', 'admin']}>
                <ManagePage />
              </RequireRole>
            }
          />
          <Route
            path="manage/edit/:id"
            element={
              <RequireRole roles={['teacher', 'admin']}>
                <EditMaterialPage />
              </RequireRole>
            }
          />
          <Route
            path="admin/users"
            element={
              <RequireRole roles={['admin']}>
                <UsersPage />
              </RequireRole>
            }
          />
          <Route
            path="admin/events"
            element={
              <RequireRole roles={['admin']}>
                <EventsPage />
              </RequireRole>
            }
          />
          <Route path="admin" element={<Navigate to="/admin/users" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
