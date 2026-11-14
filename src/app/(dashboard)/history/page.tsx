'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database,
  TrendingUp,
  TrendingDown,
  Target,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Info,
  DollarSign,
  ShieldCheck,
  Cpu,
} from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { getApiBaseUrl } from '../../utils/apiUrl';
import { fetchSignalsAction, fetchTradesAction, BacktestAuditWidget, DatabaseHealthWidget, SystemDiagnosticsWidget } from '@/features';
import { Trade } from '@/entities';

interface SignalEvent {
  id: string;
  asset: string;
  interval: string;
  signal_type: string;
  entry_price: number;
  stop_loss: number;
  take_profit_3r: number;
  regime: string;
  strategy: string;
  status: string;
  created_at?: string;
  timestamp: string;
}

export default function HistoryPage() {
  const [activeTab, setActiveTab] = useState<'signals' | 'trades' | 'audit' | 'database' | 'diagnostics'>('signals');
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [isTursoSynced, setIsTursoSynced] = useState(false);
  const [filterAsset, setFilterAsset] = useState('ALL');
  const [syncError, setSyncError] = useState<string | null>(null);

  const loadData = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setSyncError(null);

    try {
      let tursoOk = false;

      // 1. Cargar Señales desde Turso Cloud vía Server Action (aislado)
      let signalsLoaded = false;
      try {
        const tursoSignalsRes = await fetchSignalsAction({
          status: 'ALL',
          limit: 50,
        });

        if (tursoSignalsRes.success && tursoSignalsRes.data && tursoSignalsRes.data.length > 0) {
          const formatted: SignalEvent[] = tursoSignalsRes.data.map((s) => ({
            id: s.id,
            asset: s.asset,
            interval: s.timeframe || '15m',
            signal_type: s.direction,
            entry_price: s.entryPrice,
            stop_loss: s.stopLoss,
            take_profit_3r: s.takeProfit3 || s.entryPrice * 1.05,
            regime: 'TURSO_ACID',
            strategy: 'QUANT_SMC',
            status: s.status,
            created_at: s.createdAt,
            timestamp: s.createdAt || new Date().toISOString(),
          }));
          setSignals(formatted);
          signalsLoaded = true;
          tursoOk = true;
        }
      } catch (sigErr) {
        console.warn('Error en fetchSignalsAction:', sigErr);
      }

      if (!signalsLoaded) {
        // Fallback a FastAPI si Turso aún no tiene señales o falló el Server Action
        try {
          const BASE_URL = getApiBaseUrl();
          const res = await fetch(`${BASE_URL}/api/v1/signals`, { signal: AbortSignal.timeout(3000) });
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data)) {
              const normalized: SignalEvent[] = data.map((raw: Record<string, unknown>, idx: number) => {
                const entryPx = Number(raw.entry_price ?? raw.price ?? 0);
                const slPx = Number(raw.stop_loss ?? 0);
                const tp3Px = Number(raw.take_profit_3r ?? raw.tp3 ?? raw.take_profit_1 ?? raw.tp1 ?? (entryPx > 0 ? entryPx * 1.05 : 0));
                const ts = String(raw.created_at ?? raw.timestamp ?? new Date().toISOString());
                return {
                  id: String(raw.id ?? `sig_${idx}`),
                  asset: String(raw.asset ?? raw.symbol ?? 'BTCUSDT').toUpperCase(),
                  interval: String(raw.interval ?? raw.timeframe ?? '15m'),
                  signal_type: String(raw.signal_type ?? raw.direction ?? raw.type ?? 'LONG').toUpperCase().includes('SHORT') ? 'SHORT' : 'LONG',
                  entry_price: entryPx,
                  stop_loss: slPx,
                  take_profit_3r: tp3Px,
                  regime: String(raw.regime ?? 'QUANT_ENGINE'),
                  strategy: String(raw.strategy ?? 'QUANT_SMC'),
                  status: String(raw.status ?? 'APPROVED').toUpperCase(),
                  created_at: ts,
                  timestamp: ts,
                };
              });
              setSignals(normalized);
            }
          }
        } catch {
          // Ignorado en Vercel si FastAPI no responde
        }
      }

      // 2. Cargar Trades desde Turso Cloud vía Server Action (aislado) + Fallback REST VPS
      let tradesLoaded = false;
      try {
        const tursoTradesRes = await fetchTradesAction({
          status: 'ALL',
          limit: 50,
        });

        if (tursoTradesRes.success && tursoTradesRes.data) {
          tursoOk = true;
          if (tursoTradesRes.data.length > 0) {
            setTrades(tursoTradesRes.data);
            tradesLoaded = true;
          }
        } else if (!tursoTradesRes.success && tursoTradesRes.error) {
          setSyncError(tursoTradesRes.error);
        }
      } catch (trdErr) {
        console.warn('Error en fetchTradesAction:', trdErr);
        setSyncError(trdErr instanceof Error ? trdErr.message : 'Error consultando trades');
      }

      if (!tradesLoaded) {
        try {
          const BASE_URL = getApiBaseUrl();
          const res = await fetch(`${BASE_URL}/api/v1/trades/history`, { signal: AbortSignal.timeout(3000) });
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              setTrades(data as Trade[]);
            }
          }
        } catch {
          // Ignorado si FastAPI no responde
        }
      }

      setIsTursoSynced(tursoOk);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(true);
    const interval = setInterval(() => loadData(false), 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const StatusBadge = ({ status }: { status: string }) => {
    const norm = (status || 'PENDING').toUpperCase();
    if (norm === 'ACTIVE' || norm === 'APPROVED' || norm === 'OPEN' || norm === 'PENDING' || norm === 'TRIGGERED') {
      return (
        <span className="px-2 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-[10px] font-bold tracking-widest inline-flex items-center gap-1">
          <Clock size={12} /> {norm}
        </span>
      );
    }
    if (norm === 'FILLED' || norm === 'HIT_TP' || norm === 'TAKE_PROFIT' || norm === 'CLOSED') {
      return (
        <span className="px-2 py-1 rounded border border-emerald-500/30 bg-emerald-500/20 text-emerald-300 text-[10px] font-bold tracking-widest inline-flex items-center gap-1">
          <CheckCircle2 size={12} /> {norm}
        </span>
      );
    }
    if (norm === 'HIT_SL' || norm === 'STOP_LOSS' || norm === 'STOPPED_OUT' || norm === 'CANCELLED' || norm === 'REJECTED_EXCHANGE') {
      return (
        <span className="px-2 py-1 rounded border border-rose-500/30 bg-rose-500/10 text-rose-300 text-[10px] font-bold tracking-widest inline-flex items-center gap-1">
          <XCircle size={12} /> {norm}
        </span>
      );
    }
    if (norm === 'EXPIRED' || norm.startsWith('BLOCKED') || norm.includes('VETO')) {
      return (
        <span className="px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-amber-300 text-[10px] font-bold tracking-widest inline-flex items-center gap-1">
          <AlertTriangle size={12} /> {norm}
        </span>
      );
    }
    return (
      <span className="px-2 py-1 rounded border border-slate-500/30 bg-slate-500/10 text-slate-200 text-[10px] font-bold tracking-widest inline-flex items-center gap-1">
        {norm}
      </span>
    );
  };

  const SignalTypeBadge = ({ type }: { type: string }) => {
    const isLong = type === 'LONG' || type === 'BUY';
    return (
      <div
        className={`flex items-center gap-1 px-2.5 py-1 rounded border ${
          isLong
            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
            : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
        }`}
      >
        {isLong ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
        <span className="text-[10px] font-black tracking-widest">{type}</span>
      </div>
    );
  };

  const uniqueAssets = Array.from(new Set(signals.map((s) => s.asset)));
  const filteredSignals =
    filterAsset === 'ALL'
      ? signals
      : signals.filter((s) => s.asset === filterAsset);

  const filteredTrades =
    filterAsset === 'ALL'
      ? trades
      : trades.filter((t) => t.symbol === filterAsset);

  return (
    <div className="h-full w-full flex flex-col p-6 overflow-hidden">
      {/* Header */}
      <div className="flex-none mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-blue-500/20 to-transparent rounded-2xl border border-blue-500/30">
              <Database size={24} className="text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-black text-white/90 tracking-[0.2em]">
                HISTORIAL & TELEMETRÍA DUAL-ENGINE
              </h1>
              <p className="text-xs text-slate-300 tracking-wider flex items-center gap-2 mt-1">
                <Info size={14} className="text-cyan-400" />
                Persistencia continua en Turso Cloud (LibSQL) acoplada al motor algorítmico.
              </p>
            </div>
          </div>

          {/* Turso Cloud Badge */}
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold tracking-wider ${
              isTursoSynced
                ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                : 'bg-cyan-500/10 border border-cyan-500/30 text-cyan-300'
            }`}
          >
            <ShieldCheck size={16} className={isTursoSynced ? 'text-emerald-400' : 'text-cyan-400'} />
            <span>{isTursoSynced ? 'TURSO CLOUD SYNCHRONIZED' : 'VPS DUAL-ENGINE ACTIVE'}</span>
          </div>
        </div>
      </div>

      {/* Tabs & Controls */}
      <div className="flex-none flex flex-wrap items-center justify-between gap-4 mb-4 p-4 border border-white/10 rounded-2xl bg-black/40 backdrop-blur-xl">
        {/* Navigation Tabs (Touch target >= 44px) */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('signals')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'signals'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-500/10'
                : 'bg-white/5 text-slate-300 hover:text-white border border-white/10'
            }`}
          >
            <Clock size={16} />
            <span>SEÑALES CUANTITATIVAS ({signals.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('trades')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'trades'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'bg-white/5 text-slate-300 hover:text-white border border-white/10'
            }`}
          >
            <DollarSign size={16} />
            <span>TRADES EJECUTADOS ({trades.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'audit'
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-lg shadow-purple-500/10'
                : 'bg-white/5 text-slate-300 hover:text-white border border-white/10'
            }`}
          >
            <ShieldCheck size={16} />
            <span>AUDITORÍA QUANT (PARIDAD SSoT)</span>
          </button>

          <button
            onClick={() => setActiveTab('database')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'database'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'bg-white/5 text-slate-300 hover:text-white border border-white/10'
            }`}
          >
            <Database size={16} />
            <span>CAPACIDAD & SALUD DB</span>
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'diagnostics'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-500/10'
                : 'bg-white/5 text-slate-300 hover:text-white border border-white/10'
            }`}
          >
            <Cpu size={16} />
            <span>DIAGNÓSTICO & ALPHA (+164R)</span>
          </button>
        </div>

        {/* Filter Controls (Touch targets >= 44px) */}
        <div className="flex items-center gap-3">
          <label
            htmlFor="history-filter-asset"
            className="text-xs text-slate-300 font-bold tracking-wider"
          >
            FILTRAR ACTIVO:
          </label>
          <select
            id="history-filter-asset"
            name="historyFilterAsset"
            value={filterAsset}
            onChange={(e) => setFilterAsset(e.target.value)}
            className="min-h-[44px] bg-black/50 border border-white/20 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-cyan-400"
          >
            <option value="ALL">TODOS LOS ACTIVOS</option>
            {uniqueAssets.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>

          <button
            onClick={() => loadData(true)}
            className="min-h-[44px] min-w-[44px] bg-white/5 hover:bg-white/10 border border-white/20 rounded-xl flex items-center justify-center text-slate-300 hover:text-white transition-colors"
            title="Refrescar datos de Turso Cloud"
            aria-label="Refrescar registro"
          >
            <RefreshCw
              size={16}
              className={loading ? 'animate-spin text-cyan-400' : ''}
            />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden border border-white/10 rounded-2xl bg-black/40 backdrop-blur-xl flex flex-col">
        {activeTab === 'diagnostics' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
            <SystemDiagnosticsWidget />
          </div>
        ) : activeTab === 'database' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
            <DatabaseHealthWidget />
          </div>
        ) : activeTab === 'audit' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
            <BacktestAuditWidget />
          </div>
        ) : activeTab === 'signals' ? (
          <>
            <div className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/10 bg-white/[0.02] text-[10px] font-bold text-slate-300 tracking-widest">
              <div className="col-span-2">TIMESTAMP</div>
              <div className="col-span-2">ASSET / TF</div>
              <div className="col-span-1">DIRECTION</div>
              <div className="col-span-2">ENTRY</div>
              <div className="col-span-2">TARGET (3R)</div>
              <div className="col-span-1">STOP LOSS</div>
              <div className="col-span-2">STATUS</div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {loading && signals.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <span className="text-cyan-400 animate-pulse text-xs tracking-widest font-bold">
                    CONSULTANDO TURSO CLOUD...
                  </span>
                </div>
              ) : filteredSignals.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-400 text-xs tracking-widest font-bold">
                  NO SE ENCONTRARON SEÑALES
                </div>
              ) : (
                <div className="flex flex-col">
                  <AnimatePresence>
                    {filteredSignals.map((sig, i) => (
                      <motion.div
                        key={sig.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i * 0.02, 0.3) }}
                        className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/5 items-center hover:bg-white/[0.02] transition-colors"
                      >
                        <div className="col-span-2 text-xs text-slate-300 font-mono">
                          {sig.created_at || sig.timestamp
                            ? new Date(
                                sig.created_at || sig.timestamp
                              ).toLocaleString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                                month: 'short',
                                day: 'numeric',
                              })
                            : 'N/A'}
                        </div>
                        <div className="col-span-2 flex items-center gap-2">
                          <span className="text-xs font-black text-white">
                            {sig.asset}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded border border-white/10 bg-white/5 text-slate-300 font-mono">
                            {sig.interval}
                          </span>
                        </div>
                        <div className="col-span-1">
                          <SignalTypeBadge type={sig.signal_type} />
                        </div>
                        <div className="col-span-2 text-xs font-mono text-white/90">
                          {formatCurrency(sig.entry_price)}
                        </div>
                        <div className="col-span-2 text-xs font-mono text-emerald-400 flex items-center gap-1">
                          <Target size={12} />{' '}
                          {formatCurrency(sig.take_profit_3r) || 'N/A'}
                        </div>
                        <div className="col-span-1 text-xs font-mono text-rose-400">
                          {formatCurrency(sig.stop_loss)}
                        </div>
                        <div className="col-span-2">
                          <StatusBadge status={sig.status} />
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/10 bg-white/[0.02] text-[10px] font-bold text-slate-300 tracking-widest">
              <div className="col-span-2">TRADE ID</div>
              <div className="col-span-2">SYMBOL</div>
              <div className="col-span-1">SIDE</div>
              <div className="col-span-2">ENTRY PRICE</div>
              <div className="col-span-1">QUANTITY</div>
              <div className="col-span-2">PNL ($)</div>
              <div className="col-span-2">STATUS</div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {loading && trades.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <span className="text-emerald-400 animate-pulse text-xs tracking-widest font-bold">
                    CARGANDO TRADES DE TURSO...
                  </span>
                </div>
              ) : filteredTrades.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-400 text-xs tracking-widest font-bold">
                  NO HAY TRADES REGISTRADOS EN TURSO AÚN
                </div>
              ) : (
                <div className="flex flex-col">
                  <AnimatePresence>
                    {filteredTrades.map((t, i) => (
                      <motion.div
                        key={t.id || i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i * 0.02, 0.3) }}
                        className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/5 items-center hover:bg-white/[0.02] transition-colors"
                      >
                        <div className="col-span-2 text-xs text-slate-300 font-mono truncate" title={t.id}>
                          {t.id?.slice(0, 12)}...
                        </div>
                        <div className="col-span-2 text-xs font-black text-white">
                          {t.symbol}
                        </div>
                        <div className="col-span-1">
                          <SignalTypeBadge type={t.side} />
                        </div>
                        <div className="col-span-2 text-xs font-mono text-white/90">
                          {formatCurrency(t.entryPrice)}
                        </div>
                        <div className="col-span-1 text-xs font-mono text-slate-300">
                          {t.quantity}
                        </div>
                        <div
                          className={`col-span-2 text-xs font-mono font-bold ${
                            t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {t.pnl >= 0 ? `+${t.pnl.toFixed(2)}` : t.pnl.toFixed(2)} USDT
                        </div>
                        <div className="col-span-2">
                          <StatusBadge status={t.status} />
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
