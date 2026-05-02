import type { CurrentUserResponse } from '@/types/api';

export async function fetchCurrentUser(): Promise<CurrentUserResponse> {
  const res = await fetch('/api/v1/auth/me', { cache: 'no-store' });
  if (!res.ok) throw new Error(`auth/me ${res.status}: ${res.statusText}`);
  return res.json();
}

const HST_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Pacific/Honolulu',
  hour: 'numeric',
  hour12: false,
});

export function hawaiianGreeting(now: Date = new Date()): string {
  const hour = Number(HST_FORMATTER.format(now));
  if (hour >= 5 && hour < 12) return 'Aloha Kakahiaka';
  if (hour >= 12 && hour < 18) return 'Aloha Auinala';
  return 'Aloha Ahiahi';
}
