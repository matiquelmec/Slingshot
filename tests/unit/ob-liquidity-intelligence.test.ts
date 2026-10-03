import { describe, it, expect } from 'vitest';
import {
  orderBlockDetailSchema,
  nearestLiquidityClusterSchema,
  obLiquidityAuditReportSchema,
  CANONICAL_AUDITED_UNIVERSE,
} from '@/entities/signal';
import { fetchSystemDiagnosticsAction } from '@/features/system-diagnostics/actions';

describe('SOP-112: OrderBlock and Liquidity Intelligence Contracts', () => {
  it('should validate a valid OrderBlockDetail contract', () => {
    const validOb = {
      top: 85500.0,
      bottom: 84200.0,
      volumeRatio: 2.35,
      strengthScore: 92.5,
      touchCount: 0,
      isVirgin: true,
      statusLabel: 'TIER_1_VIRGIN_ELITE' as const,
    };
    const res = orderBlockDetailSchema.safeParse(validOb);
    expect(res.success).toBe(true);
  });

  it('should validate nearestLiquidityClusterSchema with magnetic attributes', () => {
    const validCluster = {
      price: 86500.0,
      type: 'SHORT_LIQ' as const,
      strength: 94,
      distancePct: 1.85,
      isMagnetic: true,
    };
    const res = nearestLiquidityClusterSchema.safeParse(validCluster);
    expect(res.success).toBe(true);
  });

  it('should validate obLiquidityAuditReportSchema structure', () => {
    const validReport = {
      asset: 'BTCUSDT',
      activeObsCount: 3,
      virginObsCount: 2,
      dominantOb: {
        top: 85500.0,
        bottom: 84200.0,
        volumeRatio: 2.15,
        strengthScore: 92.5,
        touchCount: 0,
        isVirgin: true,
        statusLabel: 'TIER_1_VIRGIN_ELITE' as const,
      },
      nearestLiqCluster: {
        price: 86500.0,
        type: 'SHORT_LIQ' as const,
        strength: 92,
        distancePct: 1.89,
        isMagnetic: true,
      },
      hasDualConfluence: true,
      confluenceScoreBonus: 5.0,
      weightingRating: 'OPTIMA_INSTITUTIONAL' as const,
      recommendation: 'DISPARO_SNIPER_ALTA_CONVICCION',
    };

    const res = obLiquidityAuditReportSchema.safeParse(validReport);
    expect(res.success).toBe(true);
  });

  it('should return all 13 canonical assets in obLiquidityAudit from fetchSystemDiagnosticsAction', async () => {
    const mockSession = {
      userId: 'test_user_sop112',
      tenantId: 'test_tenant_sop112',
      role: 'admin' as const,
      email: 'admin@slingshot.internal',
    };

    const res = await fetchSystemDiagnosticsAction({}, mockSession);
    expect(res.success).toBe(true);
    expect(res.data?.obLiquidityAudit).toBeDefined();

    const audits = res.data!.obLiquidityAudit;
    expect(audits.length).toBe(13);

    // Cada activo debe pertenecer al Universo Canónico SSoT
    audits.forEach((a) => {
      expect((CANONICAL_AUDITED_UNIVERSE as readonly string[]).includes(a.asset)).toBe(true);
      expect(a.weightingRating).toBeDefined();
      expect(a.activeObsCount).toBeGreaterThanOrEqual(0);
      expect(a.confluenceScoreBonus).toBeGreaterThanOrEqual(0);
    });
  });
});
