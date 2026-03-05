// app/types/signal.ts

export interface ConfluenceChecklist {
    factor: string;
    status: 'CONFIRMADO' | 'PARCIAL' | 'BAJO' | 'NEUTRAL' | 'PRECAUCIÓN' | 'DIVERGENTE';
    detail: string;
}

export interface ConfluenceData {
    score: number;
    conviction: string;
    checklist: ConfluenceChecklist[];
    reasoning?: string;
    rvol?: number;
}

export interface Signal {
    type: string;
    signal_type?: string;
    timestamp: string;
    price: number;
    stop_loss: number;
    take_profit_3r: number;
    entry_zone_bottom?: number;
    entry_zone_top?: number;
    risk_pct?: number;
    risk_usd?: number | string;
    leverage?: number;
    position_size?: number | string;
    expiry_candles?: number;
    expiry_timestamp?: string;
    interval_minutes?: number;
    trigger?: string;
    confluence?: ConfluenceData;
    regime?: string;
    atr_value?: number;
}

export interface QuantDiagnostic {
    rsi: number;
    rsi_oversold: boolean;
    rsi_overbought: boolean;
    bullish_divergence: boolean;
    bearish_divergence: boolean;
    macd_line: number;
    macd_signal: number;
    macd_bullish_cross: boolean;
    bbwp: number;
    squeeze_active: boolean;
    volume: number;
    volume_mean?: number;
}

export interface MLProjection {
    direction: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL' | string;
    probability: number;
}

export interface SessionData {
    current_session?: string;
    sessions?: Record<string, any>;
    pdl?: number;
    pdh?: number;
}

export interface TacticalDecision {
    regime?: string;
    market_regime?: string;
    active_strategy?: string;
    current_price?: number;
    nearest_support?: number;
    nearest_resistance?: number;
    diagnostic?: QuantDiagnostic;
    strategy?: string;
}
