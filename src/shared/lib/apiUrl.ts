/**
 * Institutional Dynamic URL Resolver (Shared FSD Primitive)
 * Automatically binds browser requests to relative path under HTTPS/Vercel
 * or to local/remote backend endpoints on development environments.
 */
export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    if (window.location.protocol === 'https:') {
      if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.startsWith('https://')) {
        return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
      }
      return '';
    }
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
  }
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }
  return 'http://80.65.211.99:8000';
}

export function getWsBaseUrl(): string {
  if (typeof window !== 'undefined') {
    if (window.location.protocol === 'https:') {
      if (process.env.NEXT_PUBLIC_API_WS_URL && process.env.NEXT_PUBLIC_API_WS_URL.startsWith('wss://')) {
        return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
      }
      return '';
    }
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.hostname}:8000`;
    }
  }
  if (process.env.NEXT_PUBLIC_API_WS_URL) {
    return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
  }
  return 'ws://80.65.211.99:8000';
}
