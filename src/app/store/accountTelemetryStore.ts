'use client';

import { create } from 'zustand';
import { AccountProfileConfig, AccountProfileType, FtmoPhase } from '../../entities/signal/types';
import { getApiBaseUrl } from '../utils/apiUrl';
import { isBitunixCoreVisible, isFtmoMt5Visible } from '@/shared';

export interface FtmoAuditAssetItem {
    symbol: string;
    timeframe: string;
    archetype: string;
    cluster: string;
    train_pf: number;
    oos_pf: number;
    oos_mean_r: number;
    oos_n: number;
    oos_total_r: number;
}

interface AccountTelemetryState {
    selectedProfile: AccountProfileType;
    ftmoPhase: FtmoPhase;
    bitunixConnected: boolean;
    bitunixEquity: number;
    bitunixRiskPct: number;
    bitunixRiskUsd: number;
    ftmoConnected: boolean;
    ftmoEquity: number;
    ftmoDailyLossUsd: number;
    ftmoDailyDdPct: number;
    ftmoLockout: boolean;
    ftmoAuditPortfolio: FtmoAuditAssetItem[];
    lastSyncTs: number;
    isSyncing: boolean;
    setSelectedProfile: (profile: AccountProfileType) => void;
    setFtmoPhase: (phase: FtmoPhase) => void;
    syncAccountTelemetry: (force?: boolean) => Promise<void>;
    getResolvedBitunixConfig: () => AccountProfileConfig;
    getResolvedFtmoConfig: (overrideSize?: number, overridePhase?: FtmoPhase) => AccountProfileConfig;
}

const FTMO_RISK_BY_PHASE: Record<FtmoPhase, number> = {
    PHASE_1: 0.75,
    PHASE_2: 0.50,
    FUNDED: 0.35,
};

export const useAccountTelemetryStore = create<AccountTelemetryState>((set, get) => ({
    selectedProfile: isFtmoMt5Visible() ? 'FTMO_100K' : 'PERSONAL_250K',
    ftmoPhase: 'PHASE_1',
    bitunixConnected: false,
    bitunixEquity: 0,
    bitunixRiskPct: 2.5,
    bitunixRiskUsd: 0,
    ftmoConnected: false,
    ftmoEquity: 100000,
    ftmoDailyLossUsd: 0,
    ftmoDailyDdPct: 0,
    ftmoLockout: false,
    ftmoAuditPortfolio: [],
    lastSyncTs: 0,
    isSyncing: false,

    setSelectedProfile: (profile) => set({ selectedProfile: profile }),
    setFtmoPhase: (phase) => set({ ftmoPhase: phase }),

    syncAccountTelemetry: async (force = false) => {
        const now = Date.now();
        const state = get();
        if (state.isSyncing) return;
        if (!force && now - state.lastSyncTs < 5000) return;

        set({ isSyncing: true });
        try {
            const baseUrl = getApiBaseUrl();
            const [bitunixRes, guardianRes, auditRes] = await Promise.all([
                isBitunixCoreVisible()
                    ? fetch(`${baseUrl}/api/v1/bitunix/telemetry`, { cache: 'no-store' }).catch(() => null)
                    : Promise.resolve(null),
                isFtmoMt5Visible()
                    ? fetch(`${baseUrl}/api/v1/ftmo/guardian`, { cache: 'no-store' }).catch(() => null)
                    : Promise.resolve(null),
                fetch(`${baseUrl}/api/v1/ftmo/universe-audit`, { cache: 'no-store' }).catch(() => null),
            ]);

            const updates: Partial<AccountTelemetryState> = { lastSyncTs: Date.now() };

            if (bitunixRes && bitunixRes.ok) {
                const b = await bitunixRes.json();
                const eq = Number(b?.equity || 0);
                const rPct = Number(b?.risk_config?.risk_pct || 2.5);
                const rUsd = Number(b?.risk_config?.risk_usd_per_trade || (eq * (rPct / 100)));
                updates.bitunixConnected = Boolean(b?.connected);
                if (eq > 0) {
                    updates.bitunixEquity = eq;
                    updates.bitunixRiskPct = rPct;
                    updates.bitunixRiskUsd = Math.round(rUsd * 100) / 100;
                }
            }

            if (guardianRes && guardianRes.ok) {
                const g = await guardianRes.json();
                updates.ftmoConnected = true;
                updates.ftmoEquity = Number(g?.current_equity || 100000);
                updates.ftmoDailyLossUsd = Number(g?.daily_loss_usd || 0);
                updates.ftmoDailyDdPct = Number(g?.daily_dd_pct || 0);
                updates.ftmoLockout = Boolean(g?.is_daily_lockout);
            }

            if (auditRes && auditRes.ok) {
                const a = await auditRes.json();
                if (Array.isArray(a?.selected_portfolio)) {
                    updates.ftmoAuditPortfolio = a.selected_portfolio;
                }
            }

            set(updates);
        } finally {
            set({ isSyncing: false });
        }
    },

    getResolvedBitunixConfig: () => {
        const s = get();
        const hasLive = isBitunixCoreVisible() && s.bitunixEquity > 0;
        const accountSize = hasLive ? Math.round(s.bitunixEquity * 100) / 100 : 10000;
        const riskPct = hasLive ? s.bitunixRiskPct : 2.5;
        const riskUsd = hasLive
            ? s.bitunixRiskUsd
            : Math.round(accountSize * (riskPct / 100) * 100) / 100;
        return {
            id: 'PERSONAL_250K',
            name: hasLive ? 'Bitunix Principal (En Vivo)' : 'Simulador Bitunix Core (2.50%)',
            accountSize,
            riskPct,
            riskUsd,
            platform: 'BITUNIX',
            isFtmo: false,
        };
    },

    getResolvedFtmoConfig: (overrideSize, overridePhase) => {
        const s = get();
        const phase = overridePhase ?? s.ftmoPhase;
        const sizeFromProfile =
            s.selectedProfile === 'FTMO_50K'
                ? 50000
                : s.selectedProfile === 'FTMO_200K'
                    ? 200000
                    : 100000;
        const accountSize = overrideSize ?? sizeFromProfile;
        const riskPct = FTMO_RISK_BY_PHASE[phase];
        const riskUsd = Math.round(accountSize * (riskPct / 100) * 100) / 100;
        const id: AccountProfileType =
            accountSize === 50000 ? 'FTMO_50K' : accountSize === 200000 ? 'FTMO_200K' : 'FTMO_100K';

        return {
            id,
            name: `FTMO Swing $${accountSize / 1000}k`,
            accountSize,
            riskPct,
            riskUsd,
            platform: 'MT5',
            isFtmo: true,
            phase,
            targetProfitPct: phase === 'PHASE_1' ? 10.0 : phase === 'PHASE_2' ? 5.0 : undefined,
            targetProfitUsd: phase === 'PHASE_1' ? accountSize * 0.10 : phase === 'PHASE_2' ? accountSize * 0.05 : undefined,
            maxDailyLossPct: 5.0,
            maxDailyLossUsd: accountSize * 0.05,
            maxTotalLossPct: 10.0,
            maxTotalLossUsd: accountSize * 0.10,
        };
    },
}));
