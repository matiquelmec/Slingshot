import { describe, it, expect } from 'vitest';
import {
  createAccountInputSchema,
  toggleAccountInputSchema,
  deleteAccountInputSchema,
  accountItemSchema,
  fetchAccountsAction,
} from '@/features';
import { UserSession } from '@/shared';

describe('Features: Multi-Account Bitunix Dispatcher Slice (FSD & Zero Trust)', () => {
  const mockSession: UserSession = {
    userId: 'user_multi_account_lead',
    tenantId: 'tenant_institutional_master',
    email: 'trader@slingshot.internal',
    role: 'trader',
  };

  it('debe validar esquemas de entrada para registrar cuentas secundarias con Zod', () => {
    const valid = createAccountInputSchema.parse({
      account_id: 'client_inversor_2',
      label: 'Cuenta Secundaria VIP',
      api_key: 'bitunix_api_key_valid_1234567890',
      secret_key: 'bitunix_secret_key_valid_1234567890',
      risk_pct: 0.025,
      max_notional_mult: 5.0,
      dry_run: false,
    });

    expect(valid.account_id).toBe('client_inversor_2');
    expect(valid.risk_pct).toBe(0.025);
    expect(valid.dry_run).toBe(false);
  });

  it('debe rechazar IDs de cuenta con caracteres no permitidos o longitud insuficiente', () => {
    expect(() =>
      createAccountInputSchema.parse({
        account_id: 'ab', // menos de 3 caracteres
        label: 'Cuenta Test',
        api_key: 'short',
        secret_key: 'short',
      })
    ).toThrow();

    expect(() =>
      createAccountInputSchema.parse({
        account_id: 'cuenta con espacios!',
        label: 'Cuenta Test',
        api_key: '123456789012',
        secret_key: '123456789012',
      })
    ).toThrow();
  });

  it('debe validar esquemas de toggle y delete con Zod', () => {
    const toggle = toggleAccountInputSchema.parse({
      account_id: 'client_2',
      enabled: false,
    });
    expect(toggle.enabled).toBe(false);

    const del = deleteAccountInputSchema.parse({
      account_id: 'client_2',
    });
    expect(del.account_id).toBe('client_2');
  });

  it('debe validar la estructura de una cuenta enmascarada (AccountItem)', () => {
    const item = accountItemSchema.parse({
      account_id: 'primary',
      label: 'Cuenta Principal (.env)',
      api_key: 'abcd...wxyz',
      enabled: true,
      risk_pct: 0.025,
      max_notional_mult: 5.0,
      dry_run: false,
      is_primary: true,
      current_balance_usdt: 746.38,
      projected_trade_risk_usd: 18.66,
    });

    expect(item.is_primary).toBe(true);
    expect(item.current_balance_usdt).toBe(746.38);
    expect(item.projected_trade_risk_usd).toBe(18.66);
  });

  it('fetchAccountsAction debe retornar la cuenta principal (.env) en fallback seguro', async () => {
    const res = await fetchAccountsAction(mockSession);
    expect(res.success).toBe(true);
    expect(res.data).toBeDefined();
    expect(res.data!.length).toBeGreaterThanOrEqual(1);

    const primary = res.data!.find((a) => a.is_primary);
    expect(primary).toBeDefined();
    expect(primary?.account_id).toBe('primary');
    expect(primary?.enabled).toBe(true);
  });
});
