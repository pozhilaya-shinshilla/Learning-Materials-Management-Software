import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios from 'axios'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import { Toaster } from './components/ui/sonner'
import { ThemeProvider } from './hooks/useTheme'
import '@fontsource-variable/source-sans-3/wght.css'
import '@fontsource-variable/source-serif-4/wght.css'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Повторяем только сетевые сбои и 5xx; ответы 4xx повтор не исправит.
      retry: (count, error) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined
        if (status !== undefined && status < 500) return false
        return count < 2
      },
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
            <Toaster />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
