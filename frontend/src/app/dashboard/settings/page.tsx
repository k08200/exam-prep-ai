'use client';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AlertCircle, CheckCircle, Download, Lock, User } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/hooks/useAuth';
import { authApi, extractErrorMessage } from '@/lib/api';

const profileSchema = z.object({
  full_name: z.string().max(255).optional(),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    new_password: z.string().min(8, 'At least 8 characters'),
    confirm_password: z.string().min(1, 'Required'),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type ProfileFormData = z.infer<typeof profileSchema>;
type PasswordFormData = z.infer<typeof passwordSchema>;

export default function SettingsPage() {
  const { user, logout, refreshUser } = useAuth();
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset: resetProfile,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name || '',
    },
  });

  const {
    register: registerPw,
    handleSubmit: handleSubmitPw,
    reset: resetPw,
    formState: { errors: pwErrors, isSubmitting: isPwSubmitting },
  } = useForm<PasswordFormData>({ resolver: zodResolver(passwordSchema) });

  useEffect(() => {
    resetProfile({ full_name: user?.full_name || '' });
  }, [resetProfile, user?.full_name]);

  const onProfileSubmit = async (data: ProfileFormData) => {
    try {
      setProfileError(null);
      await authApi.updateMe({ full_name: data.full_name ?? '' });
      await refreshUser();
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: unknown) {
      setProfileError(extractErrorMessage(err, 'Failed to update profile. Please try again.'));
    }
  };

  const onPasswordSubmit = async (data: PasswordFormData) => {
    try {
      setPasswordError(null);
      await authApi.changePassword(data.current_password, data.new_password);
      resetPw();
      setPasswordSuccess(true);
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (err: unknown) {
      setPasswordError(extractErrorMessage(err, 'Failed to change password.'));
    }
  };

  const handleDeleteAccount = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await authApi.deleteMe();
      logout();
    } catch (err: unknown) {
      setDeleteError(extractErrorMessage(err, 'Failed to delete account. Please try again.'));
      setIsDeleting(false);
    }
  };

  const handleExportData = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const response = await authApi.exportData();
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `exam-prep-ai-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setExportError(extractErrorMessage(err, 'Failed to export your data. Please try again.'));
    } finally {
      setIsExporting(false);
    }
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
              <label htmlFor="full_name" className="label-base">Full Name</label>
              <input
                id="full_name"
                type="text"
                className={`input-base ${errors.full_name ? 'border-red-400' : ''}`}
                placeholder="Your full name"
                {...register('full_name')}
              />
              {errors.full_name && (
                <p className="error-message">
                  <AlertCircle className="h-3 w-3" />
                  {errors.full_name.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="email" className="label-base">Email Address</label>
              <input
                id="email"
                type="email"
                className="input-base bg-gray-50 text-gray-500 cursor-not-allowed"
                value={user?.email || ''}
                disabled
              />
              <p className="text-xs text-gray-400 mt-1">Email cannot be changed.</p>
            </div>
            <div className="flex justify-end">
              <Button type="submit" size="sm" loading={isSubmitting}>
                Save Changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Password Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">Change Password</h2>
          </div>
        </CardHeader>
        <CardContent>
          {passwordSuccess && (
            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg mb-4 text-sm text-green-700">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              Password changed successfully!
            </div>
          )}
          {passwordError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mb-4 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {passwordError}
            </div>
          )}
          <form onSubmit={handleSubmitPw(onPasswordSubmit)} className="space-y-4">
            <div>
              <label htmlFor="current_password" className="label-base">Current Password</label>
              <input
                id="current_password"
                type="password"
                className={`input-base ${pwErrors.current_password ? 'border-red-400' : ''}`}
                placeholder="••••••••"
                {...registerPw('current_password')}
              />
              {pwErrors.current_password && (
                <p className="error-message"><AlertCircle className="h-3 w-3" />{pwErrors.current_password.message}</p>
              )}
            </div>
            <div>
              <label htmlFor="new_password" className="label-base">New Password</label>
              <input
                id="new_password"
                type="password"
                className={`input-base ${pwErrors.new_password ? 'border-red-400' : ''}`}
                placeholder="••••••••"
                {...registerPw('new_password')}
              />
              {pwErrors.new_password && (
                <p className="error-message"><AlertCircle className="h-3 w-3" />{pwErrors.new_password.message}</p>
              )}
            </div>
            <div>
              <label htmlFor="confirm_password" className="label-base">Confirm New Password</label>
              <input
                id="confirm_password"
                type="password"
                className={`input-base ${pwErrors.confirm_password ? 'border-red-400' : ''}`}
                placeholder="••••••••"
                {...registerPw('confirm_password')}
              />
              {pwErrors.confirm_password && (
                <p className="error-message"><AlertCircle className="h-3 w-3" />{pwErrors.confirm_password.message}</p>
              )}
            </div>
            <div className="flex justify-end">
              <Button type="submit" size="sm" loading={isPwSubmitting}>
                Change Password
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Download className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">Your Data</h2>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-gray-800">Download your study archive</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Includes courses, extracted material text, analyses, exams, answers, and progress.
              </p>
            </div>
            <Button variant="outline" size="sm" loading={isExporting} onClick={handleExportData}>
              <Download className="h-4 w-4" />
              Export Data
            </Button>
          </div>
          {exportError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mt-4 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {exportError}
            </div>
          )}
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
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete Account
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteConfirm}
        onClose={() => {
          if (!isDeleting) {
            setShowDeleteConfirm(false);
            setDeleteError(null);
          }
        }}
        title="Delete Account"
        description="This action is permanent and cannot be undone."
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            All your courses, materials, exams, and analytics data will be permanently deleted.
          </p>
          {deleteError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {deleteError}
            </div>
          )}
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setShowDeleteConfirm(false);
                setDeleteError(null);
              }}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={isDeleting}
              onClick={handleDeleteAccount}
            >
              Yes, Delete My Account
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
