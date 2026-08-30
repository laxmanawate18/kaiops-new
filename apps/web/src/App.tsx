import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { BootScreen } from '@/components/layout/BootScreen'
import { pageVariants } from '@/lib/motion'
import { applyTitle } from '@/lib/chrome'
import { useEffect } from 'react'

// Route-level code splitting. The console is the landing surface, so it is
// the only one worth eagerly loading; everything else arrives on demand.
import ConsolePage from '@/pages/ConsolePage'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ServicesPage = lazy(() => import('@/pages/ServicesPage'))
const ServiceDetailPage = lazy(() => import('@/pages/ServiceDetailPage'))
const ServiceFormPage = lazy(() => import('@/pages/ServiceFormPage'))
const FeedbackPage = lazy(() => import('@/pages/FeedbackPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

function Page({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="h-full w-full"
    >
      {children}
    </motion.div>
  )
}

export default function App() {
  const location = useLocation()

  // A2: dynamic document title per route.
  useEffect(() => {
    applyTitle(location.pathname)
  }, [location.pathname])

  return (
    <Suspense fallback={<BootScreen label="Loading workspace" />}>
      <AnimatePresence mode="wait" initial={false}>
        <Routes location={location} key={location.pathname}>
          {/* Public */}
          <Route
            path="/login"
            element={
              <Page>
                <LoginPage />
              </Page>
            }
          />
          <Route
            path="/register"
            element={
              <Page>
                <RegisterPage />
              </Page>
            }
          />

          {/* Authenticated shell */}
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/console" replace />} />
            <Route
              path="/console"
              element={
                <Page>
                  <ConsolePage />
                </Page>
              }
            />
            <Route
              path="/console/:sessionId"
              element={
                <Page>
                  <ConsolePage />
                </Page>
              }
            />
            <Route
              path="/dashboard"
              element={
                <Page>
                  <DashboardPage />
                </Page>
              }
            />
            <Route
              path="/services"
              element={
                <Page>
                  <ServicesPage />
                </Page>
              }
            />
            <Route
              path="/services/new"
              element={
                <ProtectedRoute requires="manage">
                  <Page>
                    <ServiceFormPage />
                  </Page>
                </ProtectedRoute>
              }
            />
            <Route
              path="/services/:id"
              element={
                <Page>
                  <ServiceDetailPage />
                </Page>
              }
            />
            <Route
              path="/services/:id/edit"
              element={
                <ProtectedRoute requires="manage">
                  <Page>
                    <ServiceFormPage />
                  </Page>
                </ProtectedRoute>
              }
            />
            <Route
              path="/feedback"
              element={
                <ProtectedRoute requires="manage">
                  <Page>
                    <FeedbackPage />
                  </Page>
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute requires="admin">
                  <Page>
                    <AdminPage />
                  </Page>
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <Page>
                  <ProfilePage />
                </Page>
              }
            />
            <Route
              path="*"
              element={
                <Page>
                  <NotFoundPage />
                </Page>
              }
            />
          </Route>
        </Routes>
      </AnimatePresence>
    </Suspense>
  )
}
