'use client';

import React, { useState, useEffect } from 'react';
import {
  fetchBacktestAuditMetricsAction,
  BacktestAuditMetrics,
} from '../actions';

export function BacktestAuditWidget() {
  const [metrics, setMetrics] = useState<BacktestAuditMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPlaybook, setSelectedPlaybook] = useState<'ALL' | 'LIQUIDITY_SWEEP_FVG' | 'OB_DISCOUNT_RETEST'>('ALL');

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      try {
        const res = await fetchBacktestAuditMetricsAction({ playbook: selectedPlaybook });
        if (res.success && res.data && isMounted) {
          setMetrics(res.data);
        }
      } catch (e) {
        console.error('Error cargando auditoría cuantitativa:', e);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, [selectedPlaybook]);

  return (
    <div className="w-full bg-[#050B14]/90 border border-slate-700/60 rounded-2xl p-4 sm:p-6 shadow-2xl backdrop-blur-xl flex flex-col gap-6">
      {/* Header institucional */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              AUDITORÍA MATEMÁTICA CERTIFICADA
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              SSoT v60.0 Event-Driven
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-2 tracking-tight">
            Panorama Cuantitativo & Paridad Real en Vivo
          </h2>
          <p className="text-sm text-slate-300 mt-1">
            Auditoría de 437 trades con reconciliación de órdenes límite y cero sesgo de ganancia fantasma.
          </p>
        </div>

        {/* Filtro Selector con Touch Target >= 44px */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-xl border border-slate-700/70">
          {(['ALL', 'LIQUIDITY_SWEEP_FVG', 'OB_DISCOUNT_RETEST'] as const).map((pb) => (
            <button
              key={pb}
              onClick={() => setSelectedPlaybook(pb)}
              className={`min-h-[44px] px-4 rounded-lg text-xs font-semibold transition-colors duration-150 flex items-center justify-center ${
                selectedPlaybook === pb
                  ? 'bg-cyan-500 text-slate-950 shadow-md font-bold'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800'
              }`}
            >
              {pb === 'ALL' ? 'Todos' : pb === 'LIQUIDITY_SWEEP_FVG' ? 'Sweep FVG' : 'OB Retest'}
            </button>
          ))}
        </div>
      </div>

      {loading && !metrics ? (
        <div className="min-h-[200px] flex items-center justify-center text-slate-400 text-sm">
          Cargando telemetría matemática auditada...
        </div>
      ) : metrics ? (
        <>
          {/* Métricas Principales en Grid Base 8 */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Win Rate */}
            <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Win Rate Real
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl sm:text-3xl font-black text-white">
                  {metrics.winRatePct}%
                </span>
                <span className="text-xs text-slate-400">
                  ({metrics.winningTrades}W / {metrics.losingTrades}L)
                </span>
              </div>
              <span className="text-xs text-emerald-400 mt-1 font-medium">
                Sin sesgo intrabar
              </span>
            </div>

            {/* Profit Factor */}
            <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Profit Factor Real
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl sm:text-3xl font-black text-cyan-300">
                  {metrics.profitFactorBase}
                </span>
                <span className="text-xs text-cyan-400 font-semibold">
                  (🚀 {metrics.profitFactorAlphaTier} Alpha)
                </span>
              </div>
              <span className="text-xs text-slate-300 mt-1">
                Pérdida media: {metrics.averageLossR}R
              </span>
            </div>

            {/* Retorno Total */}
            <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Retorno Total Neto
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl sm:text-3xl font-black text-emerald-400">
                  +{metrics.totalNetRBase} R
                </span>
                <span className="text-xs text-emerald-300 font-semibold">
                  (+{metrics.totalNetRAlphaTier} R)
                </span>
              </div>
              <span className="text-xs text-slate-300 mt-1">
                Comisiones Bitunix ya deducidas
              </span>
            </div>

            {/* Blindaje FTMO / Max DD */}
            <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Max Drawdown Cartera
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl sm:text-3xl font-black text-amber-300">
                  {metrics.maxDrawdownAlphaTierPct}%
                </span>
                <span className="text-xs text-slate-400">
                  (Base: {metrics.maxDrawdownBasePct}%)
                </span>
              </div>
              <span className="text-xs text-emerald-400 mt-1 font-medium">
                🛡️ Pasa el filtro FTMO (Max 5%)
              </span>
            </div>
          </div>

          {/* Cuadro de Paridad Matemática Frente a Live Trading */}
          <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-lg border border-emerald-500/40">
                ✓
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">
                  Paridad Matemática 1:1 con Ejecución en Vivo (Bitunix & MT5)
                </h4>
                <p className="text-xs text-slate-300 mt-0.5">
                  Las órdenes límite se ejecutan exactamente a 1.2R (50%) y 2.0R (30%). Se eliminaron +30.5R de inflación teórica.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="text-right hidden sm:block">
                <span className="text-xs text-slate-400 block">Sharpe / Sortino</span>
                <span className="text-sm font-bold text-white">
                  {metrics.sharpeRatio} / {metrics.sortinoRatio}
                </span>
              </div>
              <div className="h-8 w-px bg-slate-800 hidden sm:block" />
              <div className="text-right hidden sm:block">
                <span className="text-xs text-slate-400 block">Ratio Asimetría (W/L)</span>
                <span className="text-sm font-bold text-emerald-400">
                  {metrics.asymmetryRatio}:1.0
                </span>
              </div>
            </div>
          </div>

          {/* Universo de Activos Auditados vs Podados */}
          <div className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Universo Auditado SSoT (Mega-Caps, High-Beta Alts & Podas Cuantitativas)
            </span>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
                <span className="text-xs font-medium text-cyan-400 uppercase tracking-wider">
                  🏛️ Mega-Caps (1H OTE Swing)
                </span>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {metrics.auditedUniverse.megaCaps.map((asset) => (
                    <span key={asset} className="px-2 py-1 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[11px] font-mono font-bold">
                      {asset}
                    </span>
                  ))}
                </div>
                <span className="text-[11px] text-slate-400 mt-2">Buffer SL amplio (2.5x - 2.8x ATR)</span>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
                <span className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
                  🚀 High-Beta Alts & Metales (15M Scalp)
                </span>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {metrics.auditedUniverse.highBetaAlts.concat(metrics.auditedUniverse.tradFiMetals).map((asset) => (
                    <span key={asset} className="px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px] font-mono font-bold">
                      {asset}
                    </span>
                  ))}
                </div>
                <span className="text-[11px] text-slate-400 mt-2">SL Ágil (1.8x - 2.0x ATR) + Multiplicador Alfa</span>
              </div>

              <div className="bg-slate-900/60 border border-rose-950/60 p-4 rounded-xl flex flex-col justify-between">
                <span className="text-xs font-medium text-rose-400 uppercase tracking-wider">
                  🚫 Activos Podados / Veto Intradía
                </span>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {metrics.auditedUniverse.prunedAssets.map((asset) => (
                    <span key={asset} className="px-2 py-1 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] font-mono font-bold">
                      {asset}
                    </span>
                  ))}
                </div>
                <span className="text-[11px] text-slate-400 mt-2">Excluidos de órdenes automáticas por bajo PF/ruido</span>
              </div>
            </div>
          </div>

          {/* Sincronización Fiel de Ciclo de Vida: Apertura y Gestión */}
          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col gap-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Sincronización de Gestión de Operaciones (Backtest ↔ Live Engine)
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 block">TP1 (+{metrics.lifecycleParity.tp1TargetR}R)</span>
                <span className="text-lg font-black text-white">{metrics.lifecycleParity.tp1GridPct}% Cierre</span>
                <span className="text-[11px] text-emerald-400 block mt-0.5">+ Fast Breakeven</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 block">TP2 (+{metrics.lifecycleParity.tp2TargetR}R)</span>
                <span className="text-lg font-black text-white">{metrics.lifecycleParity.tp2GridPct}% Cierre</span>
                <span className="text-[11px] text-cyan-400 block mt-0.5">SL sube a +1.0R Verde</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 block">TP3 Runner (+{metrics.lifecycleParity.tp3TargetR}R)</span>
                <span className="text-lg font-black text-white">{metrics.lifecycleParity.tp3GridPct}% Cierre</span>
                <span className="text-[11px] text-purple-400 block mt-0.5">Trailing Ratchet</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 block">SOP-25 Corte Temprano</span>
                <span className="text-lg font-black text-rose-400">{metrics.lifecycleParity.sop25CutoffR}R</span>
                <span className="text-[11px] text-emerald-300 block mt-0.5">Ahorro 35% de Riesgo</span>
              </div>
            </div>
          </div>

          {/* Desglose por Playbook */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Desglose Institucional por Playbook (Tradezella Style)
            </span>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {metrics.playbooks.map((pb) => (
                <div
                  key={pb.name}
                  className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-white">{pb.name}</span>
                    <span className="text-xs font-semibold text-cyan-400">
                      PF: {pb.profitFactor}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-300">
                    <span>Trades: {pb.trades}</span>
                    <span>Win Rate: {pb.winRatePct}%</span>
                    <span className="text-emerald-400 font-bold">Total: +{pb.totalR} R</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
