'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Target, Clock, ArrowUpCircle, ArrowDownCircle, Pause, Layers, Eye } from 'lucide-react';

// ─── Tipos ─────────────────────────────────────────────────────────────────
interface Condition {
    label: string;
    status: 'MET' | 'PARTIAL' | 'WAITING' | 'WARNING';
    currentValue: string;
    meaning: string;
}

interface MarketContextPanelProps {
    regime: string | null;
    activeStrategy: string | null;
    diagnostic: Record<string, any> | null;
    currentPrice?: number | null;
    nearestSupport?: number | null;
    nearestResistance?: number | null;
    sessionData?: any | null;
}

// ─── Config base por régimen ────────────────────────────────────────────────
const REGIME_META: Record<string, { color: string; border: string; icon: React.ReactNode; label: string; explanation: string; accent: string }> = {
    ACCUMULATION: {
        color: 'text-neon-cyan', border: 'border-neon-cyan/30', accent: 'bg-neon-cyan',
        icon: <Layers size={14} className="text-neon-cyan" />,
        label: 'ACUMULACIÓN',
        explanation: 'Evidencia de absorción institucional a precios bajos. El precio oscila en un rango estrecho mientras se agota la oferta flotante. Hipótesis directriz: Próxima fase es MARKUP (Ruptura Alcista).',
    },
    MARKUP: {
        color: 'text-neon-green', border: 'border-neon-green/30', accent: 'bg-neon-green',
        icon: <ArrowUpCircle size={14} className="text-neon-green" />,
        label: 'TENDENCIA ALCISTA (MARKUP)',
        explanation: 'Estructura de precios ascendente confirmada (Higher Highs, Higher Lows). Dominio de la demanda institucional. Hipótesis directriz: Comprar (LONG) en retrocesos a las zonas de valor.',
    },
    DISTRIBUTION: {
        color: 'text-red-400', border: 'border-red-400/30', accent: 'bg-red-400',
        icon: <Layers size={14} className="text-red-400" />,
        label: 'DISTRIBUCIÓN',
        explanation: 'Evidencia de descarga institucional gradual a precios altos. Cierres débiles ocultos tras aparentes impulsos alcistas. Hipótesis directriz: Próxima fase es MARKDOWN (Ruptura Bajista).',
    },
    MARKDOWN: {
        color: 'text-neon-red', border: 'border-neon-red/30', accent: 'bg-neon-red',
        icon: <ArrowDownCircle size={14} className="text-neon-red" />,
        label: 'TENDENCIA BAJISTA (MARKDOWN)',
        explanation: 'Estructura de precios descendente confirmada (Lower Lows, Lower Highs). Dominio absoluto de la presión vendedora. Hipótesis directriz: Vender (SHORT) en rebotes falsos.',
    },
    RANGING: {
        color: 'text-yellow-400', border: 'border-yellow-400/30', accent: 'bg-yellow-400',
        icon: <Pause size={14} className="text-yellow-400" />,
        label: 'RANGO — STANDBY',
        explanation: 'Equilibrio temporal entre oferta y demanda. El precio oscila entre un soporte y resistencia bien definidos sin lograr una ruptura direccional. Hipótesis directriz: Esperar expansión de volumen o cazar barridas en los extremos.',
    },
    UNKNOWN: {
        color: 'text-white/40', border: 'border-white/10', accent: 'bg-white/20',
        icon: <Eye size={14} className="text-white/40" />,
        label: 'CALIBRANDO RED NEURAL...',
        explanation: 'Procesando el histórico espacial para determinar el Régimen de Wyckoff actual. El motor requiere al menos 50-200 velas previas estabilizadas antes de emitir un dictamen algorítmico seguro.',
    },
};

// ─── Generadores dinámicos de condiciones por régimen ────────────────────────
function buildConditions(
    regime: string,
    d: Record<string, any>,
    price: number | null,
    support: number | null,
    resistance: number | null,
    sessionData: any | null = null
): Condition[] {

    const rsi = d?.rsi ?? 50;
    const macdLine = d?.macd_line ?? 0;
    const macdSig = d?.macd_signal ?? 0;
    const macdCross = d?.macd_bullish_cross ?? false;
    const bbwp = d?.bbwp ?? 50;
    const squeeze = d?.squeeze_active ?? false;
    const vol = d?.volume ?? 0;
    const oversold = d?.rsi_oversold ?? false;
    const overbought = d?.rsi_overbought ?? false;
    const bullDiv = d?.bullish_divergence ?? false;
    const bearDiv = d?.bearish_divergence ?? false;

    // RSI helper
    const rsiDesc = () => {
        if (rsi < 30) return { level: 'Sobreventa extrema', note: 'Zona de pánico minorista. Los institucionales típicamente compran aquí.' };
        if (rsi < 40) return { level: 'Sobreventa moderada', note: 'Presión vendedora alta pero cediendo. Zona de interés para compradores.' };
        if (rsi < 50) return { level: 'Zona neutral bajista', note: 'Sin extremo. Momentum ligeramente negativo.' };
        if (rsi < 60) return { level: 'Zona neutral alcista', note: 'Sin extremo. Momentum ligeramente positivo.' };
        if (rsi < 70) return { level: 'Sobrecompra moderada', note: 'Presión compradora alta. Atención a agotamiento.' };
        return { level: 'Sobrecompra extrema', note: 'Zona de euforia minorista. Los institucionales suelen vender aquí.' };
    };

    // Volumen helper
    const volDesc = () => {
        if (vol > 0) return `${vol.toFixed(2)} unidades en la vela actual`;
        return 'No disponible en el tick actual';
    };

    // MACD helper
    const macdDesc = () => {
        const diff = (macdLine - macdSig).toFixed(2);
        if (macdCross) return `Línea MACD (${macdLine?.toFixed(2)}) > Señal (${macdSig?.toFixed(2)}). Momentum alcista validado.`;
        if (macdLine > macdSig) return `Línea MACD (${macdLine?.toFixed(2)}) conserva ventaja sobre Señal (${macdSig?.toFixed(2)}).`;
        return `Línea MACD (${macdLine?.toFixed(2)}) < Señal (${macdSig?.toFixed(2)}). Déficit: ${diff}.`;
    };

    // Rango helper con FALLBACK a Sesiones
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
                    status: oversold ? 'MET' : rsi < 45 ? 'PARTIAL' : 'WAITING',
                    currentValue: `Nivel actual: RSI ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: oversold
                        ? `✅ ${rs.note} El motor buscará entrada LONG en el próximo Order Block.`
                        : `Aún no llega a 35 (actualmente ${rsi.toFixed(1)}). ${rs.note}`,
                },
                {
                    label: 'Buscando: OB alcista en soporte',
                    status: 'WAITING',
                    currentValue: support ? `Soporte: $${support.toFixed(2)}` : 'Buscando zona de interés...',
                    meaning: 'Un Order Block alcista es donde los bancos dejaron órdenes de compra pendientes.',
                },
                {
                    label: 'Verificando: Momentum MACD alcista',
                    status: macdCross ? 'MET' : macdLine > macdSig ? 'PARTIAL' : 'WAITING',
                    currentValue: macdCross ? 'Cruce alcista CONFIRMADO' : `MACD: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: 'Monitoreo: Compresión BB Squeeze',
                    status: squeeze ? 'MET' : bbwp < 30 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp?.toFixed(1)}% — ${squeeze ? '🔥 COMPRIMIDO' : 'Expandido'}`,
                    meaning: squeeze ? 'Compresión extrema. Explosión inminente.' : 'Baja volatilidad. Esperando carga de energía.',
                },
                {
                    label: bullDiv ? '🔥 Alerta: Divergencia Alcista Detectada' : 'Buscando: Divergencias Cuantitativas',
                    status: bullDiv ? 'MET' : 'WAITING',
                    currentValue: bullDiv ? 'DIVERGENCIA ALCISTA (Price vs RSI)' : 'Ninguna divergencia alcista por ahora.',
                    meaning: bullDiv ? 'El precio hizo un mínimo más bajo, pero el momentum institucional (RSI) subió. Fuerte señal de reversión inminente.' : 'El momentum acompaña al precio linealmente.',
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
                    meaning: 'En tendencia, buscamos comprar los retrocesos al nivel de la EMA 50 o el Fibo 0.5 - 0.618.',
                },
                {
                    label: 'Verificando: Espacio libre en RSI (< 60)',
                    status: overbought ? 'WARNING' : rsi < 60 ? 'MET' : 'PARTIAL',
                    currentValue: `Nivel actual: RSI ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: overbought ? '⚠️ Peligro por Sobrecompra. Entrar ahora en la tendencia es entrar tarde y con alto riesgo.' : '✅ El RSI tiene margen para seguir subiendo sin sobrecalentarse.',
                },
                {
                    label: 'Confirmación: Momentum MACD alcista',
                    status: macdLine > macdSig ? 'MET' : 'WAITING',
                    currentValue: `MACD Line: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: bearDiv ? '⚠️ Alerta: Divergencia Bajista Detectada' : 'Monitoreo: Riesgo de Divergencias',
                    status: bearDiv ? 'WARNING' : 'WAITING',
                    currentValue: bearDiv ? 'DIVERGENCIA BAJISTA (Price vs RSI)' : 'Sin anomalías estructurales.',
                    meaning: bearDiv ? 'El precio hizo un máximo más alto, pero el momentum (RSI) cayó. Alerta temprana de corrección.' : 'Subida saludable soportada linealmente por el volumen y momentum.',
                },
            ];
        }

        case 'DISTRIBUTION': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Objetivo: RSI en sobrecompra (> 70)',
                    status: overbought ? 'MET' : rsi > 60 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RSI: ${rsi.toFixed(1)} (${rs.level})`,
                    meaning: overbought ? '✅ Euforia detectada. Institucionales listos para vender.' : 'Esperando agotamiento alcista (sobrecompra real).',
                },
                {
                    label: 'Buscando: Barrida de liquidez institucional',
                    status: 'WAITING',
                    currentValue: resistance ? `Umbral a romper: $${resistance.toFixed(2)}` : 'Mapeando techo...',
                    meaning: 'Buscamos que el precio supere un máximo previo temporalmente para atrapar liquidez (Sweep) antes de caer.',
                },
                {
                    label: bearDiv ? '⚠️ Alerta: Divergencia Bajista (Oculta)' : 'Monitoreo: Debilidad Estructural',
                    status: bearDiv ? 'MET' : 'WAITING',
                    currentValue: bearDiv ? 'DIVERGENCIA BAJISTA DETECTADA' : 'Subida lineal en curso.',
                    meaning: bearDiv ? 'El rally carece de fuerza de compra real. Las manos fuertes están vendiendo agresivamente en la subida.' : 'Distribución algorítmica sin debilidad oculta visible todavía.',
                },
            ];
        }

        case 'MARKDOWN': {
            const rs = rsiDesc();
            const volExtreme = vol > (d.volume_mean * 2.5); // Volumen 2.5x
            return [
                {
                    label: 'Objetivo: Pullback Bajista a la EMA 50',
                    status: 'WAITING',
                    currentValue: resistance ? `Resistencia EMA: $${resistance.toFixed(2)}` : 'Esperando rebote temporal...',
                    meaning: 'En tendencia bajista, el algoritmo busca vender (SHORT) en los rebotes pequeños hacia la EMA 50.',
                },
                {
                    label: 'Confirmando: MACD en territorio negativo',
                    status: macdLine < macdSig ? 'MET' : 'WAITING',
                    currentValue: `MACD Line: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: 'Precaución: ¿Inminente Clímax de Ventas?',
                    status: (oversold && volExtreme) ? 'WARNING' : 'WAITING',
                    currentValue: `Volumen: ${vol.toFixed(0)} | RSI: ${rsi.toFixed(1)}`,
                    meaning: (oversold && volExtreme)
                        ? '⚠️ CLÍMAX DETECTADO. El volumen es extremo en zona de sobreventa. Probable cierre masivo de cortos, peligro de reversión fuerte.'
                        : 'Sin señales de clímax. La tendencia bajista aún tiene margen para continuar.',
                },
                {
                    label: bullDiv ? '🔥 Alerta: Divergencia Alcista en Caída' : 'Monitoreo: Riesgo de Reversión',
                    status: bullDiv ? 'MET' : 'WAITING',
                    currentValue: bullDiv ? 'DIVERGENCIA ALCISTA DETECTADA' : 'Caída fluida normal.',
                    meaning: bullDiv ? 'La presión vendedora se secó. El precio cae por inercia pero el momentum (RSI) institucional ya es alcista.' : 'Las métricas de fuerza acompañan la caída sin desequilibrios.',
                },
            ];
        }

        case 'RANGING': {
            const rp = rangePos();
            const priceOut = rp && (parseInt(rp.pct) > 105 || parseInt(rp.pct) < -5);
            const lowVol = vol < (d.volume_mean * 1.2);
            return [
                {
                    label: 'Calculando: Ubicación geométrica en el lateral',
                    status: rp ? 'PARTIAL' : 'WAITING',
                    currentValue: rp
                        ? `${rp.pct}% (entre $${rp.s.toFixed(2)} y $${rp.r.toFixed(2)})`
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
                        ? '⚠️ ALERTA DE TRAMPA (Fakeout). El precio rompió la barrera pero con volumen débil. Es un cebo para atrapar minoristas. No operar.'
                        : priceOut
                            ? 'Ruptura con intención detectada. Verificando validación institucional.'
                            : 'Navegando dentro del bloque. Se requiere una ruptura volumétrica fuerte para cambiar a tendencia.',
                },
                {
                    label: 'Monitoreo: Compresión BB Squeeze',
                    status: squeeze ? 'MET' : bbwp < 25 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp?.toFixed(1)}%`,
                    meaning: squeeze
                        ? '🔥 SQUEEZE CONFIRMADO. Bandas totalmente comprimidas. Se avecina un movimiento muy fuerte y direccional pronto.'
                        : bbwp < 25
                            ? 'Baja Volatilidad: El "resorte" se está comprimiendo progresivamente.'
                            : 'Volatilidad Normal en el bloque.',
                },
                {
                    label: 'Buscando: Anomalías o Divergencias Ocultas',
                    status: bullDiv ? 'MET' : bearDiv ? 'WARNING' : 'WAITING',
                    currentValue: bullDiv ? 'RSI ALCISTA DETECTADO 🔥' : bearDiv ? 'RSI BAJISTA DETECTADO ⚠️' : 'Sin desequilibrios.',
                    meaning: bullDiv ? 'Posible "Spring" institucional inminente (manipulación a la baja antes de volar).' : bearDiv ? 'Posible "Upthrust" inminente (trampa alcista y caída).' : 'Las métricas están quietas dentro del rango.',
                },
            ];
        }


        default:
            return [
                {
                    label: 'Analizando flujos institucionales',
                    status: 'WAITING',
                    currentValue: 'Sincronizando...',
                    meaning: 'Buscando patrones de acumulación o distribución en los cierres de vela.',
                },
            ];
    }
}

const StatusDot = ({ status }: { status: Condition['status'] }) => {
    const cls = {
        MET: 'border-neon-green/60 bg-neon-green/20 text-neon-green shadow-[0_0_6px_rgba(0,255,65,0.4)]',
        PARTIAL: 'border-yellow-400/60 bg-yellow-400/20 text-yellow-400',
        WAITING: 'border-white/15 bg-white/5 text-white/30',
        WARNING: 'border-neon-red/60 bg-neon-red/20 text-neon-red shadow-[0_0_6px_rgba(255,0,60,0.4)]',
    }[status];
    const sym = { MET: '✓', PARTIAL: '◑', WAITING: '○', WARNING: '⚠' }[status];
    return (
        <div className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded-full border flex items-center justify-center text-[8px] font-black ${cls}`}>
            {sym}
        </div>
    );
};

export default function MarketContextPanel({
    regime, activeStrategy, diagnostic, currentPrice, nearestSupport, nearestResistance, sessionData
}: MarketContextPanelProps) {

    const key = (regime ?? 'UNKNOWN').toUpperCase();
    const meta = REGIME_META[key] ?? REGIME_META['UNKNOWN'];
    const d = diagnostic ?? {};

    const conditions = buildConditions(
        key, d, currentPrice ?? null, nearestSupport ?? null, nearestResistance ?? null, sessionData
    );

    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className={`flex flex-col gap-3 p-4 rounded-lg border ${meta.border} bg-black/40 backdrop-blur-sm`}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen size={11} className="text-white/30" />
                    <span className="text-[9px] font-bold tracking-widest text-white/30 uppercase">Contexto Maestro en Vivo</span>
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${meta.border} bg-black/50`}>
                    {meta.icon}
                    <span className={`text-[10px] font-black tracking-widest ${meta.color}`}>{meta.label}</span>
                </div>
            </div>

            <div className="border-l-2 border-white/10 pl-3">
                <p className="text-[10px] text-white/60 leading-relaxed">{meta.explanation}</p>
            </div>

            {activeStrategy && (
                <div className="flex items-start gap-2">
                    <Target size={10} className={`mt-0.5 flex-shrink-0 ${meta.color}`} />
                    <p className={`text-[10px] font-bold leading-relaxed ${meta.color}`}>{activeStrategy}</p>
                </div>
            )}

            <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-1.5 mb-1">
                    <Clock size={10} className="text-white/30" />
                    <span className="text-[9px] font-bold tracking-widest text-white/30 uppercase">Condiciones del Motor</span>
                </div>

                {conditions.map((c, i) => (
                    <details key={i} className="group">
                        <summary className="flex items-start gap-2 py-1.5 cursor-pointer hover:bg-white/[0.03] rounded px-1 list-none">
                            <StatusDot status={c.status} />
                            <div className="flex flex-col flex-1 min-w-0">
                                <span className={`text-[9px] font-bold leading-tight ${c.status === 'MET' ? 'text-neon-green/90' :
                                    c.status === 'PARTIAL' ? 'text-yellow-400/90' :
                                        c.status === 'WARNING' ? 'text-neon-red/90' :
                                            'text-white/60'
                                    }`}>{c.label}</span>
                                <span className="text-[9px] font-mono text-white/40 mt-0.5">{c.currentValue}</span>
                            </div>
                            <span className="text-[8px] text-white/20 group-open:rotate-90 transition-transform mt-1 flex-shrink-0">▶</span>
                        </summary>
                        <div className="pl-6 pb-2 pr-1">
                            <p className="text-[9px] text-white/50 leading-relaxed italic border-l border-white/10 pl-2">
                                {c.meaning}
                            </p>
                        </div>
                    </details>
                ))}
            </div>

            <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-white/5">
                {[
                    { name: 'RSI ALGO', val: `${d.rsi?.toFixed(1) ?? '---'}`, ok: d.rsi_oversold || d.rsi_overbought },
                    { name: 'MACD X', val: d.macd_bullish_cross ? 'BULL' : 'WAIT', ok: d.macd_bullish_cross },
                    { name: 'BB STAT', val: d.squeeze_active ? 'SQUEEZE' : 'RELAX', ok: d.squeeze_active },
                    { name: 'BBWP %', val: `${d.bbwp?.toFixed(0) ?? '---'}%`, ok: (d.bbwp ?? 50) < 20 },
                ].map(({ name, val, ok }) => (
                    <div key={name} className="flex flex-col items-center gap-0.5 bg-white/[0.02] rounded py-1 px-2">
                        <span className="text-[7px] text-white/25 tracking-widest">{name}</span>
                        <span className={`text-[9px] font-black ${ok ? meta.color : 'text-white/50'}`}>{val}</span>
                    </div>
                ))}
            </div>
        </motion.div>
    );
}
