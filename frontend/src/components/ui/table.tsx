import { cn } from '@/lib/utils'

export function Table({ className, ...props }: React.ComponentProps<'table'>) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border border-border bg-card">
      <table className={cn('w-full caption-bottom border-collapse text-sm', className)} {...props} />
    </div>
  )
}
export function TableHeader({ className, ...props }: React.ComponentProps<'thead'>) {
  return <thead className={cn('bg-muted text-left', className)} {...props} />
}
export function TableBody({ className, ...props }: React.ComponentProps<'tbody'>) {
  return <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />
}
export function TableRow({ className, ...props }: React.ComponentProps<'tr'>) {
  return <tr className={cn('border-b border-border transition-colors hover:bg-accent', className)} {...props} />
}
export function TableHead({ className, ...props }: React.ComponentProps<'th'>) {
  return <th scope="col" className={cn('px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground', className)} {...props} />
}
export function TableCell({ className, ...props }: React.ComponentProps<'td'>) {
  return <td className={cn('px-3 py-2 align-middle', className)} {...props} />
}
