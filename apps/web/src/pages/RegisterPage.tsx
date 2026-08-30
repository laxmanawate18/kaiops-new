import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, ArrowRight, Check, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Input'
import { useAuth } from '@/lib/auth/AuthProvider'
import { ApiError } from '@/lib/api/client'
import { cn } from '@/lib/utils'

/**
 * Validation mirrors the server's rules exactly (`app/auth/models.py`), so a
 * user never gets a surprise 422 for something we could have told them
 * inline. The old admin "create user" form validated nothing while the public
 * form validated everything — same endpoint, two standards.
 */
const schema = z
  .object({
    username: z
      .string()
      .min(3, 'At least 3 characters')
      .max(50, 'At most 50 characters')
      .regex(/^[A-Za-z0-9_-]+$/, 'Letters, numbers, underscore and hyphen only'),
    email: z.string().min(1, 'Enter an email').email('That does not look like an email'),
    full_name: z.string().max(100, 'At most 100 characters').optional().or(z.literal('')),
    password: z
      .string()
      .min(10, 'At least 10 characters')
        .regex(/[A-Z]/, 'Add an uppercase letter')
        .regex(/[0-9]/, 'Add a number')
      .max(128, 'At most 128 characters')
      .regex(/[A-Za-z]/, 'Must include a letter')
      .regex(/[0-9]/, 'Must include a digit'),
    confirm: z.string().min(1, 'Confirm your password'),
  })
  .refine((data) => data.password === data.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

type FormValues = z.infer<typeof schema>

const RULES = [
  { label: '10+ characters', test: (v: string) => v.length >= 10 },
  { label: 'Uppercase letter', test: (v: string) => /[A-Z]/.test(v) },
  { label: 'A letter', test: (v: string) => /[A-Za-z]/.test(v) },
  { label: 'A digit', test: (v: string) => /[0-9]/.test(v) },
]

export default function RegisterPage() {
  const { register: registerUser, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), mode: 'onBlur' })

  const password = watch('password') ?? ''

  if (isAuthenticated) return <Navigate to="/console" replace />

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await registerUser({
        username: values.username,
        email: values.email,
        password: values.password,
        full_name: values.full_name || values.username,
      })
      toast.success('Account created', { description: 'Sign in to get started.' })
      navigate('/login', { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          if (field in ({} as FormValues) || ['username', 'email', 'password', 'full_name'].includes(field)) {
            setError(field as keyof FormValues, { message })
          }
        }
        setFormError(error.message)
      } else {
        setFormError('Something went wrong creating your account.')
      }
    }
  })

  return (
    <AuthLayout
      title="Create your account"
      subtitle="New accounts start with engineer access. An administrator can grant more."
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <AnimatePresence mode="wait">
          {formError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              role="alert"
              className="overflow-hidden"
            >
              <div className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/10 px-3.5 py-3 text-sm text-danger">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                <span className="leading-relaxed">{formError}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <TextField
          label="Username"
          autoComplete="username"
          autoFocus
          placeholder="jane.doe"
          required
          error={errors.username?.message}
          {...register('username')}
        />

        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="jane@company.com"
          required
          error={errors.email?.message}
          {...register('email')}
        />

        <TextField
          label="Full name"
          autoComplete="name"
          placeholder="Jane Doe"
          hint="Optional — shown to teammates in the review queue."
          error={errors.full_name?.message}
          {...register('full_name')}
        />

        <div className="space-y-2.5">
          <TextField
            label="Password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            placeholder="••••••••••••"
            required
            error={errors.password?.message}
            trailingSlot={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="rounded p-1.5 text-content-subtle transition-colors hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
            {...register('password')}
          />

          {/* Live requirement checklist beats a red error after submit. */}
          <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Password requirements">
            {RULES.map((rule) => {
              const met = rule.test(password)
              return (
                <li
                  key={rule.label}
                  className={cn(
                    'flex items-center gap-1.5 text-2xs transition-colors',
                    met ? 'text-ok' : 'text-content-subtle',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-3 w-3 items-center justify-center rounded-full border transition-colors',
                      met ? 'border-ok bg-ok/20' : 'border-line-strong',
                    )}
                    aria-hidden
                  >
                    {met && <Check className="h-2 w-2" strokeWidth={3.5} />}
                  </span>
                  {rule.label}
                  <span className="sr-only">{met ? '— met' : '— not met'}</span>
                </li>
              )
            })}
          </ul>
        </div>

        <TextField
          label="Confirm password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder="••••••••••••"
          required
          error={errors.confirm?.message}
          {...register('confirm')}
        />

        <Button type="submit" variant="primary" size="lg" loading={isSubmitting} className="w-full">
          {isSubmitting ? 'Creating account' : 'Create account'}
          {!isSubmitting && <ArrowRight className="h-4 w-4" aria-hidden />}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-content-subtle">
        Already have an account?{' '}
        <Link
          to="/login"
          className="font-medium text-brand-300 transition-colors hover:text-brand-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
        >
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
