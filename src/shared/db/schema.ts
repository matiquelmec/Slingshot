import { relations } from 'drizzle-orm';
import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

// ============================================================================
// 1. TENANTS TABLE (Multi-Tenant Core)
// ============================================================================
export const tenants = sqliteTable('tenants', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  name: text('name').notNull(),
  tier: text('tier', { enum: ['starter', 'pro', 'institutional'] })
    .notNull()
    .default('starter'),
  maxConcurrentPositions: integer('max_concurrent_positions')
    .notNull()
    .default(3),
  status: text('status', { enum: ['active', 'suspended', 'archived'] })
    .notNull()
    .default('active'),
  createdAt: integer('created_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
  updatedAt: integer('updated_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
});

// ============================================================================
// 2. USERS TABLE
// ============================================================================
export const users = sqliteTable('users', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  tenantId: text('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  email: text('email').notNull().unique(),
  role: text('role', { enum: ['admin', 'trader', 'viewer'] })
    .notNull()
    .default('trader'),
  createdAt: integer('created_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
  updatedAt: integer('updated_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
});

// ============================================================================
// 3. SIGNALS TABLE (Quantitative Signals & Telemetry)
// ============================================================================
export const signals = sqliteTable('signals', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  tenantId: text('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: text('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  asset: text('asset').notNull(),
  direction: text('direction', { enum: ['LONG', 'SHORT'] }).notNull(),
  timeframe: text('timeframe').notNull().default('15m'),
  entryPrice: real('entry_price').notNull(),
  stopLoss: real('stop_loss').notNull(),
  takeProfit1: real('take_profit_1'),
  takeProfit2: real('take_profit_2'),
  takeProfit3: real('take_profit_3'),
  confluenceScore: real('confluence_score').notNull().default(0),
  kerValue: real('ker_value').notNull().default(0),
  status: text('status', {
    enum: ['PENDING', 'TRIGGERED', 'FILLED', 'CANCELLED', 'EXPIRED'],
  })
    .notNull()
    .default('PENDING'),
  createdAt: integer('created_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
});

// ============================================================================
// 4. TRADES TABLE (Executed Positions & PnL History)
// ============================================================================
export const trades = sqliteTable('trades', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  tenantId: text('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: text('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  signalId: text('signal_id').references(() => signals.id, {
    onDelete: 'set null',
  }),
  symbol: text('symbol').notNull(),
  side: text('side', { enum: ['BUY', 'SELL'] }).notNull(),
  entryPrice: real('entry_price').notNull(),
  exitPrice: real('exit_price'),
  quantity: real('quantity').notNull().default(0),
  pnl: real('pnl').default(0),
  pnlPercent: real('pnl_percent').default(0),
  status: text('status', { enum: ['OPEN', 'CLOSED', 'CANCELLED'] })
    .notNull()
    .default('OPEN'),
  createdAt: integer('created_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
  closedAt: integer('closed_at', { mode: 'timestamp' }),
});

// ============================================================================
// 5. RISK CONFIGS TABLE (Per-Tenant / User Circuit Breaker Rules)
// ============================================================================
export const riskConfigs = sqliteTable('risk_configs', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  tenantId: text('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: text('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  maxDrawdownDaily: real('max_drawdown_daily').notNull().default(0.05),
  maxRiskPerTradePct: real('max_risk_per_trade_pct').notNull().default(0.01),
  minRr: real('min_rr').notNull().default(2.5),
  isCircuitBreakerActive: integer('is_circuit_breaker_active', {
    mode: 'boolean',
  })
    .notNull()
    .default(false),
  updatedAt: integer('updated_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
});

// ============================================================================
// 6. ACCOUNTS TABLE (Exchange Credentials & Balance Segregation)
// ============================================================================
export const accounts = sqliteTable('accounts', {
  id: text('id')
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  tenantId: text('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: text('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  exchange: text('exchange').notNull().default('bitunix'),
  apiKeyEncrypted: text('api_key_encrypted'),
  secretEncrypted: text('secret_encrypted'),
  currentBalance: real('current_balance').notNull().default(0),
  createdAt: integer('created_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
  updatedAt: integer('updated_at', { mode: 'timestamp' })
    .notNull()
    .$defaultFn(() => new Date()),
});

// ============================================================================
// 7. RELATIONS DEFINITIONS (Drizzle ORM Relational Queries)
// ============================================================================
export const tenantsRelations = relations(tenants, ({ many }) => ({
  users: many(users),
  signals: many(signals),
  trades: many(trades),
  riskConfigs: many(riskConfigs),
  accounts: many(accounts),
}));

export const usersRelations = relations(users, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [users.tenantId],
    references: [tenants.id],
  }),
  signals: many(signals),
  trades: many(trades),
  riskConfigs: many(riskConfigs),
  accounts: many(accounts),
}));

export const signalsRelations = relations(signals, ({ one, many }) => ({
  tenant: one(tenants, {
    fields: [signals.tenantId],
    references: [tenants.id],
  }),
  user: one(users, {
    fields: [signals.userId],
    references: [users.id],
  }),
  trades: many(trades),
}));

export const tradesRelations = relations(trades, ({ one }) => ({
  tenant: one(tenants, {
    fields: [trades.tenantId],
    references: [tenants.id],
  }),
  user: one(users, {
    fields: [trades.userId],
    references: [users.id],
  }),
  signal: one(signals, {
    fields: [trades.signalId],
    references: [signals.id],
  }),
}));

export const riskConfigsRelations = relations(riskConfigs, ({ one }) => ({
  tenant: one(tenants, {
    fields: [riskConfigs.tenantId],
    references: [tenants.id],
  }),
  user: one(users, {
    fields: [riskConfigs.userId],
    references: [users.id],
  }),
}));

export const accountsRelations = relations(accounts, ({ one }) => ({
  tenant: one(tenants, {
    fields: [accounts.tenantId],
    references: [tenants.id],
  }),
  user: one(users, {
    fields: [accounts.userId],
    references: [users.id],
  }),
}));

// ============================================================================
// 8. INFERRED DOMAIN TYPES
// ============================================================================
export type TenantRecord = typeof tenants.$inferSelect;
export type NewTenantRecord = typeof tenants.$inferInsert;

export type UserRecord = typeof users.$inferSelect;
export type NewUserRecord = typeof users.$inferInsert;

export type SignalRecord = typeof signals.$inferSelect;
export type NewSignalRecord = typeof signals.$inferInsert;

export type TradeRecord = typeof trades.$inferSelect;
export type NewTradeRecord = typeof trades.$inferInsert;

export type RiskConfigRecord = typeof riskConfigs.$inferSelect;
export type NewRiskConfigRecord = typeof riskConfigs.$inferInsert;

export type AccountRecord = typeof accounts.$inferSelect;
export type NewAccountRecord = typeof accounts.$inferInsert;
