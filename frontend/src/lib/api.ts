import axios from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

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
      Cookies.remove('access_token');
      window.location.href = '/auth/login';
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
};

// Analysis - returns SSE stream URL
export const analysisApi = {
  getStreamUrl: (courseId: string) =>
    `${API_URL}/courses/${courseId}/analysis/stream`,
  get: (courseId: string) => api.get(`/courses/${courseId}/analysis`),
};

// Exams
export const examsApi = {
  getStreamUrl: (courseId: string) =>
    `${API_URL}/courses/${courseId}/exams/stream`,
  list: (courseId: string) => api.get(`/courses/${courseId}/exams`),
  get: (examId: string) => api.get(`/exams/${examId}`),
  submit: (
    examId: string,
    answers: Array<{ question_id: string; student_answer: string }>
  ) => api.post(`/exams/${examId}/submit`, { answers }),
  heatmap: (courseId: string) => api.get(`/courses/${courseId}/heatmap`),
};
