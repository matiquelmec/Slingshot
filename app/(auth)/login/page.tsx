'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Crosshair, Mail, Lock, Eye, EyeOff, AlertCircle, Loader2 } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function LoginPage() {
    const router = useRouter()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [loadingGoogle, setLoadingGoogle] = useState(false)
    const [loadingPassword, setLoadingPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleGoogle = async () => {
        setLoadingGoogle(true)
        setError(null)
        const supabase = createClient()
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: `${window.location.origin}/auth/callback`,
            },
        })
        if (error) {
            setError(error.message)
            setLoadingGoogle(false)
        }
        // Si no hay error, el browser redirige a Google automáticamente
    }

    const handlePassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoadingPassword(true)
        setError(null)
        const supabase = createClient()
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) {
            setError(error.message === 'Invalid login credentials'
                ? 'Email o contraseña incorrectos.'
                : error.message)
            setLoadingPassword(false)
            return
        }
        router.push('/')
        router.refresh()
    }

    return (
        <div className="min-h-screen w-full bg-[#02040A] flex items-center justify-center relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#111A2C] via-[#02040A] to-[#010204]" />
            <div
                className="absolute inset-0 opacity-[0.03]"
                style={{
                    backgroundImage: 'linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)',
                    backgroundSize: '50px 50px'
                }}
            />
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-neon-cyan/5 blur-[120px] rounded-full pointer-events-none" />

            <motion.div
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="relative z-10 w-full max-w-md px-6"
            >
                {/* Logo */}
                <div className="flex flex-col items-center mb-10">
                    <div className="flex items-center justify-center bg-gradient-to-br from-neon-cyan/20 to-transparent p-3.5 rounded-2xl border border-neon-cyan/30 shadow-[0_0_30px_rgba(0,229,255,0.2)] mb-4">
                        <Crosshair className="text-neon-cyan" size={28} />
                    </div>
                    <h1 className="text-2xl font-black tracking-[0.25em] text-white/90 drop-shadow-[0_0_10px_rgba(0,229,255,0.4)]">
                        SLINGSHOT
                    </h1>
                    <p className="text-[10px] text-neon-cyan/60 tracking-[0.3em] font-semibold mt-1">
                        ESTRATEGIA CUANTITATIVA INSTITUCIONAL
                    </p>
                </div>

                {/* Card */}
                <div className="bg-black/40 border border-white/8 rounded-2xl p-8 backdrop-blur-2xl shadow-[0_0_60px_rgba(0,0,0,0.6)]">
                    <div className="mb-7">
                        <h2 className="text-lg font-bold text-white/90 tracking-wider">ACCESO AL SISTEMA</h2>
                        <p className="text-xs text-white/40 mt-1 tracking-wide">Ingresa para continuar</p>
                    </div>

                    {/* ── GOOGLE BUTTON (Primary) ── */}
                    <button
                        id="btn-google"
                        onClick={handleGoogle}
                        disabled={loadingGoogle || loadingPassword}
                        className="w-full flex items-center justify-center gap-3 bg-white hover:bg-gray-100 text-gray-800 font-bold text-sm py-3.5 rounded-xl transition-all shadow-[0_2px_12px_rgba(255,255,255,0.08)] hover:shadow-[0_4px_20px_rgba(255,255,255,0.14)] disabled:opacity-50 disabled:cursor-not-allowed mb-5"
                    >
                        {loadingGoogle ? (
                            <Loader2 size={18} className="animate-spin text-gray-500" />
                        ) : (
                            /* Google "G" SVG oficial */
                            <svg width="18" height="18" viewBox="0 0 48 48">
                                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
                                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
                                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
                                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
                                <path fill="none" d="M0 0h48v48H0z" />
                            </svg>
                        )}
                        {loadingGoogle ? 'REDIRIGIENDO...' : 'Continuar con Google'}
                    </button>

                    {/* Divider */}
                    <div className="flex items-center gap-4 mb-5">
                        <div className="flex-1 h-px bg-white/8" />
                        <span className="text-[10px] font-bold tracking-widest text-white/20">O CON CONTRASEÑA</span>
                        <div className="flex-1 h-px bg-white/8" />
                    </div>

                    {/* ── EMAIL + PASSWORD (Secondary) ── */}
                    <form onSubmit={handlePassword} className="flex flex-col gap-4">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold tracking-[0.2em] text-white/40">EMAIL</label>
                            <div className="relative">
                                <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/25" />
                                <input
                                    id="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="operador@slingshot.io"
                                    className="w-full bg-white/[0.03] border border-white/8 rounded-xl pl-10 pr-4 py-3 text-sm text-white/80 placeholder:text-white/15 focus:outline-none focus:border-neon-cyan/40 focus:bg-white/[0.05] transition-all"
                                />
                            </div>
                        </div>

                        <div className="flex flex-col gap-1.5">
                            <label className="text-[10px] font-bold tracking-[0.2em] text-white/40">CONTRASEÑA</label>
                            <div className="relative">
                                <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/25" />
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••••••"
                                    className="w-full bg-white/[0.03] border border-white/8 rounded-xl pl-10 pr-12 py-3 text-sm text-white/80 placeholder:text-white/15 focus:outline-none focus:border-neon-cyan/40 focus:bg-white/[0.05] transition-all"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/25 hover:text-white/50 transition-colors"
                                >
                                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                                </button>
                            </div>
                        </div>

                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: -8 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="flex items-center gap-2.5 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3"
                            >
                                <AlertCircle size={14} className="text-red-400 shrink-0" />
                                <span className="text-xs text-red-400">{error}</span>
                            </motion.div>
                        )}

                        <button
                            id="btn-login"
                            type="submit"
                            disabled={!email || !password || loadingPassword || loadingGoogle}
                            className="w-full bg-white/5 hover:bg-white/8 border border-white/10 hover:border-white/20 text-white/70 hover:text-white/90 font-bold tracking-[0.15em] text-sm py-3 rounded-xl transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {loadingPassword
                                ? <><Loader2 size={14} className="animate-spin" /> AUTENTICANDO...</>
                                : 'ACCEDER CON CONTRASEÑA'
                            }
                        </button>
                    </form>

                    <div className="mt-6 pt-5 border-t border-white/5 text-center">
                        <p className="text-xs text-white/25">
                            ¿Sin cuenta?{' '}
                            <Link href="/register" className="text-neon-cyan/60 hover:text-neon-cyan transition-colors font-bold tracking-wider">
                                REGISTRARSE
                            </Link>
                        </p>
                    </div>
                </div>

                <p className="text-center text-[10px] text-white/10 mt-6 tracking-widest">
                    SLINGSHOT v2.0 — ACCESO RESTRINGIDO
                </p>
            </motion.div>
        </div>
    )
}
