import { describe, it, expect } from 'vitest';
import {
  tenants,
  users,
  signals,
  trades,
  riskConfigs,
  accounts,
  db,
  client,
  assertTenantOwnership,
  scopeToUser,
} from '@/shared';
import { and, eq } from 'drizzle-orm';

describe('Turso & Drizzle Multi-Tenant DB Integration', () => {
  it('instantiates the LibSQL client and Drizzle ORM instance with schema', () => {
    expect(client).toBeDefined();
    expect(db).toBeDefined();
    expect(db.query).toBeDefined();
    expect(db.query.tenants).toBeDefined();
    expect(db.query.users).toBeDefined();
    expect(db.query.signals).toBeDefined();
    expect(db.query.trades).toBeDefined();
  });

  it('defines all required multi-tenant relational tables', () => {
    expect(tenants).toBeDefined();
    expect(users).toBeDefined();
    expect(signals).toBeDefined();
    expect(trades).toBeDefined();
    expect(riskConfigs).toBeDefined();
    expect(accounts).toBeDefined();

    // Verify column definitions exist
    expect(tenants.id).toBeDefined();
    expect(tenants.name).toBeDefined();
    expect(tenants.tier).toBeDefined();

    expect(users.id).toBeDefined();
    expect(users.tenantId).toBeDefined();
    expect(users.email).toBeDefined();

    expect(signals.id).toBeDefined();
    expect(signals.tenantId).toBeDefined();
    expect(signals.userId).toBeDefined();
    expect(signals.confluenceScore).toBeDefined();

    expect(trades.id).toBeDefined();
    expect(trades.tenantId).toBeDefined();
    expect(trades.userId).toBeDefined();
    expect(trades.pnl).toBeDefined();

    expect(riskConfigs.id).toBeDefined();
    expect(riskConfigs.isCircuitBreakerActive).toBeDefined();

    expect(accounts.id).toBeDefined();
    expect(accounts.exchange).toBeDefined();
  });

  it('builds canonical multi-tenant anti-IDOR SQL queries as required by AGENTS.md', () => {
    const mockSession = {
      userId: 'user-apex-77',
      tenantId: 'tenant-inst-01',
      role: 'trader' as const,
      email: 'trader@slingshot.trade',
    };
    const targetSignalId = 'sig-uuid-1234';

    // Build the query via Drizzle query builder
    const query = db
      .select()
      .from(signals)
      .where(
        and(
          eq(signals.id, targetSignalId),
          eq(signals.userId, mockSession.userId),
          eq(signals.tenantId, mockSession.tenantId)
        )
      );

    const sqlObj = query.toSQL();
    expect(sqlObj.sql).toContain('select');
    expect(sqlObj.sql).toContain('signals');
    expect(sqlObj.sql).toContain('where');
    expect(sqlObj.params).toContain(targetSignalId);
    expect(sqlObj.params).toContain(mockSession.userId);
    expect(sqlObj.params).toContain(mockSession.tenantId);
  });

  it('enforces tenant ownership assertions using tenantGuard', () => {
    const session = {
      userId: 'user-1',
      tenantId: 'tenant-alpha',
      role: 'trader' as const,
      email: 'u1@slingshot.trade',
    };

    const validEntity = {
      id: 'entity-1',
      userId: 'user-1',
      tenantId: 'tenant-alpha',
    };

    expect(() => assertTenantOwnership(validEntity, session)).not.toThrow();

    const crossUserEntity = {
      id: 'entity-2',
      userId: 'user-2',
      tenantId: 'tenant-alpha',
    };

    expect(() => assertTenantOwnership(crossUserEntity, session)).toThrow(
      /Tenant violation/
    );

    const crossTenantEntity = {
      id: 'entity-3',
      userId: 'user-1',
      tenantId: 'tenant-beta',
    };

    expect(() => assertTenantOwnership(crossTenantEntity, session)).toThrow(
      /Tenant isolation mismatch/
    );
  });

  it('correctly constructs tenant scope conditions with scopeToUser', () => {
    const session = {
      userId: 'usr-99',
      tenantId: 'tnt-apex',
      role: 'admin' as const,
      email: 'admin@admin.trade',
    };

    const scope = scopeToUser('target-rec-01', session);
    expect(scope).toEqual({
      targetId: 'target-rec-01',
      userId: 'usr-99',
      tenantId: 'tnt-apex',
    });
  });

  it(
    'audits database capacity and health metrics via fetchDatabaseHealthAction',
    async () => {
      const { fetchDatabaseHealthAction } = await import('@/features/positions-tracker/actions');
      const health = await fetchDatabaseHealthAction();

      expect(health.success).toBe(true);
      expect(health.data).toBeDefined();
      if (health.data) {
        expect(health.data.storageType).toBe('TURSO_LIBSQL_CLOUD');
        expect(health.data.tierLimitMb).toBe(9216);
        expect(health.data.pageSizeBytes).toBeGreaterThan(0);
        expect(health.data.pageCount).toBeGreaterThan(0);
        expect(health.data.usagePercentage).toBeLessThan(1.0); // Less than 1% usage
        expect(health.data.isHealthy).toBe(true);
        expect(health.data.status).toBe('EXCELLENT');
        expect(health.data.tableCounts).toBeDefined();
        expect(health.data.tableCounts.trades).toBeGreaterThanOrEqual(0);
      }
    },
    15000
  );
});


