import { describe, it, expect } from 'vitest';
import { assertTenantOwnership, scopeToUser } from '@/shared/db/tenantGuard';
import { requireUserSession, AuthorizationError, AuthenticationError, UserSession } from '@/shared/auth';

describe('Multi-Tenant Security Isolation Guard', () => {
  const validSession: UserSession = {
    userId: 'user-alpha-001',
    tenantId: 'tenant-inst-999',
    role: 'trader',
    email: 'trader@institutional.internal',
  };

  const attackerSession: UserSession = {
    userId: 'user-mallory-666',
    tenantId: 'tenant-evil-111',
    role: 'trader',
    email: 'mallory@external.net',
  };

  it('allows access when session matches entity owner and tenant', () => {
    const signalEntity = {
      id: 'sig-101',
      userId: 'user-alpha-001',
      tenantId: 'tenant-inst-999',
    };

    const result = assertTenantOwnership(signalEntity, validSession);
    expect(result).toBe(signalEntity);
  });

  it('blocks access and throws AuthorizationError on user ID mismatch (IDOR attack)', () => {
    const targetEntity = {
      id: 'sig-101',
      userId: 'user-alpha-001',
      tenantId: 'tenant-inst-999',
    };

    expect(() => {
      assertTenantOwnership(targetEntity, attackerSession);
    }).toThrow(AuthorizationError);
  });

  it('blocks access if tenantId mismatches even if userId matches (cross-tenant breach)', () => {
    const targetEntity = {
      id: 'sig-101',
      userId: 'user-alpha-001',
      tenantId: 'tenant-diff-888',
    };

    expect(() => {
      assertTenantOwnership(targetEntity, validSession);
    }).toThrow(AuthorizationError);
  });

  it('enforces session requirement and rejects unauthenticated caller', async () => {
    await expect(requireUserSession(null)).rejects.toThrow(AuthenticationError);
  });

  it('generates correct scoped query parameter mapping', () => {
    const scoped = scopeToUser('sig-777', validSession);
    expect(scoped).toEqual({
      targetId: 'sig-777',
      userId: 'user-alpha-001',
      tenantId: 'tenant-inst-999',
    });
  });
});
