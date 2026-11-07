import { X } from 'lucide-react'
import { Dialog as SheetPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

export const Sheet = SheetPrimitive.Root
export const SheetTrigger = SheetPrimitive.Trigger
export const SheetClose = SheetPrimitive.Close
export const SheetTitle = SheetPrimitive.Title
export const SheetDescription = SheetPrimitive.Description

export function SheetContent({
  className,
  children,
  side = 'left',
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & { side?: 'left' | 'right' }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 [animation:lms-fade-in_180ms_ease-out]" />
      <SheetPrimitive.Content
        className={cn(
          'fixed inset-y-0 z-50 flex w-[85vw] max-w-sm flex-col gap-4 overflow-y-auto border-border bg-popover p-5 text-popover-foreground shadow-md',
          side === 'left' ? 'left-0 border-r [animation:lms-slide-in-left_220ms_ease-out]' : 'right-0 border-l [animation:lms-slide-in-right_220ms_ease-out]',
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close
          aria-label="Закрыть"
          className="absolute right-2 top-2 flex size-11 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <X className="size-4" aria-hidden="true" />
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}
