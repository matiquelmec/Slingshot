import React from 'react';
import { TrendingUp, TrendingDown, Crosshair } from 'lucide-react';
import { Signal, QuantDiagnostic, SessionData } from '../types/signal';

// =============== ESTRATEGIAS VISUALES DE SEÑALES ===============

export function getSignalLifecycle(sig: Signal, currentPrice: number | null, now: number): {
    status: 'PENDING' | 'EN_ZONA' | 'EXPIRADA' | 'INVALIDADA';
    label: string;
    reason: string;
    color: string;
    bgColor: string;
    countdown?: string;
} {
    const signalType = sig.signal_type || (sig.type?.includes('LONG') ? 'LONG' : 'SHORT');
    const expiryTs = sig.expiry_timestamp ? new Date(sig.expiry_timestamp).getTime() : null;

    // 0. BLOQUEADA POR AUDITORÍA (Risk Manager / Macro / HTF)
    if (sig.status === 'BLOCKED_BY_MACRO' || sig.status === 'BLOCKED_BY_FILTER' || sig.status === 'BLOCKED_BY_HTF') {
        let typeStr = 'FILTRO';
        let borderColor = 'border-red-500/10';
        let textColor = 'text-white/40';

        if (sig.status === 'BLOCKED_BY_MACRO') typeStr = 'MACRO';
        if (sig.status === 'BLOCKED_BY_HTF') {
            typeStr = 'HTF';
            borderColor = 'border-amber-500/30';
            textColor = 'text-amber-500/60';
        }

        return {
            status: 'INVALIDADA', 
            label: `⛔ BLOQUEADA (${typeStr} REJECT)`,
            reason: sig.rejection_reason || 'Rechazada por módulo de riesgo/confluencia.',
            color: textColor,
            bgColor: `bg-black/60 ${borderColor} opacity-70 grayscale-[50%]`,
        };
    }

    // 1. INVALIDADA por precio: el precio cerró más allá del SL
    if (currentPrice !== null && sig.stop_loss) {
        if (signalType === 'SHORT' && currentPrice > sig.stop_loss) {
            return {
                status: 'INVALIDADA',
                label: '✗ INVALIDADA',
                reason: `Precio actual $${currentPrice.toLocaleString()} superó el Stop Loss $${sig.stop_loss.toLocaleString()} — tesis bajista rota.`,
                color: 'text-neon-red',
                bgColor: 'bg-neon-red/5 border-neon-red/20 opacity-50',
            };
        }
        if (signalType === 'LONG' && currentPrice < sig.stop_loss) {
            return {
                status: 'INVALIDADA',
                label: '✗ INVALIDADA',
                reason: `Precio actual $${currentPrice.toLocaleString()} rompió Stop Loss $${sig.stop_loss.toLocaleString()} — tesis alcista rota.`,
                color: 'text-neon-red',
                bgColor: 'bg-neon-red/5 border-neon-red/20 opacity-50',
            };
        }
    }

    // 2. EXPIRADA por tiempo
    if (expiryTs && now > expiryTs) {
        const intervalMin = sig.interval_minutes || 15;
        const n = sig.expiry_candles || 3;
        return {
            status: 'EXPIRADA',
            label: '⏱ EXPIRADA',
            reason: `Pasaron ${n} velas de ${intervalMin}min (${n * intervalMin}min) sin que el precio llegara a la zona. Descartada.`,
            color: 'text-white/40',
            bgColor: 'bg-white/[0.02] border-white/5 opacity-60',
        };
    }

    // 3. EN ZONA: precio dentro del rango de entrada
    if (currentPrice !== null && sig.entry_zone_top != null && sig.entry_zone_bottom != null) {
        if (currentPrice >= sig.entry_zone_bottom && currentPrice <= sig.entry_zone_top) {
            return {
                status: 'EN_ZONA',
                label: '⚡ EN ZONA — ENTRY WINDOW',
                reason: `Precio actual $${currentPrice.toLocaleString()} dentro de zona ($${sig.entry_zone_bottom.toLocaleString()} – $${sig.entry_zone_top.toLocaleString()}). Confirmar volumen.`,
                color: 'text-neon-cyan',
                bgColor: 'bg-neon-cyan/5 border-neon-cyan/30',
            };
        }
    }

    // 4. PENDING: esperando llegada a zona
    const timeLeft = expiryTs ? Math.max(0, Math.floor((expiryTs - now) / 60000)) : null;
    const intervalMin = sig.interval_minutes || 15;
    const distToZone = currentPrice !== null && sig.entry_zone_top != null && sig.entry_zone_bottom != null
        ? signalType === 'LONG'
            ? sig.entry_zone_top - currentPrice
            : currentPrice - sig.entry_zone_bottom
        : null;

    const distText = distToZone != null
        ? `Precio a $${Math.abs(distToZone).toLocaleString(undefined, { maximumFractionDigits: 0 })} de la zona.`
        : '';

    return {
        status: 'PENDING',
        label: '⏳ PENDIENTE',
        reason: `Esperando zona ($${sig.entry_zone_bottom?.toLocaleString()} – $${sig.entry_zone_top?.toLocaleString()}). ${distText}`,
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-400/5 border-yellow-400/20',
        countdown: timeLeft != null ? `Expira en ~${timeLeft}min (${Math.ceil(timeLeft / intervalMin)} velas)` : undefined,
    };
}

// Función pura de mapeo de estilo y color
export function getSignalStyle(type: string) {
    if (type.includes('LONG')) {
        return {
            color: 'text-neon-green',
            bg: 'bg-neon-green/10',
            border: 'border-neon-green/30',
            shadow: 'drop-shadow-[0_0_8px_rgba(0,255,65,0.8)]',
        };
    } else if (type.includes('SHORT')) {
        return {
            color: 'text-neon-red',
            bg: 'bg-neon-red/10',
            border: 'border-neon-red/30',
            shadow: 'drop-shadow-[0_0_8px_rgba(255,0,60,0.8)]',
        };
    }
    return {
        color: 'text-white/60',
        bg: 'bg-white/5',
        border: 'border-white/10',
        shadow: '',
    };
}

// ============== LÓGICA DE CONDICIONES MET/WAITING ==================

export interface Condition {
    label: string;
    status: 'MET' | 'PARTIAL' | 'WAITING' | 'WARNING';
    currentValue: string;
    meaning: string;
}

export function buildConditions(
    regime: string,
    d: QuantDiagnostic | null,
    price: number | null,
    support: number | null,
    resistance: number | null,
    sessionData: SessionData | null = null
): Condition[] {

    // Extraemos valores seguros (fallbacks a "0" o neutrales)
    const diag = d || {
        rsi: 50, macd_line: 0, macd_signal: 0, macd_bullish_cross: false,
        bbwp: 50, squeeze_active: false, volume: 0, rsi_oversold: false,
        rsi_overbought: false, bullish_divergence: false, bearish_divergence: false,
        volume_mean: 0
    };

    const {
        rsi, macd_line, macd_signal, macd_bullish_cross, bbwp, squeeze_active,
        volume, rsi_oversold, rsi_overbought, bullish_divergence, bearish_divergence, volume_mean = 0
    } = diag;


    // RSI helper
    const rsiDesc = () => {
        if (rsi < 30) return { level: 'Sobreventa extrema', note: 'Zona de pánico minorista. Institucionales compran aquí.' };
        if (rsi < 40) return { level: 'Sobreventa moderada', note: 'Presión vendedora alta. Zona de interés.' };
        if (rsi < 50) return { level: 'Zona neutral bajista', note: 'Momentum negativo.' };
        if (rsi < 60) return { level: 'Zona neutral alcista', note: 'Momentum positivo.' };
        if (rsi < 70) return { level: 'Sobrecompra moderada', note: 'Atención a agotamiento.' };
        return { level: 'Sobrecompra extrema', note: 'Zona de euforia minorista. Vendedores institucionales activos.' };
    };

    // MACD helper
    const macdDesc = () => {
        const diff = (macd_line - macd_signal).toFixed(2);
        if (macd_bullish_cross) return `Línea MACD (${macd_line.toFixed(2)}) > Señal (${macd_signal.toFixed(2)}). Alcista validado.`;
        if (macd_line > macd_signal) return `Línea MACD (${macd_line.toFixed(2)}) conserva ventaja sobre Señal.`;
        return `Línea MACD (${macd_line.toFixed(2)}) < Señal (${macd_signal.toFixed(2)}). Déficit: ${diff}.`;
    };

    // Rango helper (Fallback al profile de Sesión)
    const rangePos = () => {
        let s = support;
        let r = resistance;
        if (!s || !r) {
            s = sessionData?.pdl ?? sessionData?.sessions?.london?.low ?? null;
            r = sessionData?.pdh ?? sessionData?.sessions?.london?.high ?? null;
        }
        if (!price || !s || !r) return null;
        const range = r - s;
        const pos = price - s;
        const pct = range > 0 ? ((pos / range) * 100).toFixed(0) : '?';
        const isFallback = (!support || !resistance);
        return { pct, s, r, range, label: isFallback ? 'Nivel Diario/Sesión' : 'Soporte/Resistencia' };
    };

    switch (regime.toUpperCase()) {

        case 'ACCUMULATION': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Objetivo: RSI en sobreventa (< 35)',
                    status: rsi_oversold ? 'MET' : rsi < 45 ? 'PARTIAL' : 'WAITING',
                    currentValue: `Nivel actual: RSI ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: rsi_oversold
                        ? `✅ ${rs.note} Búsqueda de LONG en el próximo Order Block.`
                        : `Aún no llega a 35 (actualmente ${rsi.toFixed(1)}). ${rs.note}`,
                },
                {
                    label: 'Buscando: OB alcista en soporte',
                    status: 'WAITING',
                    currentValue: support ? `Soporte: $${support.toFixed(2)}` : 'Buscando zona de interés...',
                    meaning: 'Order Block: Zona donde quedó liquidez e intencionalidad pendiente.',
                },
                {
                    label: 'Verificando: Momentum MACD alcista',
                    status: macd_bullish_cross ? 'MET' : macd_line > macd_signal ? 'PARTIAL' : 'WAITING',
                    currentValue: macd_bullish_cross ? 'Cruce alcista CONFIRMADO' : `MACD: ${macd_line.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: 'Monitoreo: Compresión BB Squeeze',
                    status: squeeze_active ? 'MET' : bbwp < 30 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp.toFixed(1)}% — ${squeeze_active ? '🔥 COMPRIMIDO' : 'Expandido'}`,
                    meaning: squeeze_active ? 'Compresión extrema. Explosión inminente.' : 'Baja volatilidad. Esperando carga.',
                },
                {
                    label: bullish_divergence ? '🔥 Alerta: Divergencia Alcista Detectada' : 'Buscando: Divergencias Cuantitativas',
                    status: bullish_divergence ? 'MET' : 'WAITING',
                    currentValue: bullish_divergence ? 'DIVERGENCIA ALCISTA (Price vs RSI)' : 'Sin anomalías alcistas.',
                    meaning: bullish_divergence ? 'El precio hizo un mínimo más bajo, pero el momentum (RSI) subió.' : 'Momentum sincrónico.',
                },
            ];
        }

        case 'MARKUP': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Objetivo: Retroceso (Pullback) y Confluencia',
                    status: 'WAITING',
                    currentValue: support ? `Soportes EMA: $${support.toFixed(2)}` : 'Esperando corrección...',
                    meaning: 'En tendencia, compramos retrocesos hacia la EMA 50 o el Fibo 0.5 - 0.618.',
                },
                {
                    label: 'Verificando: Espacio libre en RSI (< 60)',
                    status: rsi_overbought ? 'WARNING' : rsi < 60 ? 'MET' : 'PARTIAL',
                    currentValue: `Nivel actual: RSI ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: rsi_overbought ? '⚠️ Peligro de Sobrecompra. Entrar ahora es altísimo riesgo.' : '✅ El RSI tiene margen para seguir subiendo.',
                },
                {
                    label: 'Confirmación: Momentum MACD alcista',
                    status: macd_line > macd_signal ? 'MET' : 'WAITING',
                    currentValue: `MACD Line: ${macd_line.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: bearish_divergence ? '⚠️ Alerta: Divergencia Bajista Detectada' : 'Monitoreo: Riesgo de Divergencias',
                    status: bearish_divergence ? 'WARNING' : 'WAITING',
                    currentValue: bearish_divergence ? 'DIVERGENCIA BAJISTA (Price vs RSI)' : 'Sin anomalías estructurales.',
                    meaning: bearish_divergence ? 'Precio con máximo más alto, pero momentum (RSI) decayendo.' : 'Subida saludable soportada linealmente.',
                },
            ];
        }

        case 'DISTRIBUTION': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Objetivo: RSI en sobrecompra (> 70)',
                    status: rsi_overbought ? 'MET' : rsi > 60 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RSI: ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: rsi_overbought ? '✅ Euforia detectada. Institucionales listos para vender.' : 'Esperando agotamiento alcista.',
                },
                {
                    label: 'Buscando: Barrida de liquidez institucional',
                    status: 'WAITING',
                    currentValue: resistance ? `Umbral a romper: $${resistance.toFixed(2)}` : 'Mapeando techo...',
                    meaning: 'Buscamos que el precio supere un máximo previo temporalmente para atrapar liquidez (Sweep).',
                },
                {
                    label: bearish_divergence ? '⚠️ Alerta: Divergencia Bajista (Oculta)' : 'Monitoreo: Debilidad Estructural',
                    status: bearish_divergence ? 'MET' : 'WAITING',
                    currentValue: bearish_divergence ? 'DIVERGENCIA BAJISTA DETECTADA' : 'Subida lineal en curso.',
                    meaning: bearish_divergence ? 'El rally carece de fuerza de compra real. Manos fuertes vendiendo ocultamente.' : 'Distribución algorítmica sin debilidad oculta visible todavía.',
                },
            ];
        }

        case 'MARKDOWN': {
            const volExtreme = volume > (volume_mean * 2.5);
            return [
                {
                    label: 'Objetivo: Pullback Bajista a la EMA 50',
                    status: 'WAITING',
                    currentValue: resistance ? `Resistencia EMA: $${resistance.toFixed(2)}` : 'Esperando rebote temporal...',
                    meaning: 'En tendencia bajista, se busca operar en corto (SHORT) en los rebotes a la EMA 50.',
                },
                {
                    label: 'Confirmando: MACD negativo',
                    status: macd_line < macd_signal ? 'MET' : 'WAITING',
                    currentValue: `MACD Line: ${macd_line.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: 'Precaución: ¿Inminente Clímax de Ventas?',
                    status: (rsi_oversold && volExtreme) ? 'WARNING' : 'WAITING',
                    currentValue: `Vol: ${volume.toFixed(0)} | RSI: ${rsi.toFixed(1)}`,
                    meaning: (rsi_oversold && volExtreme)
                        ? '⚠️ CLÍMAX DETECTADO. Probable cierre masivo de cortos por capitulación minorista.'
                        : 'Sin señales de clímax.',
                },
                {
                    label: bullish_divergence ? '🔥 Alerta: Divergencia Alcista en Caída' : 'Monitoreo: Riesgo de Reversión',
                    status: bullish_divergence ? 'WARNING' : 'WAITING',
                    currentValue: bullish_divergence ? 'DIVERGENCIA ALCISTA DETECTADA' : 'Caída fluida normal.',
                    meaning: bullish_divergence ? 'La presión vendedora se secó internamente. El RSI ya dio la vuelta.' : 'Tendencia confirmada.',
                },
            ];
        }

        case 'RANGING': {
            const rp = rangePos();
            const priceOut = rp && (parseInt(rp.pct) > 105 || parseInt(rp.pct) < -5);
            const lowVol = volume < (volume_mean * 1.2);
            return [
                {
                    label: 'Calculando: Ubicación geométrica en el lateral',
                    status: rp ? 'PARTIAL' : 'WAITING',
                    currentValue: rp
                        ? `${rp.pct}% (entre $${rp.s?.toFixed(2)} y $${rp.r?.toFixed(2)})`
                        : 'Mapeando rangos vigentes...',
                    meaning: rp
                        ? `Posición actual: ${rp.pct}% del bloque. ${parseInt(rp.pct) < 30 ? 'Zona Soporte (LONG)' : parseInt(rp.pct) > 70 ? 'Zona Techo (SHORT)' : 'Zona Media (Riesgo)'}`
                        : 'Buscando las barreras del canal lateral.',
                },
                {
                    label: 'Verificando: Ruptura del rango y Volumen',
                    status: (priceOut && lowVol) ? 'WARNING' : priceOut ? 'MET' : 'WAITING',
                    currentValue: priceOut ? 'PRECIO FUERA DEL RANGO' : 'PRECIO DENTRO DEL RANGO',
                    meaning: (priceOut && lowVol)
                        ? '⚠️ ALERTA DE TRAMPA (Fakeout). Ruptura con volumen anémico, probablemente diseñada para casar stops.'
                        : priceOut
                            ? 'Ruptura con intención detectada. Verificando confirmación volumétrica.'
                            : 'Navegando dentro del canal lateral.',
                },
                {
                    label: 'Monitoreo: Compresión BB Squeeze',
                    status: squeeze_active ? 'MET' : bbwp < 25 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp.toFixed(1)}%`,
                    meaning: squeeze_active
                        ? '🔥 SQUEEZE CONFIRMADO. Bandas totalmente comprimidas. Explosión direccional muy próxima.'
                        : bbwp < 25
                            ? 'Baja Volatilidad: El "resorte" se comprime.'
                            : 'Volatilidad Normal en el bloque.',
                },
                {
                    label: 'Buscando: Anomalías o Divergencias Ocultas',
                    status: bullish_divergence ? 'MET' : bearish_divergence ? 'WARNING' : 'WAITING',
                    currentValue: bullish_divergence ? 'RSI ALCISTA DETECTADO 🔥' : bearish_divergence ? 'RSI BAJISTA DETECTADO ⚠️' : 'Sin desequilibrios.',
                    meaning: bullish_divergence ? 'Posible "Spring" institucional (manipulación a la baja antes de volar).' : bearish_divergence ? 'Posible "Upthrust" inminente (trampa alcista).' : 'Métricas balanceadas en el rango.',
                },
            ];
        }

        case 'CHOPPY': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Estado: Standby Táctico por Indecisión',
                    status: 'WARNING',
                    currentValue: 'Sincronización de Medias: FALLIDA',
                    meaning: 'El mercado está en un estado de "ruido". Las medias móviles se cruzan sin tendencia. Operar aquí es jugar al azar institucional.',
                },
                {
                    label: 'Monitoreo: Volatilidad Extremadamente Sucia',
                    status: bbwp > 80 ? 'WARNING' : 'WAITING',
                    currentValue: `BBWP: ${bbwp.toFixed(1)}% | Momentum: FRAGMENTADO`,
                    meaning: bbwp > 80 ? 'Volatilidad expandida pero sin dirección. Riesgo de "Whipsaw" (barrida de stops en ambos lados).' : 'Esperando que la volatilidad se asiente en un rango operable.',
                },
                {
                    label: 'Filtro: RSI en Tierra de Nadie',
                    status: 'PARTIAL',
                    currentValue: `RSI actual: ${rsi.toFixed(1)}`,
                    meaning: 'El RSI oscila cerca de 50. No hay ventaja estadística ni para compradores ni para vendedores.',
                },
                {
                    label: 'Plan de Acción: Esperar Expansión con Volumen',
                    status: 'WAITING',
                    currentValue: `Volumen actual: ${volume.toFixed(0)}`,
                    meaning: 'Necesitamos ver una vela de rango amplio (Marubozu) acompañada de volumen institucional (2x media) para confirmar el inicio de un nuevo régimen.',
                },
            ];
        }

        default:
            const rs = rsiDesc();
            return [
                {
                    label: 'Análisis Preliminar: Calibrando Régimen',
                    status: 'WAITING',
                    currentValue: 'Sincronizando Wyckoff...',
                    meaning: 'El motor requiere un historial de 200 velas (15m) para confirmar el régimen institucional con seguridad estadística. Realizando análisis de momentum preventivo.',
                },
                {
                    label: 'Monitor de Momentum (RSI)',
                    status: rsi < 30 || rsi > 70 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RSI actual: ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: rs.note,
                },
                {
                    label: 'Estado de Volatilidad (BBWP)',
                    status: squeeze_active ? 'MET' : 'WAITING',
                    currentValue: `BBWP: ${bbwp.toFixed(1)}%`,
                    meaning: squeeze_active ? 'Compresión detectada. El mercado prepara expansión.' : 'Volatilidad en fase de carga.',
                }
            ];
    }
}
