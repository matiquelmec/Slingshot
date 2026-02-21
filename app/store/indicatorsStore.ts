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
    { id: 'ema20', label: 'EMA 20', sublabel: 'Media móvil rápida', enabled: true, color: '#00E5FF' },
    { id: 'ema50', label: 'EMA 50', sublabel: 'Media móvil media', enabled: true, color: '#FFC107' },
    { id: 'ema200', label: 'EMA 200', sublabel: 'Media móvil lenta', enabled: false, color: '#EF5350' },
    { id: 'bb', label: 'Bollinger', sublabel: 'Bandas de volatilidad', enabled: false, color: '#9C27B0' },
    { id: 'volume', label: 'Volumen', sublabel: 'Barras de volumen', enabled: true, color: '#00FF41' },
    { id: 'rsi', label: 'RSI (14)', sublabel: 'Fuerza relativa', enabled: false, color: '#FF7043' },
    { id: 'macd', label: 'MACD', sublabel: 'Convergencia/Divergencia', enabled: false, color: '#26A69A' },
    { id: 'smc', label: 'SMC Blocks', sublabel: 'Estructura Institucional (OBs)', enabled: true, color: '#00FF41' },
    { id: 'fvg', label: 'Fair Value Gaps', sublabel: 'Vacíos de Liquidez (FVG)', enabled: true, color: '#FFCC00' },
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
