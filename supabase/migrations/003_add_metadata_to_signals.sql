-- ============================================================
-- SLINGSHOT v2.0 — Migration 003: Add Metadata to signal_events
-- Fecha: 2026-03-09
-- ============================================================

ALTER TABLE public.signal_events 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Comentario para documentación
COMMENT ON COLUMN public.signal_events.metadata IS 'Datos extra de la señal (reasoning, ghost_bias, fear_greed, etc.)';
