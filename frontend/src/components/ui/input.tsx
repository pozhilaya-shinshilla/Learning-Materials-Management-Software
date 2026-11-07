import * as React from 'react'
import { cn } from '@/lib/utils'

const field =
  'w-full rounded-md border border-input bg-card px-3 text-base text-foreground placeholder:text-muted-foreground transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:border-2'

export function Input({ className, type = 'text', ...props }: React.ComponentProps<'input'>) {
  return <input type={type} className={cn(field, 'h-11 min-w-0', className)} {...props} />
}

export function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return <textarea className={cn(field, 'min-h-28 py-2', className)} {...props} />
}
