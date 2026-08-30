import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { Check, KeyRound, Mail, Shield, Users2 } from 'lucide-react'
import { toast } from 'sonner'
import { authApi, feedbackApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { useAuth } from '@/lib/auth/AuthProvider'
import { ApiError } from '@/lib/api/client'
import { Card, CardBody, CardHeader, CardTitle, Avatar, SectionLabel } from '@/components/ui/primitives'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { formatDateTime } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z
      .string()
      .min(10, 'At least 10 characters')
        .regex(/[A-Z]/, 'Add an uppercase letter')
        .regex(/[0-9]/, 'Add a number')
      .max(128, 'At most 128 characters')
      .regex(/[A-Za-z]/, 'Must include a letter')
      .regex(/[0-9]/, 'Must include a digit'),
    confirm: z.string().min(1, 'Confirm the new password'),
  })
  .refine((d) => d.new_password === d.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

type PasswordValues = z.infer<typeof passwordSchema>

const ROLE_META: Record<string, { label: string; tone: 'accent' | 'brand' | 'neutral'; blurb: string }> = {
  admin: {
    label: 'Administrator',
    tone: 'accent',
    blurb: 'Full access: users, teams, the registry and the review queue.',
  },
  team_lead: {
    label: 'Team lead',
    tone: 'brand',
    blurb: 'Can manage services and triage the agent feedback queue.',
  },
  user: {
    label: 'Engineer',
    tone: 'neutral',
    blurb: 'Can run investigations and rate the agent’s answers.',
  },
}

export default function ProfilePage() {
  const { user, refresh } = useAuth()
  const [changed, setChanged] = useState(false)

  const statsQuery = useQuery({
    queryKey: qk.feedbackMyStats,
    queryFn: feedbackApi.myStats,
    retry: false,
  })

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) })

  const changePassword = useMutation({
    mutationFn: (values: PasswordValues) =>
      authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    onSuccess: () => {
      toast.success('Password updated', { description: 'Use it the next time you sign in.' })
      reset()
      setChanged(true)
      setTimeout(() => setChanged(false), 4000)
    },
    onError: (error: ApiError) => {
      if (error.status === 400) {
        setError('current_password', { message: 'That password is not correct' })
      }
      toast.error('Could not change password', { description: error.message })
    },
  })

  const roleMeta = ROLE_META[user?.role ?? 'user'] ?? ROLE_META.user

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <motion.div
        variants={staggerContainer(0.05)}
        initial="initial"
        animate="animate"
        className="mx-auto max-w-3xl space-y-6 p-6"
      >
        {/* Identity */}
        <motion.div variants={staggerItem}>
          <Card className="p-6">
            <div className="flex flex-wrap items-center gap-5">
              <Avatar name={user?.full_name || user?.username} size="lg" />
              <div className="min-w-0 flex-1 space-y-1">
                <h1 className="truncate text-lg font-semibold tracking-tight text-content">
                  {user?.full_name || user?.username}
                </h1>
                <p className="flex items-center gap-1.5 truncate text-xs text-content-muted">
                  <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {user?.email}
                </p>
              </div>
              <Badge tone={roleMeta.tone} size="md">
                <Shield className="h-3 w-3" aria-hidden />
                {roleMeta.label}
              </Badge>
            </div>

            <div className="mt-5 grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
              <div className="space-y-1">
                <SectionLabel>Username</SectionLabel>
                <p className="font-mono text-xs text-content-muted">{user?.username}</p>
              </div>
              <div className="space-y-1">
                <SectionLabel>Member since</SectionLabel>
                <p className="text-xs text-content-muted">{formatDateTime(user?.created_at)}</p>
              </div>
              <div className="space-y-1">
                <SectionLabel>Status</SectionLabel>
                <p className="text-xs text-content-muted">
                  {user?.is_active ? 'Active' : 'Deactivated'}
                </p>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Access — describes what the role actually grants, not a fake toggle list */}
        <motion.div variants={staggerItem}>
          <Card>
            <CardHeader>
              <div className="space-y-0.5">
                <CardTitle>Your access</CardTitle>
                <p className="text-2xs text-content-subtle">{roleMeta.blurb}</p>
              </div>
            </CardHeader>
            <CardBody className="space-y-4">
              <div className="space-y-2">
                <SectionLabel>Teams</SectionLabel>
                {user?.teams && user.teams.length > 0 ? (
                  <ul className="flex flex-wrap gap-2">
                    {user.teams.map((team) => (
                      <li key={team}>
                        <Badge tone="brand">
                          <Users2 className="h-3 w-3" aria-hidden />
                          {team}
                          {user.team_lead_of?.includes(team) && (
                            <span className="ml-0.5 text-[9px] uppercase tracking-wider opacity-80">
                              lead
                            </span>
                          )}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-content-subtle">
                    You are not a member of any team yet. An administrator can add you.
                  </p>
                )}
              </div>

              {statsQuery.data && (
                <div className="grid grid-cols-3 gap-3 border-t border-line pt-4">
                  {[
                    { label: 'Feedback given', value: statsQuery.data.total_feedback },
                    { label: 'Approved', value: statsQuery.data.approved },
                    { label: 'Pending review', value: statsQuery.data.pending },
                  ].map((stat) => (
                    <div key={stat.label} className="space-y-1">
                      <p className="text-xl font-semibold tabular-nums text-content">{stat.value}</p>
                      <p className="text-2xs text-content-subtle">{stat.label}</p>
                    </div>
                  ))}
                </div>
              )}

              <Button variant="ghost" size="xs" onClick={() => void refresh()}>
                Refresh from server
              </Button>
            </CardBody>
          </Card>
        </motion.div>

        {/* Password */}
        <motion.div variants={staggerItem}>
          <Card>
            <CardHeader>
              <div className="space-y-0.5">
                <CardTitle>Change password</CardTitle>
                <p className="text-2xs text-content-subtle">
                  Must be at least 6 characters and include a letter and a digit.
                </p>
              </div>
              <KeyRound className="h-4 w-4 shrink-0 text-content-subtle" aria-hidden />
            </CardHeader>
            <CardBody>
              <form
                onSubmit={handleSubmit((values) => changePassword.mutate(values))}
                className="max-w-sm space-y-4"
                noValidate
              >
                <TextField
                  label="Current password"
                  type="password"
                  autoComplete="current-password"
                  required
                  error={errors.current_password?.message}
                  {...register('current_password')}
                />
                <TextField
                  label="New password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={errors.new_password?.message}
                  {...register('new_password')}
                />
                <TextField
                  label="Confirm new password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={errors.confirm?.message}
                  {...register('confirm')}
                />

                <div className="flex items-center gap-3">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    loading={isSubmitting || changePassword.isPending}
                  >
                    Update password
                  </Button>
                  {changed && (
                    <motion.span
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-1.5 text-xs text-ok"
                    >
                      <Check className="h-3.5 w-3.5" aria-hidden />
                      Saved
                    </motion.span>
                  )}
                </div>
              </form>
            </CardBody>
          </Card>
        </motion.div>
      </motion.div>
    </div>
  )
}
