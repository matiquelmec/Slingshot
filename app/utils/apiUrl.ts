/**
 * Resuelve dinámicamente las URLs de la API REST y WebSocket.
 * Si el cliente abre la terminal desde otra PC en la red (ej. http://192.168.1.50:3000),
 * se conectará automáticamente al backend maestro en el mismo host (puerto 8000)
 * en lugar de intentar conectar a localhost de su propia máquina.
 */

export function getApiBaseUrl(): string {
    // 🛡️ En navegador bajo HTTPS (Vercel): Forzar ruta relativa '' para viajar siempre por el proxy seguro de Next.js
    if (typeof window !== 'undefined') {
        if (window.location.protocol === 'https:') {
            if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.startsWith('https://')) {
                return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
            }
            return '';
        }
        // Localhost o LAN HTTP
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
        // En HTTPS: Un WebSocket sin encriptar (ws://) es bloqueado por el navegador como SecurityError (Mixed Content)
        if (window.location.protocol === 'https:') {
            if (process.env.NEXT_PUBLIC_API_WS_URL && process.env.NEXT_PUBLIC_API_WS_URL.startsWith('wss://')) {
                return process.env.NEXT_PUBLIC_API_WS_URL.replace(/\/$/, '');
            }
            // Retorna vacío para activar de inmediato el modo Ultra-Fast REST Polling (1.5s) sin generar errores
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