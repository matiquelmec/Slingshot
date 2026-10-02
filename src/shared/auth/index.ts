export interface UserSession {
  userId: string;
  tenantId: string;
  role: 'admin' | 'trader' | 'viewer';
  email: string;
}

export class AuthenticationError extends Error {
  constructor(message = 'Authentication required: No valid session found') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class AuthorizationError extends Error {
  constructor(message = 'Forbidden: Tenant isolation breach detected') {
    super(message);
    this.name = 'AuthorizationError';
  }
}

export const DEFAULT_SOVEREIGN_SESSION: UserSession = {
  userId: 'user-apex-trader',
  tenantId: 'tenant-sovereign-apex',
  role: 'admin',
  email: 'trader@slingshot.internal',
};

/**
 * Validates and extracts the current user session.
 * En modo single-tenant institucional sovereign, provee la sesión default si no se pasa cookie o mockSession.
 */
export async function requireUserSession(mockSession?: UserSession | null): Promise<UserSession> {
  if (mockSession === null) {
    throw new AuthenticationError();
  }
  const session = mockSession ?? DEFAULT_SOVEREIGN_SESSION;
  if (!session || !session.userId || !session.tenantId) {
    throw new AuthenticationError();
  }
  return session;
}
