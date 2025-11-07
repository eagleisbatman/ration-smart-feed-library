// lib/traduora.ts
/**
 * Traduora API Client
 * Handles fetching translations from Traduora translation management system
 */

import axios from 'axios';

const TRADUORA_URL = process.env.NEXT_PUBLIC_TRADUORA_URL || process.env.TRADUORA_URL || 'http://localhost:3000';
const TRADUORA_TOKEN = process.env.TRADUORA_TOKEN || process.env.NEXT_PUBLIC_TRADUORA_TOKEN;

export interface TraduoraTranslation {
  key: string;
  value: string;
  locale: string;
}

export interface TraduoraProject {
  id: string;
  name: string;
  defaultLocale: string;
  locales: string[];
}

class TraduoraClient {
  private baseURL: string;
  private token: string | undefined;

  constructor() {
    this.baseURL = TRADUORA_URL;
    this.token = TRADUORA_TOKEN;
  }

  private getHeaders() {
    return {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json',
    };
  }

  /**
   * Fetch all translations for a project and locale
   */
  async getTranslations(projectId: string, locale: string): Promise<Record<string, string>> {
    if (!this.token) {
      console.warn('Traduora token not configured, returning empty translations');
      return {};
    }

    try {
      const response = await axios.get(
        `${this.baseURL}/api/v1/projects/${projectId}/translations/${locale}`,
        { headers: this.getHeaders() }
      );

      // Convert array of translations to key-value object
      const translations: Record<string, string> = {};
      if (Array.isArray(response.data)) {
        response.data.forEach((item: TraduoraTranslation) => {
          translations[item.key] = item.value;
        });
      } else if (response.data.translations) {
        response.data.translations.forEach((item: TraduoraTranslation) => {
          translations[item.key] = item.value;
        });
      }

      return translations;
    } catch (error: any) {
      console.error('Failed to fetch Traduora translations:', error.message);
      return {};
    }
  }

  /**
   * Update a translation
   */
  async updateTranslation(
    projectId: string,
    locale: string,
    key: string,
    value: string
  ): Promise<boolean> {
    if (!this.token) {
      console.warn('Traduora token not configured');
      return false;
    }

    try {
      await axios.put(
        `${this.baseURL}/api/v1/projects/${projectId}/translations/${locale}/${key}`,
        { value },
        { headers: this.getHeaders() }
      );
      return true;
    } catch (error: any) {
      console.error('Failed to update Traduora translation:', error.message);
      return false;
    }
  }

  /**
   * Get project information
   */
  async getProject(projectId: string): Promise<TraduoraProject | null> {
    if (!this.token) {
      return null;
    }

    try {
      const response = await axios.get(
        `${this.baseURL}/api/v1/projects/${projectId}`,
        { headers: this.getHeaders() }
      );
      return response.data;
    } catch (error: any) {
      console.error('Failed to fetch Traduora project:', error.message);
      return null;
    }
  }
}

export const traduoraClient = new TraduoraClient();

/**
 * Get translations for admin UI
 */
export async function getAdminUITranslations(locale: string): Promise<Record<string, string>> {
  const projectId = process.env.NEXT_PUBLIC_TRADUORA_ADMIN_PROJECT_ID;
  if (!projectId) {
    return {};
  }
  return traduoraClient.getTranslations(projectId, locale);
}

/**
 * Get translations for API management UI
 */
export async function getAPIMgmtTranslations(locale: string): Promise<Record<string, string>> {
  const projectId = process.env.NEXT_PUBLIC_TRADUORA_API_MGMT_PROJECT_ID;
  if (!projectId) {
    return {};
  }
  return traduoraClient.getTranslations(projectId, locale);
}

/**
 * Get feed translations for a country
 */
export async function getFeedTranslations(
  countryCode: string,
  locale: string
): Promise<Record<string, string>> {
  const projectId = `feed-formulation-feeds-${countryCode.toLowerCase()}`;
  return traduoraClient.getTranslations(projectId, locale);
}

