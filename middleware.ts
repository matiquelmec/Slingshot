import { type NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

export async function middleware(request: NextRequest) {
    return await updateSession(request)
}

export const config = {
    matcher: [
        /*
         * Aplicar middleware a todas las rutas EXCEPTO:
         * - _next/static (archivos estáticos)
         * - _next/image (optimización de imágenes)
         * - favicon.ico, archivos de imagen
         */
        '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
    ],
}
