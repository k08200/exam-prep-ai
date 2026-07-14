import axios from 'axios';
import Cookies from 'js-cookie';
import type { RuntimeHealth } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

export const metaApi = {
  health: () => api.get<RuntimeHealth>('/health'),
};

export function extractErrorMessage(
  error: unknown,
  fallback = 'Something went wrong. Please try again.'
): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first?.msg === 'string') return first.msg;
    }
    if (error.response?.status) {
      return `Request failed with status ${error.response.status}.`;
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

// Request interceptor: attach JWT token
api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url || '';
      const shouldHandleLocally =
        requestUrl.includes('/auth/login') ||
        requestUrl.includes('/auth/me/password');

      if (!shouldHandleLocally && typeof window !== 'undefined') {
        Cookies.remove('access_token');
        window.location.href = '/auth/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    api.post('/auth/register', data),
  login: (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  me: () => api.get('/auth/me'),
  updateMe: (data: { full_name?: string }) => api.patch('/auth/me', data),
  changePassword: (current_password: string, new_password: string) =>
    api.patch('/auth/me/password', { current_password, new_password }),
  exportData: () => api.get('/auth/me/export', { responseType: 'blob' }),
  deleteMe: () => api.delete('/auth/me'),
};

// Courses
export const coursesApi = {
  list: () => api.get('/courses'),
  create: (data: {
    name: string;
    description?: string;
    professor_name?: string;
    subject?: string;
  }) => api.post('/courses', data),
  get: (id: string) => api.get(`/courses/${id}`),
  update: (
    id: string,
    data: Partial<{
      name: string;
      description: string;
      professor_name: string;
      subject: string;
    }>
  ) => api.put(`/courses/${id}`, data),
  delete: (id: string) => api.delete(`/courses/${id}`),
};

// Materials
export const materialsApi = {
  upload: (courseId: string, files: File[]) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    return api.post(`/courses/${courseId}/materials`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: (courseId: string) => api.get(`/courses/${courseId}/materials`),
  delete: (courseId: string, materialId: string) =>
    api.delete(`/courses/${courseId}/materials/${materialId}`),
  retry: (courseId: string, materialId: string) =>
    api.post(`/courses/${courseId}/materials/${materialId}/retry`),
};

// Analysis - returns SSE stream URL
export const analysisApi = {
  getStreamUrl: (courseId: string) =>
    `${API_URL}/courses/${courseId}/analysis`,
  get: (courseId: string) => api.get(`/courses/${courseId}/analysis`),
};

// Exams
export const examsApi = {
  getStreamUrl: (courseId: string) =>
    `${API_URL}/courses/${courseId}/exams`,
  listAll: (limit = 20) => api.get(`/exams?limit=${limit}`),
  list: (courseId: string) => api.get(`/courses/${courseId}/exams`),
  get: (examId: string) => api.get(`/exams/${examId}`),
  result: (examId: string) => api.get(`/exams/${examId}/result`),
  delete: (examId: string) => api.delete(`/exams/${examId}`),
  submit: (
    examId: string,
    answers: Array<{ question_id: string; student_answer: string }>
  ) => api.post(`/exams/${examId}/submit`, { answers }),
  heatmap: (courseId: string) => api.get(`/courses/${courseId}/heatmap`),
};
