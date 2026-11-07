import { Tabs as TabsPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

export const Tabs = TabsPrimitive.Root

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('flex w-full gap-1 overflow-x-auto border-b border-border', className)}
      {...props}
    />
  )
}
export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        '-mb-px inline-flex h-11 shrink-0 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-4 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground data-[state=active]:border-highlight data-[state=active]:text-foreground',
        className,
      )}
      {...props}
    />
  )
}
export function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content className={cn('pt-4', className)} {...props} />
}
