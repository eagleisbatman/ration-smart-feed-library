/**
 * Authentication utilities and session management
 */

import { secureStorage } from './secure-storage';

export interface User {
  id: string;
  name: string;
  email_id: string;
  country_id?: string;
  is_admin?: boolean;
  is_superadmin?: boolean;
  country_admin_country_id?: string;
  organization_admin_org_id?: string;
}

export const auth = {
  /**
   * Get current user from secure storage
   */
  getCurrentUser(): User | null {
    return secureStorage.getUser();
  },

  /**
   * Set current user in secure storage
   */
  setCurrentUser(user: User): void {
    secureStorage.setUser(user);
  },

  /**
   * Clear user session
   */
  clearSession(): void {
    secureStorage.clearAll();
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.getCurrentUser() !== null;
  },

  /**
   * Check if user is superadmin
   */
  isSuperadmin(): boolean {
    const user = this.getCurrentUser();
    return user?.is_superadmin === true;
  },

  /**
   * Check if user is country admin
   */
  isCountryAdmin(): boolean {
    const user = this.getCurrentUser();
    return !!user?.country_admin_country_id;
  },

  /**
   * Check if user is organization admin
   */
  isOrganizationAdmin(): boolean {
    const user = this.getCurrentUser();
    return !!user?.organization_admin_org_id;
  },

  /**
   * Get user role
   */
  getUserRole(): 'superadmin' | 'country_admin' | 'organization_admin' | 'admin' | 'user' | null {
    const user = this.getCurrentUser();
    if (!user) return null;
    if (user.is_superadmin) return 'superadmin';
    if (user.country_admin_country_id) return 'country_admin';
    if (user.organization_admin_org_id) return 'organization_admin';
    if (user.is_admin) return 'admin';
    return 'user';
  },

  /**
   * Get redirect path based on user role
   */
  getRedirectPath(): string {
    const role = this.getUserRole();
    switch (role) {
      case 'superadmin':
        return '/superadmin';
      case 'country_admin':
        return '/country-admin';
      case 'organization_admin':
        return '/organizations';
      case 'admin':
        return '/';
      default:
        return '/login';
    }
  },
};

