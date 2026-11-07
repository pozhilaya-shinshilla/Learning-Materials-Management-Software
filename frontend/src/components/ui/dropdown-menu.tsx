import { Check } from 'lucide-react'
import { DropdownMenu as DropdownPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

export const DropdownMenu = DropdownPrimitive.Root
export const DropdownMenuTrigger = DropdownPrimitive.Trigger
export const DropdownMenuRadioGroup = DropdownPrimitive.RadioGroup

export function DropdownMenuContent({ className, sideOffset = 6, align = 'end', ...props }: React.ComponentProps<typeof DropdownPrimitive.Content>) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        sideOffset={sideOffset}
        align={align}
        className={cn('z-50 min-w-48 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-md', className)}
        {...props}
      />
    </DropdownPrimitive.Portal>
  )
}
const item = 'relative flex min-h-11 cursor-pointer select-none items-center gap-2 rounded-md px-3 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground [&_svg]:size-4 [&_svg]:shrink-0'
export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof DropdownPrimitive.Item>) {
  return <DropdownPrimitive.Item className={cn(item, className)} {...props} />
}
export function DropdownMenuRadioItem({ className, children, ...props }: React.ComponentProps<typeof DropdownPrimitive.RadioItem>) {
  return (
    <DropdownPrimitive.RadioItem className={cn(item, 'pr-9', className)} {...props}>
      {children}
      <DropdownPrimitive.ItemIndicator className="absolute right-3">
        <Check aria-hidden="true" />
      </DropdownPrimitive.ItemIndicator>
    </DropdownPrimitive.RadioItem>
  )
}
export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof DropdownPrimitive.Label>) {
  return <DropdownPrimitive.Label className={cn('px-3 py-2 text-xs font-semibold text-muted-foreground', className)} {...props} />
}
export function DropdownMenuSeparator({ className, ...props }: React.ComponentProps<typeof DropdownPrimitive.Separator>) {
  return <DropdownPrimitive.Separator className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
}
