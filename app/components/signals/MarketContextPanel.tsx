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
        explanation: 'Las manos fuertes compran discretamente a precios bajos antes del alza. El precio se mueve en rango estrecho mientras absorben la oferta. Señal: próxima fase es MARKUP (tendencia alcista).',
    },
    MARKUP: {
        color: 'text-neon-green', border: 'border-neon-green/30', accent: 'bg-neon-green',
        icon: <ArrowUpCircle size={14} className="text-neon-green" />,
        label: 'TENDENCIA ALCISTA (MARKUP)',
        explanation: 'Tendencia alcista activa. El precio forma Higher Highs y Higher Lows. Las manos fuertes ya están posicionadas y el mercado sube impulsado por la demanda institucional.',
    },
    DISTRIBUTION: {
        color: 'text-red-400', border: 'border-red-400/30', accent: 'bg-red-400',
        icon: <Layers size={14} className="text-red-400" />,
        label: 'DISTRIBUCIÓN',
        explanation: 'Los institucionales venden sus posiciones gradualmente a precios altos. El precio parece fuerte pero hay absorción bajista oculta. Señal: próxima fase es MARKDOWN (caída).',
    },
    MARKDOWN: {
        color: 'text-neon-red', border: 'border-neon-red/30', accent: 'bg-neon-red',
        icon: <ArrowDownCircle size={14} className="text-neon-red" />,
        label: 'TENDENCIA BAJISTA (MARKDOWN)',
        explanation: 'Tendencia bajista activa. El precio forma Lower Lows y Lower Highs. La presión vendedora domina y los institucionales están cortos.',
    },
    RANGING: {
        color: 'text-yellow-400', border: 'border-yellow-400/30', accent: 'bg-yellow-400',
        icon: <Pause size={14} className="text-yellow-400" />,
        label: 'RANGO — STANDBY',
        explanation: 'Sin dirección definida. El precio oscila entre un techo y suelo. En rango, las señales de tendencia generan falsas entradas con alta frecuencia. Esperamos ruptura con volumen.',
    },
    UNKNOWN: {
        color: 'text-white/40', border: 'border-white/10', accent: 'bg-white/20',
        icon: <Eye size={14} className="text-white/40" />,
        label: 'CALIBRANDO...',
        explanation: 'Procesando historial de precios para determinar el régimen. Necesitamos 50–200 velas para calcular las medias móviles y detectar la fase del mercado.',
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
        if (macdCross) return `Línea MACD (${macdLine?.toFixed(2)}) cruzó sobre señal (${macdSig?.toFixed(2)}) — cruce alcista confirmado.`;
        if (macdLine > macdSig) return `Línea MACD (${macdLine?.toFixed(2)}) por encima de la señal (${macdSig?.toFixed(2)}) — momentum positivo. Sin cruce aún.`;
        return `Línea MACD (${macdLine?.toFixed(2)}) por debajo de señal (${macdSig?.toFixed(2)}) — diferencia: ${diff}. Aún no hay cruce alcista.`;
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
                    label: 'RSI en zona de sobreventa (< 35)',
                    status: oversold ? 'MET' : rsi < 45 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RSI: ${rsi.toFixed(1)} — ${rs.level}`,
                    meaning: oversold
                        ? `✅ ${rs.note} El motor buscará entrada LONG en el próximo Order Block.`
                        : `Necesitamos que RSI baje a 35 (actualmente ${rsi.toFixed(1)}). ${rs.note}`,
                },
                {
                    label: 'Order Block alcista en zona de soporte',
                    status: 'WAITING',
                    currentValue: support ? `Soporte: $${support.toFixed(2)}` : 'Buscando zona de interés...',
                    meaning: 'Un Order Block alcista es donde los bancos dejaron órdenes de compra pendientes.',
                },
                {
                    label: 'MACD confirma momentum positivo',
                    status: macdCross ? 'MET' : macdLine > macdSig ? 'PARTIAL' : 'WAITING',
                    currentValue: macdCross ? 'Cruce alcista CONFIRMADO' : `MACD: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: 'BB Squeeze activo (BBWP)',
                    status: squeeze ? 'MET' : bbwp < 30 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp?.toFixed(1)}% — ${squeeze ? '🔥 COMPRIMIDO' : 'Expandido'}`,
                    meaning: squeeze ? 'Compresión extrema. Explosión inminente.' : 'Baja volatilidad. Esperando carga de energía.',
                },
                {
                    label: bullDiv ? '🔥 Divergencia Alcista (Price vs RSI)' : 'Divergencias Cuantitativas',
                    status: bullDiv ? 'MET' : 'WAITING',
                    currentValue: bullDiv ? 'DIVERGENCIA ALCISTA DETECTADA' : 'Ninguna divergencia detectada.',
                    meaning: bullDiv ? 'El precio hizo un mínimo más bajo, pero el momentum institucional (RSI) subió. Fuerte señal de trampa bajista inminente a reversión alcista.' : 'El momentum acompaña al precio de manera lineal sin generar disparidades.',
                },
            ];
        }

        case 'MARKUP': {
            const rs = rsiDesc();
            return [
                {
                    label: 'Retroceso (Pullback) de interés',
                    status: 'WAITING',
                    currentValue: support ? `Soporte EMA: $${support.toFixed(2)}` : 'Esperando corrección...',
                    meaning: 'En tendencia, compramos los retrocesos a la EMA 50 o Fibo 0.618.',
                },
                {
                    label: 'Filtro RSI: Espacio Alcista (< 60)',
                    status: overbought ? 'WARNING' : rsi < 60 ? 'MET' : 'PARTIAL',
                    currentValue: `RSI: ${rsi.toFixed(1)} — ${rs.level}`,
                    meaning: overbought ? '⚠️ Peligro por Sobrecompra. Entrar ahora en la tendencia es entrar tarde y con alto riesgo.' : '✅ El RSI tiene margen para seguir subiendo sin sobrecalentarse.',
                },
                {
                    label: 'Momentum MACD alcista',
                    status: macdLine > macdSig ? 'MET' : 'WAITING',
                    currentValue: `MACD: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: bearDiv ? '⚠️ Divergencia Bajista (Price vs RSI)' : 'Divergencias Cuantitativas',
                    status: bearDiv ? 'WARNING' : 'WAITING',
                    currentValue: bearDiv ? 'DIVERGENCIA BAJISTA DETECTADA' : 'Ninguna divergencia detectada.',
                    meaning: bearDiv ? 'El precio hizo un máximo más alto, pero el momentum (RSI) cayó. Alerta temprana de debilidad y posible corrección profunda.' : 'Subida saludable soportada por el momentum.',
                },
            ];
        }

        case 'DISTRIBUTION': {
            const rs = rsiDesc();
            return [
                {
                    label: 'RSI en sobrecompra (> 70)',
                    status: overbought ? 'MET' : rsi > 60 ? 'PARTIAL' : 'WAITING',
                    currentValue: `RSI: ${rsi.toFixed(1)} — ${rs.level}`,
                    meaning: overbought ? '✅ Euforia detectada. Institucionales vendiendo.' : 'Esperando agotamiento.',
                },
                {
                    label: 'Barrida de liquidez (Sweep)',
                    status: 'WAITING',
                    currentValue: resistance ? `Barrera: $${resistance.toFixed(2)}` : 'Buscando techo...',
                    meaning: 'Buscamos que el precio supere un máximo previo y luego sea rechazado.',
                },
                {
                    label: bearDiv ? '⚠️ Divergencia Bajista (Distribución Oculta)' : 'Divergencias Estructurales',
                    status: bearDiv ? 'MET' : 'WAITING',
                    currentValue: bearDiv ? 'DIVERGENCIA BAJISTA DETECTADA' : 'Estructura lineal normal.',
                    meaning: bearDiv ? 'El rally actual carece de fuerza de compra real. Las manos fuertes están vendiendo agresivamente en la subida.' : 'Distribución algorítmica sin alertas ocultas inmediatas.',
                },
            ];
        }

        case 'MARKDOWN': {
            const rs = rsiDesc();
            const volExtreme = vol > (d.volume_mean * 2.5); // Volumen 2.5x
            return [
                {
                    label: 'Pullback bajista',
                    status: 'WAITING',
                    currentValue: resistance ? `Resistencia: $${resistance.toFixed(2)}` : 'Esperando rebote...',
                    meaning: 'Buscamos entrar SHORT en el rebote hacia la EMA 50.',
                },
                {
                    label: 'MACD negativo',
                    status: macdLine < macdSig ? 'MET' : 'WAITING',
                    currentValue: `MACD: ${macdLine?.toFixed(2)}`,
                    meaning: macdDesc(),
                },
                {
                    label: '¿Alerta de Clímax de Ventas?',
                    status: (oversold && volExtreme) ? 'WARNING' : 'WAITING',
                    currentValue: `Vol: ${vol.toFixed(0)} | RSI: ${rsi.toFixed(1)}`,
                    meaning: (oversold && volExtreme)
                        ? '⚠️ CLÍMAX DETECTADO. El volumen es extremo en zona de sobreventa. Esto suele indicar que las manos fuertes están cerrando cortos y empezando a comprar. No entres SHORT aquí.'
                        : 'No hay señales de agotamiento masivo todavía. La tendencia tiene espacio.',
                },
                {
                    label: bullDiv ? '🔥 Divergencia Alcista en Caída' : 'Divergencia de Momentum',
                    status: bullDiv ? 'MET' : 'WAITING',
                    currentValue: bullDiv ? 'DIVERGENCIA ALCISTA DETECTADA' : 'Ninguna anomalía detectada.',
                    meaning: bullDiv ? 'La presión vendedora se secó. El precio cae por inercia pero el momentum institucional ya es alcista.' : 'Las métricas caen al unísono con el precio.',
                },
            ];
        }

        case 'RANGING': {
            const rp = rangePos();
            const priceOut = rp && (parseInt(rp.pct) > 105 || parseInt(rp.pct) < -5);
            const lowVol = vol < (d.volume_mean * 1.2);
            return [
                {
                    label: 'Ubicación en el Rango',
                    status: rp ? 'PARTIAL' : 'WAITING',
                    currentValue: rp
                        ? `${rp.pct}% (entre $${rp.s.toFixed(2)} y $${rp.r.toFixed(2)})`
                        : 'Calculando niveles...',
                    meaning: rp
                        ? `Posición actual: ${rp.pct}% del rango usando ${rp.label}. ${parseInt(rp.pct) < 30 ? 'Zona Suelo (LONG)' : parseInt(rp.pct) > 70 ? 'Zona Techo (SHORT)' : 'Zona Media (Riesgo)'}`
                        : 'El algoritmo está buscando rebotes confirmados para definir el rango.',
                },
                {
                    label: 'Filtro de Ruptura (Fakeout Check)',
                    status: (priceOut && lowVol) ? 'WARNING' : priceOut ? 'MET' : 'WAITING',
                    currentValue: priceOut ? 'PRECIO FUERA' : 'DENTRO DE RANGO',
                    meaning: (priceOut && lowVol)
                        ? '⚠️ ALERTA DE FAKEOUT. El precio rompió el nivel pero el VOLUMEN es bajo. Es una trampa de liquidez para atrapar a traders minoristas antes de volver al rango.'
                        : priceOut
                            ? 'Ruptura con intención detectada. Verificando validación institucional.'
                            : 'Esperando ruptura. Para entrar, el precio debe cerrar fuera con volumen fuerte.',
                },
                {
                    label: 'BB Squeeze (Potencial Ruptura)',
                    status: squeeze ? 'MET' : bbwp < 25 ? 'PARTIAL' : 'WAITING',
                    currentValue: `BBWP: ${bbwp?.toFixed(1)}%`,
                    meaning: squeeze
                        ? '🔥 SQUEEZE CONFIRMADO. Las bandas están comprimidas dentro de los canales. Ruptura inminente.'
                        : bbwp < 25
                            ? 'Baja Volatilidad: El precio está en fase de compresión. El "resorte" está ganando energía para el próximo impulso.'
                            : 'Volatilidad Normal: El mercado tiene espacio para moverse antes de comprimirse de nuevo.',
                },
                {
                    label: 'Divergencia Cuantitativa Activa',
                    status: bullDiv ? 'MET' : bearDiv ? 'WARNING' : 'WAITING',
                    currentValue: bullDiv ? 'ALCISTA DETECTADA 🔥' : bearDiv ? 'BAJISTA DETECTADA ⚠️' : 'Ninguna anomalía en este lateral.',
                    meaning: bullDiv ? 'Posible Wyckoff Spring inminente (manipulación a la baja antes de volar).' : bearDiv ? 'Posible Upthrust inminente (trampa alcista y caída).' : 'El volumen y RSI están neutrales en este bloque.',
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
                    { name: 'RSI', val: `${d.rsi?.toFixed(1) ?? '---'}`, ok: d.rsi_oversold || d.rsi_overbought },
                    { name: 'MACD', val: d.macd_bullish_cross ? '✓ BULL' : 'NEUTRO', ok: d.macd_bullish_cross },
                    { name: 'BB', val: d.squeeze_active ? '🔥 SQZ' : 'LIBRE', ok: d.squeeze_active },
                    { name: 'BBWP', val: `${d.bbwp?.toFixed(0) ?? '---'}%`, ok: (d.bbwp ?? 50) < 20 },
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
