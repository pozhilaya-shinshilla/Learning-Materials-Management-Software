import { zodResolver } from '@hookform/resolvers/zod'
import { Info } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { toApiError } from '@/api/errors'
import { useAuth } from '@/auth/AuthContext'
import { takeFlash } from '@/auth/storage'
import { AuthLayout } from '@/components/app/AuthLayout'
import { PasswordInput } from '@/components/app/PasswordInput'
import { FormError } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { usePageTitle } from '@/hooks/usePageTitle'
import { loginSchema } from '@/lib/validation'

export default function LoginPage() {
  usePageTitle('Вход')
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [flash] = useState(() => takeFlash())
  const [error, setError] = useState<string | null>(null)
  const form = useForm({ resolver: zodResolver(loginSchema), defaultValues: { login: '', password: '' } })

  if (user) return <Navigate to="/" replace />

  async function onSubmit(values: { login: string; password: string }) {
    setError(null)
    try {
      await login(values.login.trim(), values.password)
      navigate(from, { replace: true })
    } catch (e) {
      // 401 (неверные данные) и 403 (учётная запись заблокирована) показываем как есть.
      setError(toApiError(e).message)
    }
  }

  return (
    <AuthLayout title="Вход" description="Войдите под своим логином, чтобы работать с материалами.">
      {flash ? (
        <div role="status" className="flex gap-2 rounded-md border border-highlight p-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-highlight" aria-hidden="true" />
          <span>{flash}</span>
        </div>
      ) : null}
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <FormError message={error} />
          <FormField
            control={form.control}
            name="login"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Логин</FormLabel>
                <FormControl>
                  <Input autoComplete="username" autoCapitalize="none" spellCheck={false} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Пароль</FormLabel>
                <FormControl>
                  <PasswordInput autoComplete="current-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Входим…' : 'Войти'}
          </Button>
        </form>
      </Form>
      <p className="text-center text-sm">
        <Link to="/forgot-password" className="inline-flex min-h-11 items-center text-primary underline underline-offset-4 hover:no-underline">
          Забыли пароль?
        </Link>
      </p>
    </AuthLayout>
  )
}
