import { Popover as PopoverPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger

export function PopoverContent({ className, align = 'end', sideOffset = 6, ...props }: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn('z-50 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-md', className)}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}
