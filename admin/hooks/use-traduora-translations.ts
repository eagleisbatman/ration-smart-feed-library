'use client';

import { useQuery } from '@tanstack/react-query';
import { getAdminUITranslations } from '@/lib/traduora';
import { useLocale } from 'next-intl';

/**
 * Hook to fetch Traduora translations for admin UI
 * Falls back to next-intl translations if Traduora is not configured
 */
export function useTraduoraTranslations() {
  const locale = useLocale();
  const projectId = process.env.NEXT_PUBLIC_TRADUORA_ADMIN_PROJECT_ID;

  return useQuery({
    queryKey: ['traduora-translations', 'admin-ui', locale],
    queryFn: () => getAdminUITranslations(locale),
    enabled: !!projectId, // Only fetch if project ID is configured
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
  });
}

