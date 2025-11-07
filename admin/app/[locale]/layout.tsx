import { notFound } from 'next/navigation';
import { getTranslations } from 'next-intl/server';
import { locales } from '@/lib/i18n';
import { getMessages } from 'next-intl/server';
import { Providers } from '@/components/providers/providers';

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}) {
  const t = await getTranslations({ locale, namespace: 'metadata' });

  return {
    title: t('title'),
    description: t('description'),
  };
}

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  if (!locales.includes(locale as any)) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <Providers messages={messages}>
      {children}
    </Providers>
  );
}
