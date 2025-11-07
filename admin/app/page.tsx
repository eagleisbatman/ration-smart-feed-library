import { redirect } from 'next/navigation';
import { locales } from '@/lib/i18n';

export default function RootPage() {
  redirect(`/${locales[0]}`);
}
