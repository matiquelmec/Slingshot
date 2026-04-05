import React from 'react';
import { TrendingUp, TrendingDown, Crosshair } from 'lucide-react';
import { Signal, QuantDiagnostic, SessionData, TacticalDecision } from '../types/signal';

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
    if (sig.status === 'BLOCKED_BY_MACRO' || sig.status === 'BLOCKED_BY_FILTER' || sig.status === 'BLOCKED_BY_HTF' || sig.status === 'BLOCKED_BY_CONFIDENCE' || sig.status === 'BLOCKED_BY_VOLATILITY' || sig.status === 'STAND_BY' || sig.status === 'BLOCKED_EXPIRED') {
        const typeStr = sig.status === 'BLOCKED_BY_MACRO' ? 'MACRO' : 
                        sig.status === 'BLOCKED_BY_HTF' ? 'HTF' : 
                        sig.status === 'BLOCKED_BY_CONFIDENCE' ? 'Score' :
                        sig.status === 'BLOCKED_BY_VOLATILITY' ? 'Volatilidad' :
                        sig.status === 'STAND_BY' ? 'Conflicto IA/SMC' :
                        sig.status === 'BLOCKED_EXPIRED' ? 'Expirada' : 'Filtro';
        
        const borderColor = sig.status === 'BLOCKED_BY_HTF' ? 'border-amber-500/30' : sig.status === 'STAND_BY' ? 'border-cyan-500/30' : 'border-red-500/10';
        const textColor = sig.status === 'BLOCKED_BY_HTF' ? 'text-amber-500/60' : sig.status === 'STAND_BY' ? 'text-cyan-400/60' : 'text-white/40';

        // Detalle extendido: Combinar POR QUÉ es señal + POR QUÉ se rechaza
        // Priorizar rejection_reason que viene del broadcast estandarizado
        const whySignal = sig.confluence?.reasoning || 'Criterio técnico base cumplido.';
        const rejectionDetail = sig.rejection_reason || (sig as any).blocked_reason || 
                               (sig.status === 'BLOCKED_BY_CONFIDENCE' ? 'No alcanzó el umbral de excelencia (75%)' : 'Rechazada por módulo de riesgo.');

        return {
            status: 'INVALIDADA', 
            label: `⛔ BLOQUEADA (${typeStr} REJECT)`,
            reason: `CAUSA RECHAZO: ${rejectionDetail}\n\nPOR QUÉ ES SEÑAL: ${whySignal}`,
            color: textColor,
            bgColor: `bg-black/60 ${borderColor} opacity-95 shadow-inner`,
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

    const zoneText = sig.entry_zone_bottom != null && sig.entry_zone_top != null
        ? `Esperando zona ($${sig.entry_zone_bottom.toLocaleString()} – $${sig.entry_zone_top.toLocaleString()}). ${distText}`
        : `Esperando retorno al nivel de entrada ($${sig.price?.toLocaleString(undefined, { minimumFractionDigits: 2 }) ?? 'N/A'}). ${distText}`;

    return {
        status: 'PENDING',
        label: '⏳ PENDIENTE',
        reason: zoneText,
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
    sessionData: SessionData | null = null,
    fibonacci: TacticalDecision['fibonacci'] | null = null
): Condition[] {

    // SMC Data (Order Blocks & FVGs)
    const smc = (d as any)?.smc || { order_blocks: { bullish: [], bearish: [] }, fvgs: { bullish: [], bearish: [] } };
    const bullOBs = smc.order_blocks?.bullish?.length || 0;
    const bearOBs = smc.order_blocks?.bearish?.length || 0;
    const activeFVGs = (smc.fvgs?.bullish?.length || 0) + (smc.fvgs?.bearish?.length || 0);

    // RVOL (Volume Institucional v5.2) - SSOT
    const rvol = d?.rvol || 1.0;
    
    // Macro Bias & HTF
    const htf = (d as any)?.htf_bias || { direction: 'NEUTRAL', strength: 0 };
    const macro = (d as any)?.macro_bias || 'NEUTRAL';
    const fib = fibonacci;

    switch (regime) {
        case 'ACCUMULATION':
        case 'MARKUP': {
            const isBullishBias = htf.direction === 'BULLISH' || macro === 'LONG_ONLY';
            const isKillZone = sessionData?.is_killzone;
            
            return [
                {
                    label: 'Sesgo HTF: Alineación Alcista',
                    status: isBullishBias ? 'MET' : 'WAITING',
                    currentValue: `Bias: ${htf.direction} | Macro: ${macro}`,
                    meaning: isBullishBias ? '✅ Flujo de capital institucional a favor de compras.' : '⚠️ No hay alineación de temporalidades mayores. Riesgo alto.',
                },
                {
                    label: 'Sesión: Ventana de Volatilidad (KillZone)',
                    status: isKillZone ? 'MET' : 'PARTIAL',
                    currentValue: `Estado: ${isKillZone ? 'KILLZONE ACTIVA' : 'FUERA DE HORARIO'}`,
                    meaning: isKillZone ? '✅ Manipulación y expansión institucional en curso.' : 'Volumen bajo. Probable mercado lateral o lento.',
                },
                {
                    label: 'Liquidez: Barrida de Mínimos (Sweeps)',
                    status: (sessionData?.pdl_swept) ? 'MET' : 'WAITING',
                    currentValue: `PDL Swept: ${sessionData?.pdl_swept ? 'SÍ' : 'NO'}`,
                    meaning: sessionData?.pdl_swept ? '✅ Los bancos ya cazaron los stop-loss del piso previo. Camino libre al alza.' : 'Buscando barrida de Asian Low o PDL.',
                },
                {
                    label: 'Zona de Valor: Order Blocks (OBs)',
                    status: bullOBs > 0 ? 'MET' : 'WAITING',
                    currentValue: `OBs Alcistas: ${bullOBs} detectados`,
                    meaning: bullOBs > 0 ? '✅ El precio descansa sobre demanda institucional confirmada.' : 'Esperando formación de bloque de órdenes.',
                },
                {
                    label: 'Volumen: Esfuerzo Institucional (RVOL)',
                    status: rvol >= 1.5 ? 'MET' : rvol >= 1.2 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RVOL: ${rvol.toFixed(2)}x`,
                    meaning: rvol >= 1.5 ? '✅ Participación institucional confirmada por volumen.' : 'Esperando intención volumétrica real.',
                },
                {
                    label: 'Zona de Valor: Fibonacci Dinámico (v5.4)',
                    status: (fib && price && price < (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5)) ? 'MET' : 'WARNING',
                    currentValue: fib && price ? (price < (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5) ? 'DISCOUNT (COMPRA)' : 'PREMIUM (CARO)') : (!fib ? 'CALCULANDO' : 'FIB_WAIT'),
                    meaning: (fib && price && price < (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5)) 
                        ? '✅ Precio en zona de descuento institucional (Fair Value). Óptimo para Longs.' 
                        : '⚠️ Precio en zona Premium. Riesgo de retroceso antes de expansión.',
                },
            ];
        }
 
        case 'DISTRIBUTION':
        case 'MARKDOWN': {
            const isBearishBias = htf.direction === 'BEARISH' || macro === 'SHORT_ONLY';
            const isKillZone = sessionData?.is_killzone;
 
            return [
                {
                    label: 'Sesgo HTF: Alineación Bajista',
                    status: isBearishBias ? 'MET' : 'WAITING',
                    currentValue: `Bias: ${htf.direction} | Macro: ${macro}`,
                    meaning: isBearishBias ? '✅ Flujo de capital institucional a favor de ventas.' : '⚠️ Temporalidades mayores en contra o neutrales.',
                },
                {
                    label: 'Sesión: Ventana de Volatilidad (KillZone)',
                    status: isKillZone ? 'MET' : 'PARTIAL',
                    currentValue: `Estado: ${isKillZone ? 'KILLZONE ACTIVA' : 'FUERA DE HORARIO'}`,
                    meaning: isKillZone ? '✅ Los algoritmos de alta frecuencia están activos.' : 'Mercado en modo "Slow Walk". Poca intención bancaria.',
                },
                {
                    label: 'Liquidez: Barrida de Máximos (Sweeps)',
                    status: (sessionData?.pdh_swept) ? 'MET' : 'WAITING',
                    currentValue: `PDH Swept: ${sessionData?.pdh_swept ? 'SÍ' : 'NO'}`,
                    meaning: sessionData?.pdh_swept ? '✅ Manipulación a la alza completada. Atrapando compradores finales.' : 'Buscando barrida de Asian High o PDH.',
                },
                {
                    label: 'Zona de Valor: Order Blocks (OBs)',
                    status: bearOBs > 0 ? 'MET' : 'WAITING',
                    currentValue: `OBs Bajistas: ${bearOBs} detectados`,
                    meaning: bearOBs > 0 ? '✅ Presencia de oferta institucional en este nivel.' : 'Esperando formación de bloque de oferta.',
                },
                {
                    label: 'Esfuerzo: Confirmación de Volumen',
                    status: rvol >= 1.5 ? 'MET' : 'WAITING',
                    currentValue: `RVOL: ${rvol.toFixed(2)}x`,
                    meaning: rvol >= 1.5 ? '✅ Anomalía de volumen confirma la distribución.' : 'Volumen minorista (bajo). No hay confirmación institucional.',
                },
                {
                    label: 'Zona de Valor: Fibonacci Dinámico (v5.4)',
                    status: (fib && price && price > (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5)) ? 'MET' : 'WARNING',
                    currentValue: fib && price ? (price > (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5) ? 'PREMIUM (VENTA)' : 'DISCOUNT (BARATO)') : (!fib ? 'CALCULANDO' : 'FIB_WAIT'),
                    meaning: (fib && price && price > (fib.swing_low + (fib.swing_high - fib.swing_low) * 0.5)) 
                        ? '✅ Precio en zona Premium. Óptimo para capturar la distribución Institucional.' 
                        : '⚠️ Precio en zona de descuento. Peligro de atrapar picos ante demanda latente.',
                },
            ];
        }
 
        case 'RANGING':
        case 'CHOPPY':
        default: {
            return [
                {
                    label: 'Estado: Standby por Filtro Dinámico',
                    status: 'WARNING',
                    currentValue: `Régimen: ${regime}`,
                    meaning: 'Acción de precio sucia o consolidación lateral. El motor bloquea señales para prevenir "Whipsaws".',
                },
                {
                    label: 'Monitor de Liquidez: Zonas Pendientes',
                    status: activeFVGs > 0 ? 'PARTIAL' : 'WAITING',
                    currentValue: `FVGs Pendientes: ${activeFVGs}`,
                    meaning: 'El precio suele buscar llenar estos vacíos antes de definir una nueva tendencia.',
                },
                {
                    label: 'Estructura HTF (Superior)',
                    status: htf.direction !== 'NEUTRAL' ? 'MET' : 'WAITING',
                    currentValue: `Bias 1H: ${htf.direction}`,
                    meaning: htf.direction === 'NEUTRAL' ? 'Institucionales sin dirección clara. Evitar operar.' : 'Esperando que el marco temporal menor se alinee.',
                },
            ];
        }
    }
}
