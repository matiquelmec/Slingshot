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

export interface TacticalDecision {
    regime: string;
    strategy: string;
    reasoning: string;
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
    mlProjection: { direction: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL', probability: number };
    liquidityHeatmap: { bids: { price: number, volume: number }[], asks: { price: number, volume: number }[] } | null;
    neuralLogs: NeuralLog[];
    tacticalDecision: TacticalDecision;
    smcData: SMCDataPayload | null;
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
            latestPrice: null,
            liquidityHeatmap: null,
            mlProjection: { direction: 'NEUTRAL', probability: 50 },
            tacticalDecision: { regime: "ANALIZANDO NUEVO RIESGO...", strategy: "STANDBY", reasoning: `Sincronizando telemetría y topografía de liquidez para ${symbol}.` }
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
                    // Update del Slow Path (Confirmación Estructural al Cierre de Vela)
                    set({
                        tacticalDecision: {
                            regime: data.data.market_regime,
                            strategy: data.data.active_strategy,
                            // Por ahora armamos un reasoning estático basado en la data real.
                            // Próximamente se le puede inyectar del Python The Core Reason.
                            reasoning: `Estructura Procesada. Soportes Mapeados. Régimen Activo: ${data.data.market_regime}.`
                        }
                    });
                } else if (data.type === 'smc_data') {
                    // Update global state with precise institutional structure blocks
                    set({ smcData: data.data });

                    // Option to add a system log announcing structure update
                    set((state) => {
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: 'SENSOR',
                            message: `[SMC] Estructura Institucional sincronizada. OBs detectados: ${data.data.order_blocks.bullish.length} Bull, ${data.data.order_blocks.bearish.length} Bear. FVGs: ${data.data.fvgs.bullish.length + data.data.fvgs.bearish.length}.`
                        };
                        const updatedLogs = [newLog, ...state.neuralLogs].slice(0, 3);
                        return { neuralLogs: updatedLogs };
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
            reasoning: "Inicializando motores de inferencia."
        },
        smcData: null,
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
