/**
 * Institutional Dynamic URL Resolver (Shared FSD Primitive)
 * Automatically binds browser requests to relative path (/api/v1/...)
 * so Next.js rewrites proxy seamlessly to the configured backend server
 * on both Vercel HTTPS and local development (localhost:3000).
 */
export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    if (window.location.protocol === 'https:') {
      if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.startsWith('https://')) {
        return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
      }
      return '';
    }
    return '';
  }
  if (process.env.BACKEND_INTERNAL_URL) {
    return process.env.BACKEND_INTERNAL_URL.replace(/\/$/, '');
  }
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }
  return 'http://127.0.0.1:8000';
}

export function getWsBaseUrl(): string {
  if (typeof window !== 'undefined') {
    if (window.location.protocol === 'https:') {
      if (process.env.NEXT_PUBLIC_API_WS_URL && process.env.NEXT_PUBLIC_API_WS_URL.startsWith('wss://')) {
        return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
      }
      return '';
    }
  }
  if (process.env.NEXT_PUBLIC_API_WS_URL) {
    return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
  }
  return 'ws://127.0.0.1:8000';
}
