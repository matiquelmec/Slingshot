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

/**
 * Validates and extracts the current user session.
 * In a real Next.js Server Action / API route, this inspects auth tokens or cookies.
 */
export async function requireUserSession(mockSession?: UserSession | null): Promise<UserSession> {
  // In production, integrate with NextAuth / Supabase / Clerk / IronSession
  const session = mockSession;
  if (!session || !session.userId || !session.tenantId) {
    throw new AuthenticationError();
  }
  return session;
}
