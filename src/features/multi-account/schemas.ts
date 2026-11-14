import { z } from 'zod';

export const accountItemSchema = z.object({
  account_id: z.string(),
  label: z.string(),
  api_key: z.string(),
  secret_key: z.string().optional(),
  enabled: z.boolean(),
  risk_pct: z.number(),
  max_notional_mult: z.number(),
  dry_run: z.boolean(),
  is_primary: z.boolean(),
  current_balance_usdt: z.number().default(0),
  projected_trade_risk_usd: z.number().default(0),
  created_at: z.number().optional(),
});

export type AccountItem = z.infer<typeof accountItemSchema>;

export const createAccountInputSchema = z.object({
  account_id: z
    .string()
    .min(3, 'El ID debe tener al menos 3 caracteres')
    .max(30, 'El ID no puede superar 30 caracteres')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Solo caracteres alfanuméricos, guiones o guiones bajos'),
  label: z.string().min(2, 'La etiqueta debe tener al menos 2 caracteres').max(50),
  api_key: z.string().min(10, 'API Key inválida o demasiado corta'),
  secret_key: z.string().min(10, 'Secret Key inválida o demasiado corta'),
  risk_pct: z.number().min(0.005).max(0.10).default(0.025),
  max_notional_mult: z.number().min(1.0).max(10.0).default(5.0),
  dry_run: z.boolean().default(false),
});

export type CreateAccountInput = z.infer<typeof createAccountInputSchema>;

export const toggleAccountInputSchema = z.object({
  account_id: z.string(),
  enabled: z.boolean(),
});

export type ToggleAccountInput = z.infer<typeof toggleAccountInputSchema>;

export const deleteAccountInputSchema = z.object({
  account_id: z.string(),
});

export type DeleteAccountInput = z.infer<typeof deleteAccountInputSchema>;
