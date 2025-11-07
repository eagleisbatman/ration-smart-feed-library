'use client';

import { useTranslations as useNextIntlTranslations } from 'next-intl';
import { useTraduoraTranslations } from '@/hooks/use-traduora-translations';
import { useMemo } from 'react';

/**
 * Enhanced translations hook that merges Traduora and next-intl translations
 * Traduora translations take precedence when available
 */
export function useTranslations(namespace?: string) {
  const nextIntlT = useNextIntlTranslations(namespace);
  const { data: traduoraTranslations = {} } = useTraduoraTranslations();

  // Merge translations: Traduora takes precedence
  const mergedTranslations = useMemo(() => {
    return (key: string, values?: Record<string, any>) => {
      // Try Traduora first
      const fullKey = namespace ? `${namespace}.${key}` : key;
      if (traduoraTranslations[fullKey]) {
        let value = traduoraTranslations[fullKey];
        // Simple variable replacement
        if (values) {
          Object.entries(values).forEach(([k, v]) => {
            value = value.replace(`{${k}}`, String(v));
          });
        }
        return value;
      }
      // Fallback to next-intl
      return nextIntlT(key, values);
    };
  }, [traduoraTranslations, namespace, nextIntlT]);

  return mergedTranslations;
}

