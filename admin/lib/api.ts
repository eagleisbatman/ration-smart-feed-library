import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
api.interceptors.request.use(
  (config) => {
    // Add API key if available
    const apiKey = localStorage.getItem('api_key');
    if (apiKey) {
      config.headers.Authorization = `Bearer ${apiKey}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized - redirect to login
      localStorage.removeItem('api_key');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const feedsApi = {
  getAll: (params?: any) => api.get('/feeds/', { params }),
  getById: (id: string) => api.get(`/feeds/${id}`),
  create: (data: any) => api.post('/admin/add-feed', data),
  update: (id: string, data: any) => api.put(`/admin/feeds/${id}`, data),
  delete: (id: string) => api.delete(`/admin/feeds/${id}`),
  bulkImport: (file: File, adminUserId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/admin/bulk-upload-feeds?admin_user_id=${adminUserId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export const countriesApi = {
  getAll: () => api.get('/auth/countries'),
  getById: (id: string) => api.get(`/countries/${id}`),
  create: (data: any) => api.post('/admin/countries', data),
  update: (id: string, data: any) => api.put(`/admin/countries/${id}`, data),
};

export const organizationsApi = {
  getAll: (adminUserId: string) => api.get(`/admin/organizations?admin_user_id=${adminUserId}`),
  getById: (id: string, adminUserId: string) =>
    api.get(`/admin/organizations/${id}?admin_user_id=${adminUserId}`),
  create: (data: any, adminUserId: string) =>
    api.post(`/admin/organizations?admin_user_id=${adminUserId}`, data),
  update: (id: string, data: any, adminUserId: string) =>
    api.put(`/admin/organizations/${id}?admin_user_id=${adminUserId}`, data),
};

export const apiKeysApi = {
  getAll: (orgId: string, adminUserId: string) =>
    api.get(`/admin/organizations/${orgId}/api-keys?admin_user_id=${adminUserId}`),
  create: (orgId: string, data: any, adminUserId: string) =>
    api.post(`/admin/organizations/${orgId}/api-keys?admin_user_id=${adminUserId}`, data),
  revoke: (keyId: string, adminUserId: string) =>
    api.delete(`/admin/api-keys/${keyId}?admin_user_id=${adminUserId}`),
};

export const authApi = {
  login: (email: string, pin: string) =>
    api.post('/auth/login', { email_id: email, pin }),
  logout: () => {
    localStorage.removeItem('api_key');
    localStorage.removeItem('user');
  },
};

