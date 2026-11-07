import { Label as LabelPrimitive } from 'radix-ui'
import * as React from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn('text-sm font-semibold leading-snug text-foreground peer-disabled:opacity-50', className)}
      {...props}
    />
  )
}
