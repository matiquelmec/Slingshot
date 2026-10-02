import { AuthorizationError, UserSession } from '../auth';

export interface MultiTenantEntity {
  id: string;
  userId: string;
  tenantId?: string;
}

/**
 * Creates a scoped query condition ensuring tenant/user isolation.
 * Prevents horizontal privilege escalation (IDOR).
 */
export function scopeToUser<T extends { id: string }>(
  targetId: string,
  session: UserSession
): { targetId: string; userId: string; tenantId: string } {
  if (!session.userId || !session.tenantId) {
    throw new AuthorizationError('Invalid session for tenant isolation query');
  }

  return {
    targetId,
    userId: session.userId,
    tenantId: session.tenantId,
  };
}

/**
 * Validates that an existing entity belongs to the session user/tenant.
 */
export function assertTenantOwnership<T extends MultiTenantEntity>(
  entity: T | null | undefined,
  session: UserSession
): T {
  if (!entity) {
    throw new AuthorizationError('Entity not found');
  }

  if (entity.userId !== session.userId) {
    throw new AuthorizationError(
      `Tenant violation: Entity owned by ${entity.userId}, accessed by ${session.userId}`
    );
  }

  if (entity.tenantId && session.tenantId && entity.tenantId !== session.tenantId) {
    throw new AuthorizationError(
      `Tenant isolation mismatch: Expected tenant ${session.tenantId}, got ${entity.tenantId}`
    );
  }

  return entity;
}
