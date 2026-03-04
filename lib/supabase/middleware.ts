import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
    let supabaseResponse = NextResponse.next({ request })

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                getAll() {
                    return request.cookies.getAll()
                },
                setAll(cookiesToSet) {
                    cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
                    supabaseResponse = NextResponse.next({ request })
                    cookiesToSet.forEach(({ name, value, options }) =>
                        supabaseResponse.cookies.set(name, value, options)
                    )
                },
            },
        }
    )

    // Refrescar la sesión del usuario — IMPORTANTE: no remover esta llamada.
    const { data: { user } } = await supabase.auth.getUser()

    // Rutas públicas que no requieren autenticación
    const publicRoutes = ['/login', '/register', '/auth/callback']
    const isPublicRoute = publicRoutes.some(route => request.nextUrl.pathname.startsWith(route))

    // Si no hay usuario y la ruta no es pública → redirigir a /login
    if (!user && !isPublicRoute) {
        const url = request.nextUrl.clone()
        url.pathname = '/login'
        return NextResponse.redirect(url)
    }

    // Si hay usuario y está intentando acceder a login/register → redirigir al dashboard
    if (user && (request.nextUrl.pathname === '/login' || request.nextUrl.pathname === '/register')) {
        const url = request.nextUrl.clone()
        url.pathname = '/'
        return NextResponse.redirect(url)
    }

    return supabaseResponse
}
