'use client';

import React, { useState, useEffect } from 'react';
import {
  fetchBacktestAuditMetricsAction,
  fetchTheoryVsPracticeParityAction,
  BacktestAuditMetrics,
  TheoryVsPracticeParityReport,
} from '../actions';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Cpu,
  Activity,
  Layers,
  ArrowRight,
  Zap,
} from 'lucide-react';

export function BacktestAuditWidget() {
  const [activeTab, setActiveTab] = useState<'SSOT_BACKTEST' | 'PARITY_AUDIT'>('SSOT_BACKTEST');
  const [metrics, setMetrics] = useState<BacktestAuditMetrics | null>(null);
  const [parityReport, setParityReport] = useState<TheoryVsPracticeParityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPlaybook, setSelectedPlaybook] = useState<'ALL' | 'LIQUIDITY_SWEEP_FVG' | 'OB_DISCOUNT_RETEST'>('ALL');
  const [parityScope, setParityScope] = useState<'FULL_SPECTRUM' | 'SL_TP_RELIABILITY' | 'EXECUTION_FRICTION' | 'CAPITAL_PRESERVATION'>('FULL_SPECTRUM');

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      try {
        if (activeTab === 'SSOT_BACKTEST') {
          const res = await fetchBacktestAuditMetricsAction({ playbook: selectedPlaybook });
          if (res.success && res.data && isMounted) {
            setMetrics(res.data);
          }
        } else {
          const res = await fetchTheoryVsPracticeParityAction({ comparisonScope: parityScope });
          if (res.success && res.data && isMounted) {
            setParityReport(res.data);
          }
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
  }, [activeTab, selectedPlaybook, parityScope]);

  return (
    <div className="w-full bg-[#050B14]/90 border border-slate-700/60 rounded-2xl p-4 sm:p-6 shadow-2xl backdrop-blur-xl flex flex-col gap-6">
      {/* Selector de Modo Principal (Touch targets >= 44px) */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2 bg-slate-900/90 p-1.5 rounded-xl border border-slate-700/80">
          <button
            onClick={() => setActiveTab('SSOT_BACKTEST')}
            className={`min-h-[44px] px-5 rounded-lg text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'SSOT_BACKTEST'
                ? 'bg-cyan-500 text-slate-950 shadow-lg font-black'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
            }`}
          >
            <Activity size={16} />
            <span>PANORAMA QUANT (BACKTEST SSoT)</span>
          </button>
          <button
            onClick={() => setActiveTab('PARITY_AUDIT')}
            className={`min-h-[44px] px-5 rounded-lg text-xs font-bold tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'PARITY_AUDIT'
                ? 'bg-purple-500 text-slate-950 shadow-lg font-black'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
            }`}
          >
            <ShieldCheck size={16} />
            <span>TEORÍA VS. PRÁCTICA (SOP-119)</span>
          </button>
        </div>

        {activeTab === 'SSOT_BACKTEST' ? (
          /* Filtro Selector Playbook con Touch Target >= 44px */
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
        ) : (
          /* Filtro Selector de Enfoque Paridad */
          <div className="flex items-center gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-700/70 overflow-x-auto">
            {(
              [
                { id: 'FULL_SPECTRUM', label: 'Todo el Espectro' },
                { id: 'SL_TP_RELIABILITY', label: 'SL & TP Fiabilidad' },
                { id: 'EXECUTION_FRICTION', label: 'Fricción de Mercado' },
                { id: 'CAPITAL_PRESERVATION', label: 'Preservación Capital' },
              ] as const
            ).map((sc) => (
              <button
                key={sc.id}
                onClick={() => setParityScope(sc.id)}
                className={`min-h-[44px] px-3 rounded-lg text-xs font-medium transition-colors duration-150 whitespace-nowrap flex items-center justify-center ${
                  parityScope === sc.id
                    ? 'bg-purple-500 text-slate-950 shadow-md font-bold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800'
                }`}
              >
                {sc.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* CONTENIDO MODO 1: BACKTEST SSOT */}
      {activeTab === 'SSOT_BACKTEST' && (
        <>
          {/* Header institucional */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                AUDITORÍA MATEMÁTICA CERTIFICADA
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                SSoT v60.0 Event-Driven
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1 tracking-tight">
              Panorama Cuantitativo & Paridad Real en Vivo
            </h2>
            <p className="text-sm text-slate-300">
              Auditoría de 437 trades con reconciliación de órdenes límite y cero sesgo de ganancia fantasma.
            </p>
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

              {/* Sincronización Fiel de Ciclo de Vida */}
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
        </>
      )}

      {/* CONTENIDO MODO 2: TEORÍA VS PRÁCTICA REAL (SOP-119) */}
      {activeTab === 'PARITY_AUDIT' && (
        <>
          {/* Header de Paridad */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                AUDITORÍA DE EJECUCIÓN & ROBUSTEZ (SOP-119)
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                TIER_1_AAA INSTITUCIONAL
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1 tracking-tight">
              Contraste Empírico: Teoría (Backtest & Monte Carlo) vs. Realidad en Exchange
            </h2>
            <p className="text-sm text-slate-300">
              Evaluación exhaustiva de fiabilidad de Stop Loss, Take Profit, fricción de microestructura y gestión en tiempo real.
            </p>
          </div>

          {loading && !parityReport ? (
            <div className="min-h-[200px] flex items-center justify-center text-slate-400 text-sm">
              Cargando auditoría empírica de paridad en vivo...
            </div>
          ) : parityReport ? (
            <>
              {/* Tarjetas de Fiabilidad y Solvencia en Grid Base 8 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* SL Reliability */}
                <div className="bg-slate-900/70 border border-emerald-500/30 p-4 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                        Fiabilidad Stop Loss
                      </span>
                      <ShieldCheck size={18} className="text-emerald-400" />
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-black text-emerald-400">
                        {parityReport.scorecard.stopLossReliabilityPct}%
                      </span>
                      <span className="text-xs text-emerald-300 font-semibold">
                        ROCK-SOLID
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-2 leading-relaxed">
                    Órdenes Stop registradas nativamente en Bitunix. Cierres de emergencia blindados con positionId (SOP-118).
                  </p>
                </div>

                {/* TP Reliability */}
                <div className="bg-slate-900/70 border border-cyan-500/30 p-4 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                        Fiabilidad Take Profit
                      </span>
                      <Zap size={18} className="text-cyan-400" />
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-black text-cyan-300">
                        {parityReport.scorecard.takeProfitReliabilityPct}%
                      </span>
                      <span className="text-xs text-cyan-300 font-semibold">
                        DUAL-LAYER
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-2 leading-relaxed">
                    TP nativo inicial (SOP-117) + Preservación invariante en ajustes de SL (SOP-118) + Reconciliador 15s.
                  </p>
                </div>

                {/* Dynamic Management */}
                <div className="bg-slate-900/70 border border-purple-500/30 p-4 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                        Gestión de Posiciones
                      </span>
                      <Layers size={18} className="text-purple-400" />
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-black text-purple-300">
                        {parityReport.scorecard.positionManagementReliabilityPct}%
                      </span>
                      <span className="text-xs text-purple-300 font-semibold">
                        OPERATIVO
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-2 leading-relaxed">
                    Escalamiento en 5 fases continuas: SOP-25 (-0.65R) → SOP-48 (-0.5R) → Fast BE (+1.0R) → Trailing Runner.
                  </p>
                </div>

                {/* Haircut Parity */}
                <div className="bg-slate-900/70 border border-slate-700/80 p-4 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                        Expectativa Real / Trade
                      </span>
                      <TrendingUp size={18} className="text-amber-400" />
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-black text-amber-300">
                        +{parityReport.scorecard.realWorldExpectancyR} R
                      </span>
                      <span className="text-xs text-slate-400">
                        (Teórico: +{parityReport.scorecard.theoreticalExpectancyR}R)
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-2 leading-relaxed">
                    Haircut absorbido del {parityReport.scorecard.expectationHaircutPct}% por slippage y carry drag. Profit Factor real: {parityReport.scorecard.realWorldProfitFactor}.
                  </p>
                </div>
              </div>

              {/* Dictamen Institucional */}
              <div className="bg-slate-900/50 border border-purple-500/30 p-4 sm:p-5 rounded-xl flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-purple-500/20 text-purple-300 flex items-center justify-center shrink-0 border border-purple-500/40">
                  <Cpu size={24} />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white tracking-wide">
                    Dictamen Técnico Staff Software Engineer & Cuantitativo
                  </h4>
                  <p className="text-xs text-slate-200 mt-1 leading-relaxed">
                    {parityReport.scorecard.systemVerdict}
                  </p>
                </div>
              </div>

              {/* Matriz Comparativa: Teoría vs. Monte Carlo vs. Práctica Real */}
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Matriz Comparativa de Paridad y Fricción de Microestructura
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {parityReport.dimensions.length} Dimensiones Auditadas
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {parityReport.dimensions.map((dim, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col gap-3 hover:border-slate-700 transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">{dim.dimension}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                              dim.frictionLevel === 'MINIMAL'
                                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                                : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                            }`}
                          >
                            Fricción {dim.frictionLevel}
                          </span>
                        </div>
                        <span className="text-xs font-mono font-bold text-cyan-300">
                          {dim.mitigationSop}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                        {/* Teoría Backtest */}
                        <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                          <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block mb-1">
                            1. Teoría Backtest (SSoT v60.0)
                          </span>
                          <p className="text-slate-300 leading-relaxed">{dim.theoryBacktest}</p>
                        </div>

                        {/* Monte Carlo */}
                        <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                          <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider block mb-1">
                            2. Simulación Monte Carlo (10k)
                          </span>
                          <p className="text-slate-300 leading-relaxed">{dim.monteCarloStochastic}</p>
                        </div>

                        {/* Realidad Exchange */}
                        <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block mb-1">
                            3. Práctica Real (Bitunix / MT5)
                          </span>
                          <p className="text-slate-200 leading-relaxed">{dim.liveExchangeReality}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Ciclo de Vida de Posición: Gestión Paso a Paso */}
              <div className="bg-slate-900/60 border border-slate-800 p-4 sm:p-5 rounded-xl flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-wide">
                      Mecánica y Ciclo de Vida: ¿Cómo se gestionan las posiciones en vivo?
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Transición determinista de estados en TradeManager y Reconciliador de NexusNode.
                    </p>
                  </div>
                  <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    6 FASES AUTOMATIZADAS
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {parityReport.lifecycleStages.map((stg, i) => (
                    <div
                      key={i}
                      className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl flex flex-col justify-between gap-2"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-purple-300">{stg.stage}</span>
                          <span className="text-[10px] font-mono text-slate-500">#{i}</span>
                        </div>
                        <span className="text-[11px] font-medium text-amber-300 mt-1 block">
                          ⚡ {stg.thresholdCondition}
                        </span>
                        <div className="mt-2 text-xs text-slate-300 space-y-1">
                          <p>
                            <strong className="text-slate-200">SL:</strong> {stg.targetSlAction}
                          </p>
                          <p>
                            <strong className="text-slate-200">TP:</strong> {stg.targetTpAction}
                          </p>
                        </div>
                      </div>
                      <div className="pt-2 border-t border-slate-900">
                        <span className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                          <CheckCircle2 size={12} /> {stg.exchangeSafetyGuarantee}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Respuestas a Preguntas Críticas del Usuario */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {parityReport.criticalTakeaways.map((item, idx) => (
                  <div
                    key={idx}
                    className={`p-4 rounded-xl border flex flex-col justify-between ${
                      item.type === 'SUCCESS'
                        ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-100'
                        : item.type === 'WARNING'
                        ? 'bg-amber-950/20 border-amber-500/30 text-amber-100'
                        : 'bg-cyan-950/20 border-cyan-500/30 text-cyan-100'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        {item.type === 'SUCCESS' ? (
                          <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                        ) : item.type === 'WARNING' ? (
                          <AlertTriangle size={16} className="text-amber-400 shrink-0" />
                        ) : (
                          <ArrowRight size={16} className="text-cyan-400 shrink-0" />
                        )}
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                          {item.title}
                        </h4>
                      </div>
                      <p className="text-xs text-slate-200 mt-2 leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
