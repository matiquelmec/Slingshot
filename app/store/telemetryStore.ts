import { create } from 'zustand';

export interface CandleData {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export type Timeframe = '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '4h' | '8h' | '1d' | '1w' | '1M';

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

export interface TacticalDecision {
    regime: string;
    strategy: string;
    reasoning: string;
    nearest_support: number | null;
    nearest_resistance: number | null;
    sma_fast: number | null;
    sma_slow: number | null;
    sma_slow_slope: number | null;
    bb_width: number | null;
    bb_width_mean: number | null;
    dist_to_sma200: number | null;
    signals: any[];
    key_levels: { resistances: KeyLevel[]; supports: KeyLevel[] };
}

export interface SessionInfo {
    high: number | null;
    low: number | null;
    status: 'ACTIVE' | 'CLOSED' | 'PENDING';
    swept_high: boolean;
    swept_low: boolean;
}

export interface SessionData {
    current_session: string;
    current_session_utc: string;
    local_time: string;
    is_killzone: boolean;
    sessions: { asia: SessionInfo; london: SessionInfo; ny: SessionInfo; };
    pdh: number | null;
    pdl: number | null;
    pdh_swept: boolean;
    pdl_swept: boolean;
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

interface TelemetryState {
    isConnected: boolean;
    activeSymbol: string;
    activeTimeframe: Timeframe;
    candles: CandleData[];
    latestPrice: number | null;
    mlProjection: { direction: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL' | 'ANALIZANDO' | 'CALIBRANDO' | 'ERROR', probability: number, reason?: string };
    liquidityHeatmap: { bids: { price: number, volume: number }[], asks: { price: number, volume: number }[] } | null;
    neuralLogs: NeuralLog[];
    tacticalDecision: TacticalDecision;
    smcData: SMCDataPayload | null;
    sessionData: SessionData | null;
    connect: (symbol: string, timeframe?: Timeframe) => void;
    disconnect: () => void;
    setTimeframe: (tf: Timeframe) => void;
}

export const useTelemetryStore = create<TelemetryState>((set, get) => {
    let ws: WebSocket | null = null;

    const doConnect = (symbol: string, timeframe: Timeframe) => {
        // Clean up existing connection
        if (ws) {
            ws.close();
            ws = null;
        }

        set({
            activeSymbol: symbol,
            activeTimeframe: timeframe,
            candles: [],
            isConnected: false,
            smcData: null,
            sessionData: null,
            latestPrice: null,
            liquidityHeatmap: null,
            mlProjection: { direction: 'NEUTRAL', probability: 50, reason: "Aguardando conexión de telemetría..." },
            tacticalDecision: {
                regime: "ANALIZANDO NUEVO RIESGO...", strategy: "STANDBY",
                reasoning: `Sincronizando telemetría para ${symbol}.`,
                nearest_support: null, nearest_resistance: null,
                sma_fast: null, sma_slow: null, sma_slow_slope: null,
                bb_width: null, bb_width_mean: null, dist_to_sma200: null, signals: [],
                key_levels: { resistances: [], supports: [] }
            }
        });

        // Connect to FastAPI Backend WebSocket - pass timeframe as query param
        ws = new WebSocket(`ws://localhost:8000/api/v1/stream/${symbol}?interval=${timeframe}`);

        ws.onopen = () => {
            set({ isConnected: true });
            console.log(`Telemetry connected: ${symbol} @ ${timeframe}`);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'candle') {
                    const newCandle: CandleData = {
                        time: data.data.timestamp,
                        open: data.data.open,
                        high: data.data.high,
                        low: data.data.low,
                        close: data.data.close,
                        volume: data.data.volume
                    };

                    set((state) => {
                        const currentCandles = [...state.candles];
                        const lastIdx = currentCandles.length - 1;

                        if (lastIdx >= 0 && currentCandles[lastIdx].time === newCandle.time) {
                            currentCandles[lastIdx] = newCandle; // Update ongoing candle
                        } else {
                            currentCandles.push(newCandle); // New candle
                            if (currentCandles.length > 1000) currentCandles.shift();
                        }

                        // Desactivamos la simulación (Mock Data). Ahora esperamos 'neural_pulse' y 'tactical_update' reales.
                        return {
                            candles: currentCandles,
                            latestPrice: newCandle.close
                        };
                    });
                } else if (data.type === 'neural_pulse') {
                    // Update del Fast Path (Tiempo Real Inter-Vela)
                    set((state) => {
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: data.data.log.type,
                            message: data.data.log.message
                        };
                        const updatedLogs = [newLog, ...state.neuralLogs].slice(0, 5); // Mantener últimos 5

                        return {
                            mlProjection: data.data.ml_projection,
                            liquidityHeatmap: data.data.liquidity_heatmap,
                            neuralLogs: updatedLogs
                        };
                    });
                } else if (data.type === 'tactical_update') {
                    const d = data.data;
                    set({
                        tacticalDecision: {
                            regime: d.market_regime ?? 'UNKNOWN',
                            strategy: d.active_strategy ?? 'STANDBY',
                            reasoning: `Régimen: ${d.market_regime}. Soportes mapeados. Dist SMA200: ${d.dist_to_sma200 != null ? (d.dist_to_sma200 * 100).toFixed(2) + '%' : 'N/A'}`,
                            nearest_support: d.nearest_support ?? null,
                            nearest_resistance: d.nearest_resistance ?? null,
                            sma_fast: d.sma_fast ?? null,
                            sma_slow: d.sma_slow ?? null,
                            sma_slow_slope: d.sma_slow_slope ?? null,
                            bb_width: d.bb_width ?? null,
                            bb_width_mean: d.bb_width_mean ?? null,
                            dist_to_sma200: d.dist_to_sma200 ?? null,
                            signals: d.signals ?? [],
                            key_levels: d.key_levels ?? { resistances: [], supports: [] },
                        }
                    });
                } else if (data.type === 'session_update') {
                    set({ sessionData: data.data });
                } else if (data.type === 'smc_data') {
                    set({ smcData: data.data });
                    set((state) => {
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: 'SENSOR',
                            message: `[SMC] Estructura actualizada. OBs: ${data.data.order_blocks.bullish.length} Bull / ${data.data.order_blocks.bearish.length} Bear. FVGs: ${data.data.fvgs.bullish.length + data.data.fvgs.bearish.length}.`
                        };
                        return { neuralLogs: [newLog, ...state.neuralLogs].slice(0, 3) };
                    });
                }
            } catch (e) {
                console.error("Failed to parse telemetry message", e);
            }
        };

        ws.onclose = () => {
            set({ isConnected: false });
        };

        ws.onerror = () => {
            set({ isConnected: false });
        };
    };

    return {
        isConnected: false,
        activeSymbol: 'BTCUSDT',
        activeTimeframe: '15m',
        candles: [],
        latestPrice: null,
        mlProjection: { direction: 'ALCISTA', probability: 64 },
        neuralLogs: [
            { id: 'init', timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }), type: 'SYSTEM', message: 'Modelo XGBoost cargado exitosamente. Pesos calibrados para volatilidad actual.' }
        ],
        tacticalDecision: {
            regime: "DESCUBRIENDO...",
            strategy: "STANDBY",
            reasoning: "Inicializando motores de inferencia.",
            nearest_support: null, nearest_resistance: null,
            sma_fast: null, sma_slow: null, sma_slow_slope: null,
            bb_width: null, bb_width_mean: null, dist_to_sma200: null, signals: [],
            key_levels: { resistances: [], supports: [] }
        },
        smcData: null,
        sessionData: null,
        liquidityHeatmap: null,

        connect: (symbol: string, timeframe?: Timeframe) => {
            const tf = timeframe ?? get().activeTimeframe;
            doConnect(symbol, tf);
        },

        setTimeframe: (tf: Timeframe) => {
            const symbol = get().activeSymbol;
            doConnect(symbol, tf);
        },

        disconnect: () => {
            if (ws) {
                ws.close();
                ws = null;
            }
        }
    };
});
