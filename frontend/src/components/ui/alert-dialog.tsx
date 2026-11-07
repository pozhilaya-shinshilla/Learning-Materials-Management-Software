import { AlertDialog as AlertPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'
import { buttonVariants } from './button'

export const AlertDialog = AlertPrimitive.Root
export const AlertDialogTrigger = AlertPrimitive.Trigger

export function AlertDialogContent({ className, ...props }: React.ComponentProps<typeof AlertPrimitive.Content>) {
  return (
    <AlertPrimitive.Portal>
      <AlertPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 [animation:lms-fade-in_180ms_ease-out]" />
      <AlertPrimitive.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex w-[calc(100vw-1.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-lg border border-border bg-popover p-5 text-popover-foreground shadow-md [animation:lms-fade-in_180ms_ease-out]',
          className,
        )}
        {...props}
      />
    </AlertPrimitive.Portal>
  )
}
export function AlertDialogHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('flex flex-col gap-1.5', className)} {...props} />
}
export function AlertDialogFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)} {...props} />
}
export function AlertDialogTitle({ className, ...props }: React.ComponentProps<typeof AlertPrimitive.Title>) {
  return <AlertPrimitive.Title className={cn('font-serif text-xl font-semibold', className)} {...props} />
}
export function AlertDialogDescription({ className, ...props }: React.ComponentProps<typeof AlertPrimitive.Description>) {
  return <AlertPrimitive.Description className={cn('text-sm text-muted-foreground', className)} {...props} />
}
export function AlertDialogAction({ className, ...props }: React.ComponentProps<typeof AlertPrimitive.Action>) {
  return <AlertPrimitive.Action className={cn(buttonVariants({ variant: 'destructive' }), className)} {...props} />
}
export function AlertDialogCancel({ className, ...props }: React.ComponentProps<typeof AlertPrimitive.Cancel>) {
  return <AlertPrimitive.Cancel className={cn(buttonVariants({ variant: 'outline' }), className)} {...props} />
}
