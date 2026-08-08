import { Signal, NeuralLog, TacticalDecision, SessionData, SMCDataPayload, GhostData, HTFBias, NewsItem, LiquidationCluster, EconomicEvent, OnChainMetrics } from '../../types/signal';

export interface CandleData {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    bullish_div?: boolean;
    bearish_div?: boolean;
}

export type Timeframe = '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '4h' | '8h' | '1d' | '1w' | '1M';

export interface TelemetryState {
    advisorLogs: Record<string, any>;
    isConnected: boolean;
    connectionStatus: 'CONNECTING' | 'CONNECTED' | 'STALLED' | 'DISCONNECTED';
    connectionMode: 'WS' | 'FALLBACK' | 'DISCONNECTED';
    isCalibrating: boolean;
    activeSymbol: string;
    activeTimeframe: Timeframe;
    candles: CandleData[];
    latestPrice: number | null;
    latestPrices: Record<string, number | null>;
    mlProjection: { direction: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL' | 'ANALIZANDO' | 'CALIBRANDO' | 'ERROR', probability: number, reason?: string };
    liquidityHeatmap: { bids: { price: number, volume: number }[], asks: { price: number, volume: number }[] } | null;
    neuralLogs: NeuralLog[];
    tacticalDecision: TacticalDecision;
    smcData: SMCDataPayload | null;
    sessionData: SessionData | null;
    ghostData: GhostData | null;
    htfBias: HTFBias | null;
    news: NewsItem[];
    liquidations: LiquidationCluster[];
    marketSummary: Record<string, { asset: string, price: number | null, regime: string, strategy: string, bias: string, trend: number }>;
    economicEvents: EconomicEvent[];
    onchainMetrics: OnChainMetrics | null;
    signalHistory: Record<string, Signal>;
    signalIds: string[];
    auditedSignals: Record<string, Signal>;
    auditedIds: string[];
    activeConnectionId: string | null;
    viewMode: 'SYMBOL' | 'GLOBAL';
    connect: (symbol: string, timeframe?: Timeframe) => void;
    disconnect: () => void;
    setTimeframe: (tf: Timeframe) => void;
    setNews: (news: NewsItem[]) => void;
    setViewMode: (mode: 'SYMBOL' | 'GLOBAL') => void;
    hydrateSignals: (signals: Signal[]) => void;
    fetchEconomicEvents: () => Promise<void>;
    clearSignalHistory: () => void;
}
