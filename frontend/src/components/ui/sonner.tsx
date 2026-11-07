import { Toaster as Sonner } from 'sonner'
import { useTheme } from '@/hooks/useTheme'

export function Toaster() {
  const { choice } = useTheme()
  return (
    <Sonner
      theme={choice}
      position="top-center"
      closeButton
      toastOptions={{ classNames: { toast: 'font-sans' } }}
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
          '--success-bg': 'var(--popover)',
          '--success-text': 'var(--popover-foreground)',
          '--success-border': 'var(--success)',
          '--error-bg': 'var(--popover)',
          '--error-text': 'var(--popover-foreground)',
          '--error-border': 'var(--destructive)',
        } as React.CSSProperties
      }
    />
  )
}
