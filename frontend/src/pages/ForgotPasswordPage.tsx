import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { authApi } from '@/api/endpoints'
import { toApiError } from '@/api/errors'
import { AuthLayout } from '@/components/app/AuthLayout'
import { FormError } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { usePageTitle } from '@/hooks/usePageTitle'
import { recoverySchema } from '@/lib/validation'

export default function ForgotPasswordPage() {
  usePageTitle('Восстановление пароля')
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const form = useForm({ resolver: zodResolver(recoverySchema), defaultValues: { email: '' } })

  async function onSubmit({ email }: { email: string }) {
    setError(null)
    try {
      // Сервер всегда отвечает 202 и одним текстом: по ответу нельзя узнать, есть ли такой адрес.
      const response = await authApi.recovery(email.trim())
      setDone(response.detail)
    } catch (e) {
      const err = toApiError(e)
      if (err.fields.email) form.setError('email', { message: err.fields.email })
      else setError(err.message)
    }
  }

  return (
    <AuthLayout title="Восстановление пароля" description="Укажите e-mail учётной записи: мы отправим код для смены пароля.">
      {done ? (
        <div className="flex flex-col gap-4">
          <div role="status" className="flex gap-3 rounded-md border border-success p-3 text-sm">
            <MailCheck className="mt-0.5 size-5 shrink-0 text-success" aria-hidden="true" />
            <span>{done}</span>
          </div>
          <Button asChild>
            <Link to="/reset-password">У меня есть код</Link>
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
            <FormError message={error} />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>E-mail</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" inputMode="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? 'Отправляем…' : 'Получить код'}
            </Button>
          </form>
        </Form>
      )}
      <p className="text-center text-sm">
        <Link to="/login" className="inline-flex min-h-11 items-center text-primary underline underline-offset-4 hover:no-underline">
          Вернуться ко входу
        </Link>
      </p>
    </AuthLayout>
  )
}
