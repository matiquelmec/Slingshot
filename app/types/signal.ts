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
    asset?: string;
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
    confluence_score?: number;
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

export interface NeuralLog {
    id: string;
    timestamp: string;
    type: 'SYSTEM' | 'SENSOR' | 'ALERT';
    message: string;
}

export interface KeyLevel {
    price: number;
    touches: number;
    zone_top: number;
    zone_bottom: number;
    type: 'SUPPORT' | 'RESISTANCE';
    origin: 'PIVOT' | 'ROLE_REVERSAL';
    strength: 'WEAK' | 'MODERATE' | 'STRONG';
    is_active: boolean;
    ob_confluence: boolean;
    volume_score: number;
    mtf_confluence: boolean;
    mtf_score: number;
}

export interface SessionInfo {
    high: number | null;
    low: number | null;
    status: 'ACTIVE' | 'CLOSED' | 'PENDING';
    swept_high: boolean;
    swept_low: boolean;
    start_utc: number;
    end_utc: number;
}

export interface SessionData {
    current_session: string;
    current_session_utc?: string;
    local_time?: string;
    local_time_ny?: string;
    local_time_lon?: string;
    local_time_chile?: string;
    timestamp_utc?: number;
    is_killzone?: boolean;
    sessions?: { asia: SessionInfo; london: SessionInfo; ny: SessionInfo; };
    pdh: number | null;
    pdl: number | null;
    pdh_swept?: boolean;
    pdl_swept?: boolean;
}

export interface OrderBlockData {
    time: number;
    top: number;
    bottom: number;
    status: string;
    confirmation_time: number;
}

export interface SMCDataPayload {
    order_blocks: {
        bullish: OrderBlockData[];
        bearish: OrderBlockData[];
    };
    fvgs: {
        bullish: OrderBlockData[];
        bearish: OrderBlockData[];
    };
}

export interface GhostData {
    symbol?: string;
    fear_greed_value: number;
    fear_greed_label: string;
    btc_dominance: number;
    funding_rate: number;
    funding_symbol?: string;
    macro_bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'BLOCK_LONGS' | 'BLOCK_SHORTS' | 'CONFLICTED' | string;
    block_longs: boolean;
    block_shorts: boolean;
    reason: string;
    last_updated?: number;
}

export interface TacticalDecision {
    regime: string;
    market_regime?: string;
    active_strategy?: string;
    current_price: number | null;
    nearest_support: number | null;
    nearest_resistance: number | null;
    diagnostic?: QuantDiagnostic;
    strategy?: string;
    reasoning?: string;
    sma_fast?: number | null;
    sma_slow?: number | null;
    sma_slow_slope?: number | null;
    bb_width?: number | null;
    bb_width_mean?: number | null;
    dist_to_sma200?: number | null;
    signals?: Signal[];
    key_levels?: { resistances: KeyLevel[]; supports: KeyLevel[] };
    fibonacci?: {
        swing_high: number;
        swing_low: number;
        levels: Record<string, number>;
    };
}

