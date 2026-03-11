-- ============================================================
-- SLINGSHOT v2.0 — Migration 002: Radar & Signal Audit
-- Fecha: 2026-03-09
-- Responsabilidad: Tabla de estados en tiempo real y nuevos estados de auditoría.
-- ============================================================

-- 1. Crear tabla de estados para el Radar (Watchlist VIP en tiempo real)
CREATE TABLE IF NOT EXISTS public.market_states (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    asset         TEXT NOT NULL UNIQUE,
    price         NUMERIC NOT NULL,
    change_24h    NUMERIC DEFAULT 1.2,
    regime        TEXT NOT NULL DEFAULT 'ANALIZANDO',
    macro_bias    TEXT NOT NULL DEFAULT 'NEUTRAL',
    last_updated  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Habilitar Realtime para actualizaciones instantáneas en el Dashboard
BEGIN;
  -- Intentar añadir a la publicación si existe, si no, crear publicación (fallback seguro)
  DO $$ 
  BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
      ALTER PUBLICATION supabase_realtime ADD TABLE public.market_states;
    END IF;
  END $$;
COMMIT;

-- 3. Row Level Security (RLS)
ALTER TABLE public.market_states ENABLE ROW LEVEL SECURITY;

-- Lectura permitida para cualquier usuario logueado
CREATE POLICY "market_states_read_all" 
    ON public.market_states FOR SELECT 
    TO authenticated 
    USING (true);

-- Escritura solo para el Service Role (Backend Orchestrator)
CREATE POLICY "market_states_write_service_role" 
    ON public.market_states FOR ALL 
    TO service_role 
    USING (true);

-- 4. Actualización de Auditoría de Señales
-- Añadimos 'BLOCKED_BY_MACRO' a los estados permitidos para mayor transparencia.
-- Nota: Intentamos borrar la constraint previa si existe.
DO $$ 
BEGIN
    -- Postgres suele nombrar las constraints de columna como 'tabla_columna_check'
    ALTER TABLE public.signal_events DROP CONSTRAINT IF EXISTS signal_events_status_check;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

ALTER TABLE public.signal_events 
ADD CONSTRAINT signal_events_status_check 
CHECK (status IN ('ACTIVE', 'HIT_TP', 'HIT_SL', 'EXPIRED', 'BLOCKED_BY_MACRO'));
