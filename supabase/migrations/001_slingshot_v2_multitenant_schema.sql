-- ============================================================
-- SLINGSHOT v2.0 — Migration 001: Schema Multi-Tenant
-- Fecha: 2026-03-04
-- Aplicar en: Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. SEÑALES GLOBALES
-- No pertenecen a un usuario específico.
-- El engine Python las genera una vez para todos los usuarios.
CREATE TABLE IF NOT EXISTS public.signal_events (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    asset            TEXT NOT NULL,
    interval         TEXT NOT NULL DEFAULT '15m',
    signal_type      TEXT NOT NULL CHECK (signal_type IN ('LONG', 'SHORT')),
    entry_price      FLOAT NOT NULL,
    stop_loss        FLOAT NOT NULL,
    take_profit      FLOAT NOT NULL,
    confluence_score FLOAT,
    regime           TEXT,
    strategy         TEXT,
    trigger          TEXT,
    status           TEXT DEFAULT 'ACTIVE'
                     CHECK (status IN ('ACTIVE', 'HIT_TP', 'HIT_SL', 'EXPIRED')),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    closed_price     FLOAT,
    pnl_pct          FLOAT
);

CREATE INDEX IF NOT EXISTS idx_signal_events_asset   ON public.signal_events(asset);
CREATE INDEX IF NOT EXISTS idx_signal_events_status  ON public.signal_events(status);
CREATE INDEX IF NOT EXISTS idx_signal_events_created ON public.signal_events(created_at DESC);

-- 2. WATCHLISTS PERSONALES
-- Cada usuario elige qué activos monitorear.
-- El orquestador de workers usa esto para saber qué símbolos necesitan un worker activo.
CREATE TABLE IF NOT EXISTS public.user_watchlists (
    id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    asset          TEXT NOT NULL,
    interval       TEXT DEFAULT '15m',
    alerts_enabled BOOLEAN DEFAULT true,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, asset, interval)
);

CREATE INDEX IF NOT EXISTS idx_watchlists_user ON public.user_watchlists(user_id);

-- 3. SUBSCRIPTION TIERS
-- Controlan el acceso a features por usuario (free / pro / enterprise).
-- Se crea automáticamente con tier 'free' cuando el usuario se registra (ver trigger abajo).
CREATE TABLE IF NOT EXISTS public.subscription_tiers (
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    tier            TEXT DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    max_watchlist   INT DEFAULT 3,        -- free: 3 | pro: 20 | enterprise: 999
    telegram_alerts BOOLEAN DEFAULT false,
    api_access      BOOLEAN DEFAULT false,
    valid_until     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. TRADES PERSONALES
-- El usuario registra qué señales tomó y su resultado real.
-- Base del Portfolio Tracker y cálculo de P&L personal.
CREATE TABLE IF NOT EXISTS public.user_trades (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    signal_id     UUID REFERENCES public.signal_events(id) ON DELETE SET NULL,
    asset         TEXT NOT NULL,
    signal_type   TEXT CHECK (signal_type IN ('LONG', 'SHORT')),
    entry_price   FLOAT,
    exit_price    FLOAT,
    position_size FLOAT,
    result        TEXT CHECK (result IN ('WIN', 'LOSS', 'BREAKEVEN', 'OPEN')),
    pnl_usdt      FLOAT,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_trades_user   ON public.user_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_user_trades_signal ON public.user_trades(signal_id);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) — Multi-tenancy
-- Cada usuario ve SOLO sus propios datos.
-- ============================================================

-- signal_events: lectura pública para cualquier usuario autenticado
-- solo el service_role (engine Python) puede escribir
ALTER TABLE public.signal_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "signal_events_read_by_authenticated"
    ON public.signal_events FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "signal_events_write_by_service_role"
    ON public.signal_events FOR ALL
    TO service_role
    USING (true);

-- user_watchlists: el usuario gestiona solo su propia watchlist
ALTER TABLE public.user_watchlists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "watchlists_own_user_only"
    ON public.user_watchlists FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- subscription_tiers: el usuario solo lee su propio tier
-- el service_role lo actualiza al cambiar de plan
ALTER TABLE public.subscription_tiers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tiers_read_own_user"
    ON public.subscription_tiers FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "tiers_write_service_role"
    ON public.subscription_tiers FOR ALL
    TO service_role
    USING (true);

-- user_trades: el usuario gestiona solo sus propios trades
ALTER TABLE public.user_trades ENABLE ROW LEVEL SECURITY;

CREATE POLICY "trades_own_user_only"
    ON public.user_trades FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- TRIGGER: Auto-crear tier FREE al registrarse un usuario
-- Se ejecuta automáticamente en cada INSERT en auth.users
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.subscription_tiers (
        user_id,
        tier,
        max_watchlist,
        telegram_alerts,
        api_access
    )
    VALUES (
        NEW.id,
        'free',
        3,
        false,
        false
    )
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
