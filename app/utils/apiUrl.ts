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
    if (typeof window !== 'undefined') {
        const protocol = window.location.protocol;
        const host = window.location.hostname;
        return `${protocol}//${host}:8000`;
    }
    return 'http://localhost:8000';
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