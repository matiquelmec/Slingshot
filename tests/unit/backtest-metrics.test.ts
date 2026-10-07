import { describe, it, expect } from 'vitest';
import {
  fetchBacktestAuditMetricsAction,
  backtestAuditQuerySchema,
  fetchTheoryVsPracticeParityAction,
  theoryVsPracticeQuerySchema,
} from '@/features';
import { UserSession } from '@/shared';

describe('Features: Backtest Metrics Audit Slice (FSD & Zero Trust)', () => {
  const mockSession: UserSession = {
    userId: 'user_quant_auditor',
    tenantId: 'tenant_institutional_audit',
    email: 'auditor@slingshot.internal',
    role: 'trader',
  };

  it('debe validar los esquemas Zod de consulta correctamente', () => {
    const validParams = backtestAuditQuerySchema.parse({
      playbook: 'LIQUIDITY_SWEEP_FVG',
      includeTearSheet: true,
    });
    expect(validParams.playbook).toBe('LIQUIDITY_SWEEP_FVG');
    expect(validParams.includeTearSheet).toBe(true);

    const defaultParams = backtestAuditQuerySchema.parse({});
    expect(defaultParams.playbook).toBe('ALL');
    expect(defaultParams.includeTearSheet).toBe(true);
  });

  it('debe rechazar consultas con playbooks inválidos', () => {
    expect(() =>
      backtestAuditQuerySchema.parse({
        playbook: 'INVALID_PLAYBOOK',
      })
    ).toThrow();
  });

  it('debe retornar métricas auditadas con paridad SSoT v60.0 y sin ganancia fantasma', async () => {
    const result = await fetchBacktestAuditMetricsAction(
      { playbook: 'ALL' },
      mockSession
    );

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();

    const data = result.data!;
    expect(data.auditStatus).toBe('VERIFIED_SSOT_PARITY');
    expect(data.totalTrades).toBe(437);
    expect(data.winRatePct).toBe(44.9);
    expect(data.liveParityVerified).toBe(true);
    expect(data.phantomProfitCleared).toBe(true);

    // Paridad matemática estricta: órdenes límite TP1 @ 1.2R y TP2 @ 2.0R
    expect(data.profitFactorBase).toBe(1.62);
    expect(data.profitFactorAlphaTier).toBe(1.79);
    expect(data.totalNetRBase).toBe(97.98);
    expect(data.maxDrawdownAlphaTierPct).toBe(-4.76); // < 5.0% Blindaje FTMO
    expect(data.asymmetryRatio).toBe(2.2);

    expect(data.playbooks.length).toBe(2);

    // Verificación de Universo Auditado y Paridad de Ciclo de Vida
    expect(data.auditedUniverse).toBeDefined();
    expect(data.auditedUniverse.megaCaps).toContain('BTCUSDT');
    expect(data.auditedUniverse.megaCaps).toContain('SOLUSDT');
    expect(data.auditedUniverse.highBetaAlts).toContain('INJUSDT');
    expect(data.auditedUniverse.highBetaAlts).toContain('NEARUSDT');
    expect(data.auditedUniverse.prunedAssets).toContain('AVAXUSDT');
    expect(data.auditedUniverse.prunedAssets).toContain('RENDERUSDT');

    expect(data.lifecycleParity).toBeDefined();
    expect(data.lifecycleParity.tp1GridPct).toBe(50);
    expect(data.lifecycleParity.tp1TargetR).toBe(1.2);
    expect(data.lifecycleParity.tp2GridPct).toBe(30);
    expect(data.lifecycleParity.tp2TargetR).toBe(2.0);
    expect(data.lifecycleParity.tp3GridPct).toBe(20);
    expect(data.lifecycleParity.sop25CutoffR).toBe(-0.65);
  });

  it('debe filtrar correctamente por playbook específico', async () => {
    const result = await fetchBacktestAuditMetricsAction(
      { playbook: 'OB_DISCOUNT_RETEST' },
      mockSession
    );

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data!.playbooks.length).toBe(1);
    expect(result.data!.playbooks[0].name).toBe('OB_DISCOUNT_RETEST');
    expect(result.data!.playbooks[0].profitFactor).toBe(1.91);
  });

  it('debe validar el esquema Zod de Paridad Teoría vs Práctica (SOP-119)', () => {
    const validParams = theoryVsPracticeQuerySchema.parse({
      comparisonScope: 'SL_TP_RELIABILITY',
      assetFilter: 'BTCUSDT',
    });
    expect(validParams.comparisonScope).toBe('SL_TP_RELIABILITY');
    expect(validParams.assetFilter).toBe('BTCUSDT');

    const defaultParams = theoryVsPracticeQuerySchema.parse({});
    expect(defaultParams.comparisonScope).toBe('FULL_SPECTRUM');
    expect(defaultParams.assetFilter).toBe('ALL');

    expect(() =>
      theoryVsPracticeQuerySchema.parse({
        comparisonScope: 'INVALID_SCOPE',
      })
    ).toThrow();
  });

  it('debe certificar la fiabilidad de Stop Loss (99.8%) y Take Profit (99.4%) en la auditoría de paridad (SOP-119)', async () => {
    const result = await fetchTheoryVsPracticeParityAction(
      { comparisonScope: 'FULL_SPECTRUM' },
      mockSession
    );

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();

    const report = result.data!;
    expect(report.auditStatus).toBe('EMPIRICAL_PARITY_CERTIFIED');
    expect(report.scorecard.stopLossReliabilityPct).toBe(99.8);
    expect(report.scorecard.stopLossStatus).toBe('ROCK_SOLID_HARDENED');
    expect(report.scorecard.takeProfitReliabilityPct).toBe(99.4);
    expect(report.scorecard.takeProfitStatus).toBe('SECURED_DUAL_LAYER');
    expect(report.scorecard.positionManagementReliabilityPct).toBe(99.2);

    // Verificación de Haircut Cuantitativo y Expectativa Matemática Real
    expect(report.scorecard.theoreticalExpectancyR).toBe(0.224);
    expect(report.scorecard.realWorldExpectancyR).toBe(0.198);
    expect(report.scorecard.expectationHaircutPct).toBe(11.6);
    expect(report.scorecard.theoreticalProfitFactor).toBe(1.79);
    expect(report.scorecard.realWorldProfitFactor).toBe(1.62);
    expect(report.scorecard.isSystemReliable).toBe(true);

    // Dimensiones comparativas y ciclo de vida de posición
    expect(report.dimensions.length).toBe(6);
    expect(report.lifecycleStages.length).toBe(6);
    expect(report.criticalTakeaways.length).toBe(4);
  });

  it('debe filtrar adecuadamente las dimensiones según el alcance solicitado', async () => {
    const slTpResult = await fetchTheoryVsPracticeParityAction(
      { comparisonScope: 'SL_TP_RELIABILITY' },
      mockSession
    );
    expect(slTpResult.success).toBe(true);
    expect(slTpResult.data!.dimensions.length).toBe(2);

    const frictionResult = await fetchTheoryVsPracticeParityAction(
      { comparisonScope: 'EXECUTION_FRICTION' },
      mockSession
    );
    expect(frictionResult.success).toBe(true);
    expect(frictionResult.data!.dimensions.length).toBe(3);
  });
});
