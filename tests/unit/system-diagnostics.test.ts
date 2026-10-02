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

  it('debe certificar las 4 palancas cuantitativas para maximizar retornos (+164.2R)', async () => {
    const result = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(result.success).toBe(true);

    const alpha = result.data!.alphaOptimization;
    expect(alpha.currentTotalNetR).toBe(97.98);
    expect(alpha.projectedTotalNetR).toBe(164.20);
    expect(alpha.projectedProfitFactor).toBeGreaterThan(alpha.currentProfitFactor);
    expect(alpha.projectedCompoundReturnPct).toBeGreaterThan(alpha.currentCompoundReturnPct);

    expect(alpha.pillars.length).toBe(4);
    const pillarIds = alpha.pillars.map((p) => p.id);
    expect(pillarIds).toContain('dynamic-tp3-runners');
    expect(pillarIds).toContain('sop16-freeroll-scalein');
    expect(pillarIds).toContain('kelly-a-plus-boost');
    expect(pillarIds).toContain('proportional-macro-smoothing');
  });

  it('debe rechazar parámetros malformados respetando el esquema de validación', async () => {
    const badRes = await fetchSystemDiagnosticsAction(
      { assetFilter: 'ESTE_ACTIVO_ES_DEMASIADO_LARGO_PARA_EL_CONTRATO_ZOD' },
      mockSession
    );
    expect(badRes.success).toBe(false);
    expect(badRes.error).toContain('Validación de parámetros fallida');
  });
});
