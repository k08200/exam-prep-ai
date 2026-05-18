'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Brain, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { authApi, extractErrorMessage } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

const registerSchema = z
  .object({
    full_name: z.string().optional(),
    email: z.string().email('Please enter a valid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Za-z]/, 'Password must contain at least one letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'Contains a letter', test: (p: string) => /[A-Za-z]/.test(p) },
  { label: 'Contains a number', test: (p: string) => /[0-9]/.test(p) },
];

export default function RegisterPage() {
  const [serverError, setServerError] = useState<string | null>(null);
  const router = useRouter();
  const { login, user, loading } = useAuth();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: 'onChange',
  });

  const passwordValue = watch('password', '');

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null);
    try {
      await authApi.register({
        email: data.email,
        password: data.password,
        full_name: data.full_name || undefined,
      });
      // Auto-login after registration
      await login(data.email, data.password);
    } catch (err: unknown) {
      setServerError(extractErrorMessage(err, 'Registration failed. Please try again.'));
    }
  };

  useEffect(() => {
    if (!loading && user) {
      router.push('/dashboard');
    }
  }, [loading, router, user]);

  if (loading || user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="h-10 w-10 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="w-10 h-10 gradient-hero rounded-xl flex items-center justify-center">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Exam Prep AI</span>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Free forever. No credit card required.
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          {/* Server error */}
          {serverError && (
            <div className="flex items-start gap-2.5 p-3.5 bg-red-50 border border-red-200 rounded-lg mb-5 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{serverError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {/* Full Name */}
            <div>
              <label htmlFor="full_name" className="label-base">
                Full Name{' '}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                id="full_name"
                type="text"
                autoComplete="name"
                className="input-base"
                placeholder="Alex Johnson"
                {...register('full_name')}
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="label-base">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className={`input-base ${
                  errors.email ? 'border-red-400 focus:ring-red-500' : ''
                }`}
                placeholder="you@university.edu"
                {...register('email')}
              />
              {errors.email && (
                <p className="error-message">
                  <AlertCircle className="h-3 w-3" />
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="label-base">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                className={`input-base ${
                  errors.password ? 'border-red-400 focus:ring-red-500' : ''
                }`}
                placeholder="Create a strong password"
                {...register('password')}
              />
              {/* Password rules */}
              {passwordValue && (
                <div className="mt-2 space-y-1">
                  {PASSWORD_RULES.map((rule) => {
                    const passed = rule.test(passwordValue);
                    return (
                      <div
                        key={rule.label}
                        className={`flex items-center gap-1.5 text-xs ${
                          passed ? 'text-green-600' : 'text-gray-400'
                        }`}
                      >
                        <CheckCircle
                          className={`h-3 w-3 ${
                            passed ? 'text-green-500' : 'text-gray-300'
                          }`}
                        />
                        {rule.label}
                      </div>
                    );
                  })}
                </div>
              )}
              {errors.password && !passwordValue && (
                <p className="error-message">
                  <AlertCircle className="h-3 w-3" />
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirm_password" className="label-base">
                Confirm Password
              </label>
              <input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                className={`input-base ${
                  errors.confirm_password ? 'border-red-400 focus:ring-red-500' : ''
                }`}
                placeholder="Repeat your password"
                {...register('confirm_password')}
              />
              {errors.confirm_password && (
                <p className="error-message">
                  <AlertCircle className="h-3 w-3" />
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={isSubmitting}
            >
              {isSubmitting ? 'Creating account…' : 'Create Account'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link
              href="/auth/login"
              className="font-medium text-blue-600 hover:text-blue-700 transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          By creating an account, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}
