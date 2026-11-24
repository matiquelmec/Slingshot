import { create } from 'zustand';

export type IndicatorCategory = 'SSOT_CORE' | 'STRUCTURE' | 'LIQUIDITY';
export type ChartPresetId = 'CLEAN' | 'SSOT_STRATEGY' | 'LIQUIDITY_FLOW' | 'FULL_AUDIT';

export interface Indicator {
    id: string;
    label: string;
    sublabel: string;
    enabled: boolean;
    color: string;
    category: IndicatorCategory;
}

export const INDICATORS_STORAGE_KEY = 'slingshot_chart_indicators_v2';

export const CHART_PRESETS: Record<
    ChartPresetId,
    { id: ChartPresetId; label: string; description: string; enabledIds: string[] }
> = {
    CLEAN: {
        id: 'CLEAN',
        label: 'Limpio',
        description: 'Solo velas y flujo de volumen',
        enabledIds: ['volume'],
    },
    SSOT_STRATEGY: {
        id: 'SSOT_STRATEGY',
        label: 'Estrategia SSoT',
        description: 'EMA 200, AVWAP, SMC, FVG, Setup R:R y Sesiones',
        enabledIds: ['ema200', 'avwap', 'active_setup', 'smc', 'fvg', 'session', 'volume'],
    },
    LIQUIDITY_FLOW: {
        id: 'LIQUIDITY_FLOW',
        label: 'Liquidez',
        description: 'AVWAP, Heatmap, Rekt Radar, Value Area y Traps',
        enabledIds: ['avwap', 'heatmap', 'liquidations', 'value_area', 'traps', 'volume'],
    },
    FULL_AUDIT: {
        id: 'FULL_AUDIT',
        label: 'Auditoría',
        description: 'Todas las capas técnicas habilitadas',
        enabledIds: [
            'ema200',
            'avwap',
            'active_setup',
            'smc',
            'fvg',
            'sr',
            'session',
            'liquidations',
            'fibonacci',
            'volume',
            'heatmap',
            'value_area',
            'traps',
            'williams_oops',
        ],
    },
};

export const INDICATOR_DEFAULTS: Indicator[] = [
    // SSoT Core (Active live strategy alignment)
    { id: 'ema200', label: 'EMA 200 Institucional', sublabel: 'Tendencia macro y filtro direccional', enabled: true, color: '#38BDF8', category: 'SSOT_CORE' },
    { id: 'avwap', label: 'Session AVWAP (UTC)', sublabel: 'Precio justo diario 00:00 UTC (SOP-114)', enabled: true, color: '#F59E0B', category: 'SSOT_CORE' },
    { id: 'active_setup', label: 'Setup Activo R:R', sublabel: 'Entry, SL, Fast BE y TP1/TP2/TP3', enabled: true, color: '#10B981', category: 'SSOT_CORE' },
    { id: 'volume', label: 'Volumen', sublabel: 'Flujo de transacciones por vela', enabled: true, color: '#00FF41', category: 'SSOT_CORE' },

    // Structure & Sessions
    { id: 'smc', label: 'SMC Order Blocks', sublabel: 'Bloques institucionales vigentes', enabled: true, color: '#00FF41', category: 'STRUCTURE' },
    { id: 'fvg', label: 'Fair Value Gaps', sublabel: 'Desequilibrios de liquidez (FVG)', enabled: true, color: '#FFCC00', category: 'STRUCTURE' },
    { id: 'session', label: 'Sesiones & Killzones', sublabel: 'Asia, Londres, NY y PDH/PDL', enabled: true, color: '#C084FC', category: 'STRUCTURE' },
    { id: 'sr', label: 'Soporte / Resistencia', sublabel: 'Niveles clave multi-temporalidad', enabled: false, color: '#00E5FF', category: 'STRUCTURE' },
    { id: 'fibonacci', label: 'Autofib (OTE)', sublabel: 'Zonas Premium / Discount (0.618–0.786)', enabled: false, color: '#FF7043', category: 'STRUCTURE' },

    // Liquidity & Microstructure
    { id: 'value_area', label: 'Yosh Value Area', sublabel: 'VAH / VAL / POC (Perfil de Volumen)', enabled: false, color: '#FFD700', category: 'LIQUIDITY' },
    { id: 'heatmap', label: 'Heatmap Order Book', sublabel: 'Muros de liquidez L2 (Bids/Asks)', enabled: false, color: '#BF00FF', category: 'LIQUIDITY' },
    { id: 'liquidations', label: 'Rekt Radar', sublabel: 'Clusters de liquidación apalancada', enabled: false, color: '#FF003C', category: 'LIQUIDITY' },
    { id: 'traps', label: 'Market Traps', sublabel: 'Barridos Look Above/Below & Fail', enabled: false, color: '#FF00FF', category: 'LIQUIDITY' },
    { id: 'williams_oops', label: 'Oops! Reversal', sublabel: 'Niveles Larry Williams (PDH/PDL)', enabled: false, color: '#E11D48', category: 'LIQUIDITY' },
    { id: 'williams_r', label: 'Williams %R', sublabel: 'Oscilador de sobrecompra/venta (14p)', enabled: false, color: '#8B5CF6', category: 'LIQUIDITY' },
];

interface PersistedIndicatorsPayload {
    enabledMap: Record<string, boolean>;
    activePreset: ChartPresetId | 'CUSTOM';
}

function readPersistedState(): PersistedIndicatorsPayload | null {
    if (typeof window === 'undefined') return null;
    try {
        const raw = window.localStorage.getItem(INDICATORS_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as Partial<PersistedIndicatorsPayload>;
        if (!parsed || typeof parsed.enabledMap !== 'object' || parsed.enabledMap === null) {
            return null;
        }
        return {
            enabledMap: parsed.enabledMap,
            activePreset: parsed.activePreset || 'CUSTOM',
        };
    } catch {
        return null;
    }
}

function writePersistedState(indicators: Indicator[], activePreset: ChartPresetId | 'CUSTOM'): void {
    if (typeof window === 'undefined') return;
    try {
        const enabledMap: Record<string, boolean> = {};
        for (const ind of indicators) {
            enabledMap[ind.id] = ind.enabled;
        }
        window.localStorage.setItem(
            INDICATORS_STORAGE_KEY,
            JSON.stringify({ enabledMap, activePreset } satisfies PersistedIndicatorsPayload)
        );
    } catch {
        // Ignore storage quota or private mode failures
    }
}

export interface IndicatorsState {
    indicators: Indicator[];
    activePreset: ChartPresetId | 'CUSTOM';
    hydrated: boolean;
    hydrate: () => void;
    toggleIndicator: (id: string) => void;
    applyPreset: (preset: ChartPresetId) => void;
    setIndicators: (indicators: Indicator[]) => void;
}

export const useIndicatorsStore = create<IndicatorsState>((set, get) => ({
    indicators: INDICATOR_DEFAULTS,
    activePreset: 'SSOT_STRATEGY',
    hydrated: false,

    hydrate: () => {
        if (get().hydrated) return;
        const persisted = readPersistedState();
        if (!persisted) {
            set({ hydrated: true });
            return;
        }
        const merged = INDICATOR_DEFAULTS.map((def) => ({
            ...def,
            enabled:
                typeof persisted.enabledMap[def.id] === 'boolean'
                    ? persisted.enabledMap[def.id]
                    : def.enabled,
        }));
        set({
            indicators: merged,
            activePreset: persisted.activePreset,
            hydrated: true,
        });
    },

    toggleIndicator: (id: string) =>
        set((state) => {
            const next = state.indicators.map((ind) =>
                ind.id === id ? { ...ind, enabled: !ind.enabled } : ind
            );
            writePersistedState(next, 'CUSTOM');
            return { indicators: next, activePreset: 'CUSTOM' };
        }),

    applyPreset: (preset: ChartPresetId) =>
        set((state) => {
            const enabledSet = new Set(CHART_PRESETS[preset].enabledIds);
            const next = state.indicators.map((ind) => ({
                ...ind,
                enabled: enabledSet.has(ind.id),
            }));
            writePersistedState(next, preset);
            return { indicators: next, activePreset: preset };
        }),

    setIndicators: (indicators) => {
        writePersistedState(indicators, 'CUSTOM');
        set({ indicators, activePreset: 'CUSTOM' });
    },
}));
