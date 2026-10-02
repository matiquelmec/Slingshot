import { createClient } from '@libsql/client';
import { drizzle } from 'drizzle-orm/libsql';
import * as schema from './schema';

const DEFAULT_TURSO_URL = 'libsql://slingshot-slingshotagente.aws-ap-northeast-1.turso.io';
const DEFAULT_TURSO_TOKEN = 'eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTA5NTQwNDEsImlkIjoiMDFhMGZkMmQtY2EwMS03NTNiLTliNWMtMGE2MGQzYTM4NWJiIiwia2lkIjoicUMwQ0plVkY2amwzUkE1dlNjbEJXbG5XRXNoNHpyZURUbUE0bDBqUm1NQSIsInJpZCI6IjM5NzMxMDAyLTg3YzYtNGUyOS05NDc2LTZjZDZmM2VkNTViNSJ9.vvPQtU5zulZzdYMY2G70VyOoyKDvGrVXpbp2QiPhPJHp2Y5oVTN1XNhE0vRn8qzD4UrLhr2OR1TpLqHs_i59Dg';

// En Vercel / Web standard APIs, 'file:' no está soportado. Usamos siempre el endpoint institucional de Turso Cloud.
const rawUrl = process.env.TURSO_DATABASE_URL || DEFAULT_TURSO_URL;
const isWebOrVercel = typeof window !== 'undefined' || !!process.env.VERCEL || !rawUrl.startsWith('file:');
const url = isWebOrVercel && rawUrl.startsWith('file:') ? DEFAULT_TURSO_URL : rawUrl;
const authToken = process.env.TURSO_AUTH_TOKEN || (url === DEFAULT_TURSO_URL ? DEFAULT_TURSO_TOKEN : undefined);

export const client = createClient({
  url,
  authToken: url.startsWith('file:') ? undefined : authToken,
});

export const db = drizzle(client, { schema });

export * from './schema';
export * from './tenantGuard';
