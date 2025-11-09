import axios from 'axios';
import { secureStorage } from './secure-storage';

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
    // Add API key if available (from secure storage)
    const apiKey = secureStorage.getApiKey();
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
  (response) => {
    // Refresh session on successful requests
    secureStorage.refreshSession();
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized - clear session and redirect to login
      secureStorage.clearAll();
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ==================== AUTHENTICATION ====================
export const authApi = {
  requestOtp: (email: string, purpose: 'login' | 'registration' | 'password_reset') =>
    api.post('/auth/otp/request', { email_id: email, purpose }),
  loginWithOtp: (email: string, otpCode: string) =>
    api.post('/auth/otp/login', { email_id: email, otp_code: otpCode }),
  registerWithOtp: (data: { name: string; email_id: string; country_id: string; otp_code: string }) =>
    api.post('/auth/otp/register', data),
  logout: () => {
    secureStorage.clearAll();
  },
  checkSuperadmin: (email: string) =>
    api.get('/admin/superadmin/check', { params: { email_id: email } }),
};

// ==================== FEEDS ====================
export const feedsApi = {
  getAll: (params?: {
    country_id?: string;
    feed_type?: string;
    feed_category?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/feeds/', { params }),
  getById: (id: string) => api.get(`/feeds/${id}`),
  create: (data: any, adminUserId: string) =>
    api.post('/admin/add-feed', data, { params: { admin_user_id: adminUserId } }),
  update: (id: string, data: any, adminUserId: string) =>
    api.put(`/admin/update-feed/${id}`, data, { params: { admin_user_id: adminUserId } }),
  delete: (id: string, adminUserId: string) =>
    api.delete(`/admin/delete-feed/${id}`, { params: { admin_user_id: adminUserId } }),
  bulkImport: (file: File, adminUserId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/admin/bulk-upload-feeds?admin_user_id=${adminUserId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ==================== COUNTRY ADMIN FEEDS ====================
export const countryAdminFeedsApi = {
  getMyCountry: (email: string) =>
    api.get('/admin/country/my-country', { params: { email_id: email } }),
  getFeeds: (email: string, params?: {
    limit?: number;
    offset?: number;
    feed_type?: string;
    search?: string;
  }) => api.get('/admin/country/feeds', { params: { email_id: email, ...params } }),
  createFeed: (email: string, data: any) =>
    api.post('/admin/country/feeds', data, { params: { email_id: email } }),
  updateFeed: (email: string, feedId: string, data: any) =>
    api.put(`/admin/country/feeds/${feedId}`, data, { params: { email_id: email } }),
  bulkUpload: (email: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/admin/country/feeds/bulk-upload?email_id=${email}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getTranslations: (email: string, feedId: string) =>
    api.get(`/admin/country/feeds/${feedId}/translations`, { params: { email_id: email } }),
  addTranslation: (email: string, feedId: string, data: any) =>
    api.post(`/admin/country/feeds/${feedId}/translations`, data, { params: { email_id: email } }),
  deleteTranslation: (email: string, feedId: string, translationId: string) =>
    api.delete(`/admin/country/feeds/${feedId}/translations/${translationId}`, { params: { email_id: email } }),
  deleteFeed: (email: string, feedId: string) =>
    api.delete(`/admin/country/feeds/${feedId}`, { params: { email_id: email } }),
};

// ==================== COUNTRIES ====================
export const countriesApi = {
  getAll: () => api.get('/auth/countries'),
  getById: (id: string) => api.get(`/countries/${id}`),
  create: (data: any, adminUserId: string) =>
    api.post('/admin/countries', data, { params: { admin_user_id: adminUserId } }),
  update: (id: string, data: any, adminUserId: string) =>
    api.put(`/admin/countries/${id}`, data, { params: { admin_user_id: adminUserId } }),
};

// ==================== ORGANIZATIONS ====================
export const organizationsApi = {
  // Admin endpoints
  getAll: (adminUserId: string) =>
    api.get(`/admin/organizations`, { params: { admin_user_id: adminUserId } }),
  getById: (id: string, adminUserId: string) =>
    api.get(`/admin/organizations/${id}`, { params: { admin_user_id: adminUserId } }),
  create: (data: any, adminUserId: string) =>
    api.post(`/admin/organizations`, data, { params: { admin_user_id: adminUserId } }),
  update: (id: string, data: any, adminUserId: string) =>
    api.put(`/admin/organizations/${id}`, data, { params: { admin_user_id: adminUserId } }),
  // Public organization endpoints (self-service)
  requestOtp: (email: string, purpose: 'registration' | 'login') =>
    api.post('/org/request-otp', { email, purpose }),
  register: (data: any) => api.post('/org/register', data),
  login: (data: { contact_email: string; otp_code: string }) => api.post('/org/login', data),
  createApiKey: (orgId: string, data: { contact_email: string; otp_code: string; key_name?: string; expires_in_days?: number }) =>
    api.post(`/org/${orgId}/api-keys/create?contact_email=${encodeURIComponent(data.contact_email)}&otp_code=${encodeURIComponent(data.otp_code)}${data.key_name ? `&key_name=${encodeURIComponent(data.key_name)}` : ''}${data.expires_in_days ? `&expires_in_days=${data.expires_in_days}` : ''}`),
};

// ==================== API KEYS ====================
export const apiKeysApi = {
  getAll: (orgId: string, adminUserId: string) =>
    api.get(`/admin/organizations/${orgId}/api-keys`, { params: { admin_user_id: adminUserId } }),
  create: (orgId: string, data: any, adminUserId: string) =>
    api.post(`/admin/organizations/${orgId}/api-keys`, data, { params: { admin_user_id: adminUserId } }),
  revoke: (keyId: string, adminUserId: string) =>
    api.delete(`/admin/api-keys/${keyId}`, { params: { admin_user_id: adminUserId } }),
};

// ==================== SUPERADMIN ====================
export const superadminApi = {
  check: (email: string) =>
    api.get('/admin/superadmin/check', { params: { email_id: email } }),
  createCountryAdmin: (data: {
    admin_email: string;
    admin_name: string;
    country_id: string;
    superadmin_email: string;
  }) =>
    api.post('/admin/superadmin/create-country-admin', null, { params: data }),
  listCountryAdmins: (superadminEmail: string) =>
    api.get('/admin/superadmin/country-admins', { params: { superadmin_email: superadminEmail } }),
  removeCountryAdmin: (adminId: string, superadminEmail: string) =>
    api.delete(`/admin/superadmin/country-admin/${adminId}`, { params: { superadmin_email: superadminEmail } }),
};
