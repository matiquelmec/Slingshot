'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { Crosshair, Mail, Lock, Eye, EyeOff, AlertCircle, Loader2 } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
    const router = useRouter()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleLogin = async (e: React.FormEvent) => {
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
            {/* Glow top */}
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
                        <p className="text-xs text-white/40 mt-1 tracking-wide">Ingresa tus credenciales para continuar</p>
                    </div>

                    <form onSubmit={handleLogin} className="flex flex-col gap-4">
                        {/* Email */}
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

                        {/* Password */}
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

                        {/* Error */}
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

                        {/* Submit */}
                        <button
                            id="btn-login"
                            type="submit"
                            disabled={loading}
                            className="mt-2 w-full bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/30 hover:border-neon-cyan/60 text-neon-cyan font-bold tracking-[0.2em] text-sm py-3.5 rounded-xl transition-all hover:shadow-[0_0_20px_rgba(0,229,255,0.2)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {loading ? (
                                <><Loader2 size={14} className="animate-spin" /> AUTENTICANDO...</>
                            ) : (
                                'ACCEDER AL SISTEMA'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 pt-6 border-t border-white/5 text-center">
                        <p className="text-xs text-white/30">
                            ¿Sin acceso?{' '}
                            <Link href="/register" className="text-neon-cyan/70 hover:text-neon-cyan transition-colors font-bold tracking-wider">
                                SOLICITAR REGISTRO
                            </Link>
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
