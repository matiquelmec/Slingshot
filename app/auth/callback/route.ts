import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function GET(request: Request) {
    const { searchParams, origin } = new URL(request.url)
    const code = searchParams.get('code')
    const next = searchParams.get('next') ?? '/'

    console.log('[Auth Callback] Recibido. code presente:', !!code, '| origin:', origin)

    if (!code) {
        console.log('[Auth Callback] No hay code — redirigiendo a login con error')
        return NextResponse.redirect(`${origin}/login?error=no_code`)
    }

    const cookieStore = await cookies()
    const allCookies = cookieStore.getAll()
    console.log('[Auth Callback] Cookies en request:', allCookies.map(c => c.name))

    // Crear el redirect ANTES para escribir los cookies de sesión directamente sobre él
    const redirectTo = next.startsWith('/') ? `${origin}${next}` : `${origin}/${next}`
    const redirectResponse = NextResponse.redirect(redirectTo)

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                getAll() {
                    return cookieStore.getAll()
                },
                setAll(cookiesToSet) {
                    console.log('[Auth Callback] Escribiendo cookies de sesión:', cookiesToSet.map(c => c.name))
                    cookiesToSet.forEach(({ name, value, options }) => {
                        // Escribir sobre la redirect response para que el browser los reciba
                        redirectResponse.cookies.set(name, value, options)
                    })
                },
            },
        }
    )

    const { data, error } = await supabase.auth.exchangeCodeForSession(code)

    if (error) {
        console.error('[Auth Callback] ERROR en exchangeCodeForSession:', error.message)
        return NextResponse.redirect(`${origin}/login?error=exchange_failed`)
    }

    console.log('[Auth Callback] ✅ Sesión creada. Usuario:', data.session?.user?.email)
    return redirectResponse
}
