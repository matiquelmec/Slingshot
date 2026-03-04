'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import { Crosshair, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle2, Loader2, Zap } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'

type Tab = 'password' | 'magic'

export default function LoginPage() {
    const router = useRouter()
    const [tab, setTab] = useState<Tab>('magic')

    // Password login
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Magic link
    const [magicEmail, setMagicEmail] = useState('')
    const [magicLoading, setMagicLoading] = useState(false)
    const [magicError, setMagicError] = useState<string | null>(null)
    const [magicSent, setMagicSent] = useState(false)

    const handlePassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)
        const supabase = createClient()
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) {
            setError(error.message === 'Invalid login credentials'
                ? 'Email o contraseña incorrectos.'
                : error.message)
            setLoading(false)
            return
        }
        router.push('/')
        router.refresh()
    }

    const handleMagicLink = async (e: React.FormEvent) => {
        e.preventDefault()
        setMagicLoading(true)
        setMagicError(null)
        const supabase = createClient()
        const { error } = await supabase.auth.signInWithOtp({
            email: magicEmail,
            options: {
                emailRedirectTo: `${window.location.origin}/auth/callback`,
                shouldCreateUser: true, // Crea cuenta si no existe — registra y loguea en un paso
            }
        })
        if (error) {
            setMagicError(error.message)
            setMagicLoading(false)
            return
        }
        setMagicSent(true)
        setMagicLoading(false)
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
                    <div className="mb-6">
                        <h2 className="text-lg font-bold text-white/90 tracking-wider">ACCESO AL SISTEMA</h2>
                        <p className="text-xs text-white/40 mt-1 tracking-wide">Elige tu método de autenticación</p>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-2 mb-6 bg-white/[0.03] rounded-xl p-1 border border-white/5">
                        <button
                            id="tab-magic"
                            onClick={() => setTab('magic')}
                            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all ${tab === 'magic'
                                    ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/30 shadow-[0_0_12px_rgba(0,229,255,0.1)]'
                                    : 'text-white/30 hover:text-white/60'
                                }`}
                        >
                            <Zap size={13} />
                            MAGIC LINK
                        </button>
                        <button
                            id="tab-password"
                            onClick={() => setTab('password')}
                            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all ${tab === 'password'
                                    ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/30 shadow-[0_0_12px_rgba(0,229,255,0.1)]'
                                    : 'text-white/30 hover:text-white/60'
                                }`}
                        >
                            <Lock size={13} />
                            CONTRASEÑA
                        </button>
                    </div>

                    <AnimatePresence mode="wait">
                        {/* ── MAGIC LINK TAB ── */}
                        {tab === 'magic' && (
                            <motion.div
                                key="magic"
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 10 }}
                                transition={{ duration: 0.2 }}
                            >
                                {magicSent ? (
                                    <div className="text-center py-4">
                                        <div className="flex items-center justify-center mb-4">
                                            <div className="p-3.5 bg-neon-green/10 rounded-full border border-neon-green/30">
                                                <CheckCircle2 size={28} className="text-neon-green" />
                                            </div>
                                        </div>
                                        <p className="text-sm font-bold text-white/80 tracking-wide mb-2">ENLACE ENVIADO</p>
                                        <p className="text-xs text-white/40 mb-1">Revisa tu bandeja de entrada en</p>
                                        <p className="text-sm text-neon-cyan font-bold mb-5">{magicEmail}</p>
                                        <p className="text-[11px] text-white/30">
                                            Haz click en el enlace del email para entrar al sistema.<br />
                                            Si eres nuevo, tu cuenta se creará automáticamente.
                                        </p>
                                        <button
                                            onClick={() => { setMagicSent(false); setMagicEmail('') }}
                                            className="mt-5 text-xs text-white/30 hover:text-white/60 transition-colors underline"
                                        >
                                            Usar otro email
                                        </button>
                                    </div>
                                ) : (
                                    <form onSubmit={handleMagicLink} className="flex flex-col gap-4">
                                        <div className="bg-neon-cyan/5 border border-neon-cyan/15 rounded-xl px-4 py-3">
                                            <p className="text-[10px] font-bold tracking-wider text-neon-cyan/70 mb-0.5">SIN CONTRASEÑA</p>
                                            <p className="text-[10px] text-white/40">
                                                Te enviamos un enlace mágico a tu email. Un click y entras.
                                                Si no tienes cuenta, se crea automáticamente con plan FREE.
                                            </p>
                                        </div>

                                        <div className="flex flex-col gap-1.5">
                                            <label className="text-[10px] font-bold tracking-[0.2em] text-white/50">
                                                TU EMAIL
                                            </label>
                                            <div className="relative">
                                                <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
                                                <input
                                                    id="magic-email"
                                                    type="email"
                                                    value={magicEmail}
                                                    onChange={(e) => setMagicEmail(e.target.value)}
                                                    placeholder="operador@slingshot.io"
                                                    required
                                                    className="w-full bg-white/[0.04] border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white/90 placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(0,229,255,0.1)] transition-all"
                                                />
                                            </div>
                                        </div>

                                        {magicError && (
                                            <motion.div
                                                initial={{ opacity: 0, y: -8 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="flex items-center gap-2.5 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3"
                                            >
                                                <AlertCircle size={14} className="text-red-400 shrink-0" />
                                                <span className="text-xs text-red-400">{magicError}</span>
                                            </motion.div>
                                        )}

                                        <button
                                            id="btn-magic-link"
                                            type="submit"
                                            disabled={magicLoading}
                                            className="mt-1 w-full bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/30 hover:border-neon-cyan/60 text-neon-cyan font-bold tracking-[0.2em] text-sm py-3.5 rounded-xl transition-all hover:shadow-[0_0_20px_rgba(0,229,255,0.2)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                        >
                                            {magicLoading ? (
                                                <><Loader2 size={14} className="animate-spin" /> ENVIANDO...</>
                                            ) : (
                                                <><Zap size={14} /> ENVIAR MAGIC LINK</>
                                            )}
                                        </button>
                                    </form>
                                )}
                            </motion.div>
                        )}

                        {/* ── PASSWORD TAB ── */}
                        {tab === 'password' && (
                            <motion.div
                                key="password"
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                            >
                                <form onSubmit={handlePassword} className="flex flex-col gap-4">
                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-[10px] font-bold tracking-[0.2em] text-white/50">
                                            IDENTIFICADOR
                                        </label>
                                        <div className="relative">
                                            <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
                                            <input
                                                id="email"
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                placeholder="operador@slingshot.io"
                                                required
                                                className="w-full bg-white/[0.04] border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white/90 placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(0,229,255,0.1)] transition-all"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-[10px] font-bold tracking-[0.2em] text-white/50">
                                            CLAVE DE ACCESO
                                        </label>
                                        <div className="relative">
                                            <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
                                            <input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                placeholder="••••••••••••"
                                                required
                                                className="w-full bg-white/[0.04] border border-white/10 rounded-xl pl-10 pr-12 py-3 text-sm text-white/90 placeholder:text-white/20 focus:outline-none focus:border-neon-cyan/50 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(0,229,255,0.1)] transition-all"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
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
                                        disabled={loading}
                                        className="mt-1 w-full bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/30 hover:border-neon-cyan/60 text-neon-cyan font-bold tracking-[0.2em] text-sm py-3.5 rounded-xl transition-all hover:shadow-[0_0_20px_rgba(0,229,255,0.2)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                    >
                                        {loading ? (
                                            <><Loader2 size={14} className="animate-spin" /> AUTENTICANDO...</>
                                        ) : (
                                            'ACCEDER AL SISTEMA'
                                        )}
                                    </button>
                                </form>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <div className="mt-6 pt-6 border-t border-white/5 text-center">
                        <p className="text-xs text-white/30">
                            ¿Sin cuenta?{' '}
                            <Link href="/register" className="text-neon-cyan/70 hover:text-neon-cyan transition-colors font-bold tracking-wider">
                                REGISTRARSE
                            </Link>
                            {' '}— o usa Magic Link para acceso inmediato.
                        </p>
                    </div>
                </div>

                <p className="text-center text-[10px] text-white/15 mt-6 tracking-widest">
                    SLINGSHOT v2.0 — ACCESO RESTRINGIDO
                </p>
            </motion.div>
        </div>
    )
}
