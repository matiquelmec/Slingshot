import { describe, it, expect } from 'vitest';
import {
  fetchSystemDiagnosticsAction,
  systemDiagnosticsQuerySchema,
} from '@/features';
import { UserSession } from '@/shared';

describe('Features: System Diagnostics & Alpha Optimizer Slice (FSD & Zero Trust)', () => {
  const mockSession: UserSession = {
    userId: 'user_institutional_lead',
    tenantId: 'tenant_sovereign_apex',
    email: 'lead@slingshot.internal',
    role: 'admin',
  };

  it('debe validar los esquemas Zod de consulta con valores por defecto', () => {
    const valid = systemDiagnosticsQuerySchema.parse({});
    expect(valid.includeDatabaseCheck).toBe(true);
    expect(valid.assetFilter).toBe('ALL');

    const custom = systemDiagnosticsQuerySchema.parse({
      includeDatabaseCheck: false,
      assetFilter: 'BTCUSDT',
    });
    expect(custom.includeDatabaseCheck).toBe(false);
    expect(custom.assetFilter).toBe('BTCUSDT');
  });

  it('debe certificar que el sistema NO está congelado y reportar el estado de paciencia selectiva', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();

    const data = result.data!;
    expect(data.isFrozen).toBe(false);
    expect(data.systemState).toBe('SELECTIVE_PATIENCE');
    expect(data.freezeDiagnosis).toContain('El sistema NO está congelado');
    expect(data.tenantId).toBe(mockSession.tenantId);
    expect(data.userId).toBe(mockSession.userId);
  });

  it('debe auditar los 7 centinelas de riesgo que justifican la selectividad institucional', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(result.success).toBe(true);

    const centinels = result.data!.vetoCentinels;
    expect(centinels.length).toBe(7);

    const codes = centinels.map((c) => c.code);
    expect(codes).toContain('SOP-18 / SOP-102');
    expect(codes).toContain('SOP-100 / SOP-101');
    expect(codes).toContain('SOP-95 / SOP-102');
    expect(codes).toContain('SOP-52');
    expect(codes).toContain('SOP-94');
    expect(codes).toContain('SOP-102 BTC');
    expect(codes).toContain('SSoT Whitelist');

    for (const c of centinels) {
      expect(c.reasonWhyHolding.length).toBeGreaterThan(10);
      expect(['ACTIVE_GUARDING', 'PASSING', 'STANDBY']).toContain(c.status);
    }
  });

  it('debe certificar las 4 palancas cuantitativas para maximizar retornos (+221.4R)', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(result.success).toBe(true);

    const alpha = result.data!.alphaOptimization;
    expect(alpha.currentTotalNetR).toBe(97.98);
    expect(alpha.projectedTotalNetR).toBe(221.38);
    expect(alpha.projectedProfitFactor).toBe(2.35);
    expect(alpha.projectedCompoundReturnPct).toBe(4820.0);

    expect(alpha.pillars.length).toBe(4);
    const pillarIds = alpha.pillars.map((p) => p.id);
    expect(pillarIds).toContain('dynamic-tp3-runners');
    expect(pillarIds).toContain('trinity-mega-kelly');
    expect(pillarIds).toContain('asset-incubator-rotation');
    expect(pillarIds).toContain('sop16-freeroll-scalein');
  });

  it('debe rechazar parámetros malformados respetando el esquema de validación', async () => {
    const badRes = await fetchSystemDiagnosticsAction(
      { assetFilter: 'ESTE_ACTIVO_ES_DEMASIADO_LARGO_PARA_EL_CONTRATO_ZOD' },
      mockSession
    );
    expect(badRes.success).toBe(false);
    expect(badRes.error).toContain('Validación de parámetros fallida');
  });

  it('debe auditar la sincronización full-stack (Frontend, Backend, DB y VPS)', async () => {
    const { auditFullStackSyncAction } = await import('@/features');
    const syncRes = await auditFullStackSyncAction({}, mockSession);

    expect(syncRes.success).toBe(true);
    expect(syncRes.data).toBeDefined();

    const data = syncRes.data!;
    expect(data.frontend.canonicalAssetsCount).toBe(13);
    expect(data.frontend.prunedAssetsBlocked).toBe(true);
    expect(data.frontend.fsdArchitecture).toBe('COMPLIANT_STRICT');

    expect(data.backend.canonicalRadarAssetsCount).toBe(13);
    expect(data.backend.dynamicWatchlistDisabled).toBe(true);

    expect(data.database.storageType).toBe('TURSO_LIBSQL_CLOUD');
    expect(data.database.isHealthy).toBe(true);

    expect(data.vps.endpoint).toBe('http://80.65.211.99:8000');
    expect(data.vps.syncDeploymentAction).toContain('git pull origin main');
  });

  it('debe exponer el desglose cuantitativo de los 13 activos y recomendaciones estratégicas', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(result.success).toBe(true);
    expect(result.data?.assetProfiles).toBeDefined();
    expect(result.data?.assetProfiles.length).toBe(13);

    const bnbProfile = result.data?.assetProfiles.find((p) => p.asset === 'BNBUSDT');
    expect(bnbProfile).toBeDefined();
    expect(bnbProfile?.netContributionR).toBeGreaterThan(20);
    expect(bnbProfile?.historicalProfitFactor).toBeGreaterThan(2.5);

    expect(result.data?.strategicRecommendations.length).toBeGreaterThanOrEqual(5);
  });

  it('debe auditar la fase actual de mercado y el escenario análogo del backtest', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(result.success).toBe(true);
    expect(result.data?.regimeScenario).toBeDefined();

    const scenario = result.data!.regimeScenario;
    expect(scenario.currentPhase).toBe('BULL_EXPANSION');
    expect(scenario.confidence).toBeGreaterThan(0.80);
    expect(scenario.historicalMatchesCount).toBeGreaterThan(100);
    expect(scenario.scenarioWinRate).toBeGreaterThan(40);
    expect(scenario.scenarioProfitFactor).toBeGreaterThan(1.50);
    expect(scenario.isAdjustmentRequired).toBe(true);
    expect(scenario.actionableGuidelines.length).toBeGreaterThanOrEqual(3);
  });

  it('debe auditar el orquestador de ciclos multi-año (2020-2026), proyecciones y ajustes requeridos', async () => {
    const { fetchMultiYearCycleAnalysisAction, multiYearCycleQuerySchema } = await import('@/features');
    
    // 1. Schema validation
    const parsed = multiYearCycleQuerySchema.parse({});
    expect(parsed.targetBtcPrice).toBe(84600.0);
    expect(parsed.includeDetailedPhases).toBe(true);

    // 2. Action execution with Zero Trust session
    const res = await fetchMultiYearCycleAnalysisAction({}, mockSession);
    expect(res.success).toBe(true);
    expect(res.data).toBeDefined();

    const data = res.data!;
    expect(data.macroCycleStage).toContain('Consolidación de Rango Alto');
    expect(data.historicalAnalogs.length).toBe(4);

    const cycleIds = data.historicalAnalogs.map((c) => c.cycleId);
    expect(cycleIds).toContain('cycle_2020_2021_post_halving_ath');
    expect(cycleIds).toContain('cycle_2022_2023_bear_to_bull_recovery');
    expect(cycleIds).toContain('cycle_2024_etf_reaccumulation');
    expect(cycleIds).toContain('cycle_2025_2026_pre_expansion');

    // 3. Verificar métricas del ciclo 2020 (similitud alta con consolidación actual)
    const cycle2020 = data.historicalAnalogs.find((c) => c.cycleId === 'cycle_2020_2021_post_halving_ath');
    expect(cycle2020).toBeDefined();
    expect(cycle2020?.strategyPerformance.profitFactor).toBeGreaterThan(1.80);
    expect(cycle2020?.strategyPerformance.netR).toBeGreaterThan(50);
    expect(cycle2020?.similarityScore).toBeGreaterThan(90);

    // 4. Proyecciones futuras y ajustes tácticos
    expect(data.projectedNextPhases.length).toBe(3);
    expect(data.institutionalAdjustments.length).toBe(4);

    const params = data.institutionalAdjustments.map((a) => a.parameter);
    expect(params).toContain('Malla de Salidas en Runners (Post-TP3)');
    expect(params).toContain('Multiplicador Kelly en la Trinidad');
    expect(params).toContain('Veto de Operativa en Centro de Rango');
  });

  it('debe auditar la simulación Monte Carlo (10,000 caminos), VaR 99% y certificación TIER_1_AAA', async () => {
    const { fetchMonteCarloSimulationAction, monteCarloQuerySchema } = await import('@/features');

    // 1. Zod Schema Validation
    const parsed = monteCarloQuerySchema.parse({});
    expect(parsed.iterations).toBe(10000);
    expect(parsed.horizonTrades).toBe(100);

    const custom = monteCarloQuerySchema.parse({ iterations: 5000, horizonTrades: 50 });
    expect(custom.iterations).toBe(5000);
    expect(custom.horizonTrades).toBe(50);

    // 2. Action Execution con Zero Trust
    const res = await fetchMonteCarloSimulationAction({}, mockSession);
    expect(res.success).toBe(true);
    expect(res.data).toBeDefined();

    const mc = res.data!;
    expect(mc.iterations).toBe(10000);
    expect(mc.horizonTrades).toBe(100);
    expect(mc.solvencyGrade).toBe('TIER_1_AAA');
    expect(mc.probabilityOfProfitPct).toBeGreaterThanOrEqual(95.0);
    expect(mc.medianFinalNetR).toBeGreaterThan(50.0);
    expect(mc.var99R).toBeGreaterThan(20.0);
    expect(mc.cvar99R).toBeLessThanOrEqual(mc.var99R);
    expect(mc.riskOfRuinPct).toBeLessThan(5.0);

    // 3. Conos de Equidad
    expect(mc.equityCones.steps.length).toBe(10);
    expect(mc.equityCones.p50.length).toBe(10);
    expect(mc.equityCones.p95.length).toBe(10);

    // Verificar que P95 > P50 > P5 en el último paso
    const lastIdx = mc.equityCones.steps.length - 1;
    expect(mc.equityCones.p95[lastIdx]).toBeGreaterThan(mc.equityCones.p50[lastIdx]);
    expect(mc.equityCones.p50[lastIdx]).toBeGreaterThan(mc.equityCones.p5[lastIdx]);
  });
});


