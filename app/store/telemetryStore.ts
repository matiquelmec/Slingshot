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

                        // --- Mock ML Projection Dynamics ---
                        // Only bump probability slightly to simulate 'live' calculating behavior, 
                        // jumping based loosely on close vs open of the latest tick.
                        let prob = state.mlProjection.probability;
                        const direction = newCandle.close >= newCandle.open ? 'ALCISTA' : 'BAJISTA';

                        // Drift towards the short term candle bias 
                        if (direction === state.mlProjection.direction) {
                            prob = Math.min(99, prob + (Math.random() * 2));
                        } else {
                            prob = Math.max(51, prob - (Math.random() * 3));
                            if (prob <= 51) {
                                prob = 52 + Math.random() * 10;
                            }
                        }

                        // --- Dynamic Neural Logs ---
                        let updatedLogs = [...state.neuralLogs];
                        // Chance to generate log (e.g. 5% per tick)
                        if (Math.random() > 0.95 && currentCandles.length > 5) {
                            const types: Array<'SYSTEM' | 'SENSOR' | 'ALERT'> = ['SYSTEM', 'SENSOR', 'ALERT'];
                            const selectedType = types[Math.floor(Math.random() * types.length)];

                            let msg = "Analizando volumen derivado...";
                            const priceNode = newCandle.close.toFixed(2);

                            if (selectedType === 'ALERT') {
                                msg = direction === 'ALCISTA' ? `Cacería de liquidez alcista detectada cerca de $${priceNode}. (RVOL > 1.4x)` : `Rechazo de liquidez inminente en $${priceNode}. Monitoreando volumen (RVOL > 1.8x).`;
                            } else if (selectedType === 'SENSOR') {
                                msg = `Mapeo Topográfico... FVG detectado en $${priceNode} (Block Institucional ${direction.toLowerCase()}).`;
                            } else {
                                msg = `Ajustando pesos del modelo XGBoost. Divergencia en TF ${state.activeTimeframe} detectada.`;
                            }

                            const newLog: NeuralLog = {
                                id: Math.random().toString(36).substring(7),
                                timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                                type: selectedType,
                                message: msg
                            };

                            updatedLogs.unshift(newLog); // prepend
                            if (updatedLogs.length > 3) updatedLogs = updatedLogs.slice(0, 3); // keep only 3
                        }

                        // --- Dynamic Tactical Decision (Market Regime Router Mock) ---
                        let currentDecision = { ...state.tacticalDecision };

                        // Slowly adapt the regime to give organic feel
                        if (Math.random() > 0.90) { // 10% chance per tick to potentially change phase
                            const isTrending = prob > 65 || prob < 35;
                            if (isTrending) {
                                currentDecision.regime = direction === 'ALCISTA' ? "TENDENCIA BULLISH CONSTANTE" : "SELL-OFF BEARISH SEVERO";
                                currentDecision.strategy = "Trend Pullbacks";
                                currentDecision.reasoning = direction === 'ALCISTA' ? "Fuerte moméntum detectado. Esperando retroceso a la franja del Golden Pocket." : "Alta presión de venta institucional. Buscando rebotes débiles a premium zones.";
                            } else if (prob > 55 || prob < 45) {
                                currentDecision.regime = "COMPRESIÓN DE VOLATILIDAD";
                                currentDecision.strategy = "SMC Liquidations";
                                currentDecision.reasoning = "El precio está comprimiendo liquidez en rangos estrechos. Detectando barridos falsos de Order Blocks.";
                            } else {
                                currentDecision.regime = "RANGO LATERAL SIN TENDENCIA";
                                currentDecision.strategy = "Mean Reversion / Neutral";
                                currentDecision.reasoning = "Asimetría en RVOL insuficiente. Estrategias tácticas de reversión a la media mediante desviación estándar.";
                            }
                        }

                        return {
                            candles: currentCandles,
                            latestPrice: newCandle.close,
                            mlProjection: { direction: (prob > 52 && newCandle.close >= newCandle.open) ? 'ALCISTA' : 'BAJISTA', probability: Math.round(prob) },
                            neuralLogs: updatedLogs,
                            tacticalDecision: currentDecision
                        };
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
