/**
 * Secure Storage Utilities
 * Provides secure storage for sensitive data like API keys
 * Uses sessionStorage with encryption and expiration
 */

const STORAGE_PREFIX = 'rs_';
const API_KEY_KEY = `${STORAGE_PREFIX}api_key`;
const USER_KEY = `${STORAGE_PREFIX}user`;
const USER_EMAIL_KEY = `${STORAGE_PREFIX}user_email`;
const SESSION_EXPIRY_KEY = `${STORAGE_PREFIX}session_expiry`;
const SESSION_DURATION_MS = 8 * 60 * 60 * 1000; // 8 hours

/**
 * Simple encryption/decryption (for client-side storage)
 * Note: This is not cryptographically secure, but prevents casual inspection
 * For production, use httpOnly cookies with backend encryption
 */
function simpleEncrypt(text: string): string {
  if (typeof window === 'undefined') return text;
  try {
    // Simple base64 encoding with obfuscation
    const encoded = btoa(encodeURIComponent(text));
    return encoded.split('').reverse().join('');
  } catch {
    return text;
  }
}

function simpleDecrypt(encrypted: string): string {
  if (typeof window === 'undefined') return encrypted;
  try {
    const reversed = encrypted.split('').reverse().join('');
    return decodeURIComponent(atob(reversed));
  } catch {
    return encrypted;
  }
}

/**
 * Check if session has expired
 */
function isSessionExpired(): boolean {
  if (typeof window === 'undefined') return true;
  const expiryStr = sessionStorage.getItem(SESSION_EXPIRY_KEY);
  if (!expiryStr) return true;
  
  try {
    const expiry = parseInt(expiryStr, 10);
    return Date.now() > expiry;
  } catch {
    return true;
  }
}

/**
 * Set session expiry timestamp
 */
function setSessionExpiry(): void {
  if (typeof window === 'undefined') return;
  const expiry = Date.now() + SESSION_DURATION_MS;
  sessionStorage.setItem(SESSION_EXPIRY_KEY, expiry.toString());
}

/**
 * Secure storage for API keys and sensitive data
 */
export const secureStorage = {
  /**
   * Store API key securely
   */
  setApiKey(apiKey: string): void {
    if (typeof window === 'undefined') return;
    try {
      const encrypted = simpleEncrypt(apiKey);
      sessionStorage.setItem(API_KEY_KEY, encrypted);
      setSessionExpiry();
    } catch (error) {
      console.error('Failed to store API key:', error);
    }
  },

  /**
   * Get API key securely
   */
  getApiKey(): string | null {
    if (typeof window === 'undefined') return null;
    if (isSessionExpired()) {
      this.clearAll();
      return null;
    }
    
    try {
      const encrypted = sessionStorage.getItem(API_KEY_KEY);
      if (!encrypted) return null;
      return simpleDecrypt(encrypted);
    } catch (error) {
      console.error('Failed to retrieve API key:', error);
      return null;
    }
  },

  /**
   * Store user data
   */
  setUser(user: any): void {
    if (typeof window === 'undefined') return;
    try {
      sessionStorage.setItem(USER_KEY, JSON.stringify(user));
      if (user.email_id) {
        sessionStorage.setItem(USER_EMAIL_KEY, user.email_id);
      }
      setSessionExpiry();
    } catch (error) {
      console.error('Failed to store user:', error);
    }
  },

  /**
   * Get user data
   */
  getUser(): any | null {
    if (typeof window === 'undefined') return null;
    if (isSessionExpired()) {
      this.clearAll();
      return null;
    }
    
    try {
      const userStr = sessionStorage.getItem(USER_KEY);
      if (!userStr) return null;
      return JSON.parse(userStr);
    } catch (error) {
      console.error('Failed to retrieve user:', error);
      return null;
    }
  },

  /**
   * Get user email
   */
  getUserEmail(): string | null {
    if (typeof window === 'undefined') return null;
    if (isSessionExpired()) {
      this.clearAll();
      return null;
    }
    
    return sessionStorage.getItem(USER_EMAIL_KEY);
  },

  /**
   * Clear all secure storage
   */
  clearAll(): void {
    if (typeof window === 'undefined') return;
    try {
      sessionStorage.removeItem(API_KEY_KEY);
      sessionStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(USER_EMAIL_KEY);
      sessionStorage.removeItem(SESSION_EXPIRY_KEY);
      
      // Also clear legacy localStorage items
      localStorage.removeItem('api_key');
      localStorage.removeItem('user');
      localStorage.removeItem('user_email');
    } catch (error) {
      console.error('Failed to clear storage:', error);
    }
  },

  /**
   * Check if session is valid
   */
  isSessionValid(): boolean {
    if (typeof window === 'undefined') return false;
    return !isSessionExpired();
  },

  /**
   * Refresh session expiry
   */
  refreshSession(): void {
    if (typeof window === 'undefined') return;
    if (this.isSessionValid()) {
      setSessionExpiry();
    }
  },
};

/**
 * Auto-refresh session on user activity
 */
if (typeof window !== 'undefined') {
  let refreshTimeout: NodeJS.Timeout | null = null;
  
  const refreshSessionOnActivity = () => {
    if (refreshTimeout) {
      clearTimeout(refreshTimeout);
    }
    
    refreshTimeout = setTimeout(() => {
      secureStorage.refreshSession();
    }, 5 * 60 * 1000); // Refresh every 5 minutes of activity
  };

  // Listen for user activity
  ['click', 'keypress', 'scroll', 'mousemove'].forEach(event => {
    window.addEventListener(event, refreshSessionOnActivity, { passive: true });
  });
}

