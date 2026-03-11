'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export interface UserTier {
    tier: 'free' | 'pro' | 'enterprise'
    max_watchlist: number
    telegram_alerts: boolean
    api_access: boolean
    valid_until: string | null
}

export interface UserProfile {
    id: string
    email: string | null
    tier: UserTier
}

const DEFAULT_TIER: UserTier = {
    tier: 'free',
    max_watchlist: 5,
    telegram_alerts: false,
    api_access: false,
    valid_until: null,
}

/**
 * Hook central de identidad del usuario.
 * 
 * Expone: user (perfil + tier), isLoading, isAuthenticated.
 * Se ejecuta una sola vez al montar — los datos quedan en caché
 * mientras el componente esté montado.
 * 
 * Uso:
 *   const { user, isLoading } = useUser()
 *   if (!user) return null  // no autenticado
 *   console.log(user.tier.max_watchlist)  // 3 (free), 20 (pro)
 */
export function useUser() {
    const [user, setUser] = useState<UserProfile | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        let mounted = true

        async function fetchUser() {
            const supabase = createClient()

            // 1. Obtener sesión actual
            const { data: { user: authUser } } = await supabase.auth.getUser()
            if (!authUser || !mounted) {
                setIsLoading(false)
                return
            }

            // 2. Obtener tier del usuario (subscription_tiers)
            const { data: tierData } = await supabase
                .from('subscription_tiers')
                .select('tier, max_watchlist, telegram_alerts, api_access, valid_until')
                .eq('user_id', authUser.id)
                .single()

            if (!mounted) return

            setUser({
                id: authUser.id,
                email: authUser.email ?? null,
                tier: tierData ?? DEFAULT_TIER,
            })
            setIsLoading(false)
        }

        fetchUser()
        return () => { mounted = false }
    }, [])

    return {
        user,
        isLoading,
        isAuthenticated: !isLoading && user !== null,
    }
}
