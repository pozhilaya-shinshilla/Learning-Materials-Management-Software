import { Slot } from 'radix-ui'
import * as React from 'react'
import {
  Controller,
  FormProvider,
  useFormContext,
  useFormState,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
} from 'react-hook-form'
import { cn } from '@/lib/utils'
import { Label } from './label'

export const Form = FormProvider

interface FieldContextValue {
  name: string
}
const FormFieldContext = React.createContext<FieldContextValue | null>(null)
interface ItemContextValue {
  id: string
}
const FormItemContext = React.createContext<ItemContextValue | null>(null)

export function FormField<TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>(
  props: ControllerProps<TFieldValues, TName>,
) {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )
}

function useFormField() {
  const field = React.useContext(FormFieldContext)
  const item = React.useContext(FormItemContext)
  const { getFieldState, control } = useFormContext()
  const formState = useFormState({ control, name: field?.name })
  if (!field || !item) throw new Error('Поле формы вне FormField/FormItem')
  const state = getFieldState(field.name, formState)
  return {
    name: field.name,
    id: item.id,
    descriptionId: `${item.id}-description`,
    messageId: `${item.id}-message`,
    error: state.error,
  }
}

export function FormItem({ className, ...props }: React.ComponentProps<'div'>) {
  const id = React.useId()
  return (
    <FormItemContext.Provider value={{ id }}>
      <div className={cn('flex flex-col gap-1.5', className)} {...props} />
    </FormItemContext.Provider>
  )
}

export function FormLabel({ className, children, required, ...props }: React.ComponentProps<typeof Label> & { required?: boolean }) {
  const { id } = useFormField()
  return (
    <Label htmlFor={id} className={className} {...props}>
      {children}
      {required ? <span aria-hidden="true" className="ml-0.5 text-destructive">*</span> : null}
    </Label>
  )
}

export function FormControl(props: React.ComponentProps<typeof Slot.Root>) {
  const { id, descriptionId, messageId, error } = useFormField()
  return (
    <Slot.Root
      id={id}
      aria-describedby={error ? `${descriptionId} ${messageId}` : descriptionId}
      aria-invalid={!!error}
      {...props}
    />
  )
}

export function FormDescription({ className, ...props }: React.ComponentProps<'p'>) {
  const { descriptionId } = useFormField()
  return <p id={descriptionId} className={cn('text-sm text-muted-foreground', className)} {...props} />
}

export function FormMessage({ className, children, ...props }: React.ComponentProps<'p'>) {
  const { error, messageId } = useFormField()
  const body = error ? String(error.message ?? '') : children
  if (!body) return null
  return (
    <p id={messageId} role="alert" className={cn('text-sm font-medium text-destructive', className)} {...props}>
      {body}
    </p>
  )
}
