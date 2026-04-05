import { create } from 'zustand';

export interface Indicator {
    id: string;
    label: string;
    sublabel: string;
    enabled: boolean;
    color: string;
}

interface IndicatorsState {
    indicators: Indicator[];
    toggleIndicator: (id: string) => void;
    setIndicators: (indicators: Indicator[]) => void;
}

export const INDICATOR_DEFAULTS: Indicator[] = [
    { id: 'smc', label: 'SMC Blocks', sublabel: 'Order Blocks (Última vela institucional)', enabled: true, color: '#00FF41' },
    { id: 'fvg', label: 'Fair Value Gaps', sublabel: 'Vacíos de Liquidez (Desequilibrio)', enabled: true, color: '#FFCC00' },
    { id: 'sr', label: 'Soporte / Resistencia', sublabel: 'Zonas de Alta Probabilidad (MTF)', enabled: true, color: '#00E5FF' },
    { id: 'session', label: 'Sesiones de Mercado', sublabel: 'Brackets & Killzones (Power Hour)', enabled: true, color: '#C084FC' },
    { id: 'liquidations', label: 'Rekt Radar', sublabel: 'Niveles de Liquidación (Trapped)', enabled: true, color: '#FF003C' },
    { id: 'fibonacci', label: 'Autofib', sublabel: 'Zonas de Descuento (Premium/Discount)', enabled: false, color: '#FF7043' },
    { id: 'volume', label: 'Volumen', sublabel: 'Flujo de Transacciones', enabled: true, color: '#00FF41' },
    { id: 'heatmap', label: 'Heatmap Neural', sublabel: 'Muros de Liquidez (Order Book)', enabled: true, color: '#BF00FF' },
];

export const useIndicatorsStore = create<IndicatorsState>((set) => ({
    indicators: INDICATOR_DEFAULTS,
    toggleIndicator: (id: string) =>
        set((state) => ({
            indicators: state.indicators.map((ind) =>
                ind.id === id ? { ...ind, enabled: !ind.enabled } : ind
            ),
        })),
    setIndicators: (indicators) => set({ indicators }),
}));
