import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { authApi } from '@/api/endpoints'
import { AuthLayout } from '@/components/app/AuthLayout'
import { PasswordInput } from '@/components/app/PasswordInput'
import { FormError } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { usePageTitle } from '@/hooks/usePageTitle'
import { applyServerErrors } from '@/lib/errors-ui'
import { resetSchema } from '@/lib/validation'

export default function ResetPasswordPage() {
  usePageTitle('Новый пароль')
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const form = useForm({
    resolver: zodResolver(resetSchema),
    defaultValues: { token: params.get('token') ?? '', new_password: '', confirm: '' },
  })

  async function onSubmit(values: { token: string; new_password: string }) {
    setError(null)
    try {
      await authApi.reset(values.token.trim(), values.new_password)
      toast.success('Пароль изменён. Войдите с новым паролем.')
      navigate('/login', { replace: true })
    } catch (e) {
      // 401: код неверный или устарел. Это не «сессия закончилась», поэтому остаёмся на странице.
      const rest = applyServerErrors(form, e, ['token', 'new_password'])
      if (rest) setError(rest.message)
    }
  }

  return (
    <AuthLayout title="Новый пароль" description="Введите код из письма и придумайте новый пароль.">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <FormError message={error} />
          <FormField
            control={form.control}
            name="token"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Код из письма</FormLabel>
                <FormControl>
                  <Input autoComplete="one-time-code" autoCapitalize="none" spellCheck={false} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Новый пароль</FormLabel>
                <FormControl>
                  <PasswordInput autoComplete="new-password" {...field} />
                </FormControl>
                <FormDescription>Не короче 8 символов, с заглавной буквой, цифрой и специальным символом.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="confirm"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Повторите пароль</FormLabel>
                <FormControl>
                  <PasswordInput autoComplete="new-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Сохраняем…' : 'Сменить пароль'}
          </Button>
        </form>
      </Form>
      <p className="text-center text-sm">
        <Link to="/login" className="inline-flex min-h-11 items-center text-primary underline underline-offset-4 hover:no-underline">
          Вернуться ко входу
        </Link>
      </p>
    </AuthLayout>
  )
}
