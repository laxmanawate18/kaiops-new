import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { TooltipProvider } from '@/components/ui/primitives'
import { AuthProvider } from '@/lib/auth/AuthProvider'
import { queryClient } from '@/lib/queryClient'
import App from './App'
import './styles/globals.css'

const container = document.getElementById('root')
if (!container) throw new Error('Root element #root not found')

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <TooltipProvider delayDuration={250} skipDelayDuration={400}>
            <App />
            <Toaster
              position="bottom-right"
              theme="dark"
              richColors
              closeButton
              // Toasts replace every alert() in the old build. They must never
              // block interaction, and they must be dismissible.
              toastOptions={{
                classNames: {
                  toast: 'panel-raised !bg-surface-overlay !border-line-strong !text-content',
                  description: '!text-content-muted',
                  actionButton: '!bg-brand-500 !text-content-inverse',
                },
              }}
            />
          </TooltipProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
