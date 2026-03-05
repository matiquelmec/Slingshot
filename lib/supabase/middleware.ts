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
                    // Paso 1: escribir en el request (para que esté disponible en el handler)
                    cookiesToSet.forEach(({ name, value }) =>
                        request.cookies.set(name, value)
                    )
                    // Paso 2: crear nueva respuesta con el request actualizado
                    supabaseResponse = NextResponse.next({ request })
                    // Paso 3: escribir los cookies en la respuesta final
                    cookiesToSet.forEach(({ name, value, options }) =>
                        supabaseResponse.cookies.set(name, value, options)
                    )
                },
            },
        }
    )

    // IMPORTANTE: No agregar lógica entre createServerClient y getUser,
    // ya que puede causar bugs difíciles de depurar.
    const { data: { user } } = await supabase.auth.getUser()

    // Rutas públicas (sin auth requerida)
    const pathname = request.nextUrl.pathname
    const isPublicRoute =
        pathname.startsWith('/login') ||
        pathname.startsWith('/register') ||
        pathname.startsWith('/auth/') ||   // cubre /auth/callback y cualquier sub-ruta
        pathname.startsWith('/_next') ||
        pathname === '/favicon.ico'

    // Sin usuario + ruta protegida → login
    if (!user && !isPublicRoute) {
        const url = request.nextUrl.clone()
        url.pathname = '/login'
        return NextResponse.redirect(url)
    }

    // Con usuario + intentando ir a login/register → dashboard
    if (user && (pathname === '/login' || pathname === '/register')) {
        const url = request.nextUrl.clone()
        url.pathname = '/'
        return NextResponse.redirect(url)
    }

    return supabaseResponse
}
