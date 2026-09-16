/**
 * Resuelve dinámicamente las URLs de la API REST y WebSocket.
 * Si el cliente abre la terminal desde otra PC en la red (ej. http://192.168.1.50:3000),
 * se conectará automáticamente al backend maestro en el mismo host (puerto 8000)
 * en lugar de intentar conectar a localhost de su propia máquina.
 */

export function getApiBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
    }
    // En Vercel o navegador remoto, usar ruta relativa para que el proxy reescriba por HTTPS
    if (typeof window !== 'undefined') {
        // Si estamos en localhost directo
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return `${window.location.protocol}//${window.location.hostname}:8000`;
        }
        // En Vercel: usar la misma URL del sitio (''), las peticiones /api/* viajan seguras por HTTPS a Vercel y Vercel las pide al VPS
        return '';
    }
    return 'http://80.65.211.99:8000';
}

export function getWsBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_API_WS_URL) {
        return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
    }
    if (typeof window !== 'undefined') {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        return `${protocol}//${host}:8000`;
    }
    return 'ws://localhost:8000';
}