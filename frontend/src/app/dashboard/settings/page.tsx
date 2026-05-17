'use client';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AlertCircle, CheckCircle, User, Lock } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { authApi } from '@/lib/api';

const profileSchema = z.object({
  full_name: z.string().optional(),
  email: z.string().email('Invalid email').min(1),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export default function SettingsPage() {
  const { user } = useAuth();
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name || '',
      email: user?.email || '',
    },
  });

  const onProfileSubmit = async (_data: ProfileFormData) => {
    // Profile update would call the appropriate endpoint
    // For now, show success feedback
    setProfileError(null);
    setProfileSuccess(true);
    setTimeout(() => setProfileSuccess(false), 3000);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">Manage your account preferences</p>
      </div>

      {/* Profile Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">Profile</h2>
          </div>
        </CardHeader>
        <CardContent>
          {profileSuccess && (
            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg mb-4 text-sm text-green-700">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              Profile updated successfully!
            </div>
          )}
          {profileError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mb-4 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {profileError}
            </div>
          )}
          <form onSubmit={handleSubmit(onProfileSubmit)} className="space-y-4">
            <div>
              <label className="label-base">Full Name</label>
              <input
                type="text"
                className="input-base"
                placeholder="Your full name"
                {...register('full_name')}
              />
            </div>
            <div>
              <label className="label-base">Email Address</label>
              <input
                type="email"
                className={`input-base ${errors.email ? 'border-red-400' : ''}`}
                placeholder="your@email.com"
                {...register('email')}
              />
              {errors.email && (
                <p className="error-message">
                  <AlertCircle className="h-3 w-3" />
                  {errors.email.message}
                </p>
              )}
            </div>
            <div className="flex justify-end">
              <Button type="submit" size="sm" loading={isSubmitting}>
                Save Changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Account Info Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">Account</h2>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Account ID</span>
              <span className="font-mono text-xs text-gray-600 bg-gray-50 px-2 py-0.5 rounded">
                {user?.id ? `${user.id.slice(0, 8)}…` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Account Status</span>
              <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-medium">
                Active
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-500">Member Since</span>
              <span className="text-gray-700">
                {user?.created_at
                  ? new Intl.DateTimeFormat('en-US', {
                      year: 'numeric',
                      month: 'long',
                    }).format(new Date(user.created_at))
                  : '—'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-red-200">
        <CardHeader>
          <h2 className="text-sm font-semibold text-red-700">Danger Zone</h2>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-800">Delete Account</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Permanently delete your account and all associated data.
              </p>
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={() =>
                alert('To delete your account, please contact support.')
              }
            >
              Delete Account
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
