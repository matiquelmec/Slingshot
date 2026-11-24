const WebSocket = require('ws');
const http = require('http');

// 13 Activos Canónicos SSoT (SOP-125 & SOP-147: Binance USDⓈ-M Perpetual Futures WS)
const assets = [
  "btcusdt", "ethusdt", "solusdt", "bnbusdt", "linkusdt",
  "xrpusdt", "xauusdt", "suiusdt", "injusdt", "nearusdt",
  "fetusdt", "atomusdt", "tiausdt"
];

// Memoria caché local en microsegundos para Ticks con Order Flow Delta
const ticksCache = {};
assets.forEach(asset => {
  ticksCache[asset.toUpperCase()] = {
    price: 0,
    volume: 0,
    timestamp: 0,
    taker_buy_volume: 0,
    taker_sell_volume: 0,
    delta_ratio: 0.0,
    price_change_pct: 0.0
  };
});

// ── CONEXIÓN WEBSOCKET PERSISTENTE A BINANCE USDⓈ-M FUTURES (SOP-147) ──
function connectWebSocket() {
  const streams = assets.map(asset => `${asset}@ticker`).join('/');
  const wsUrl = `wss://fstream.binance.com/stream?streams=${streams}`;

  console.log(`📡 [SIDECAR] Conectando a WebSocket de Binance Futures (fstream)...`);
  const ws = new WebSocket(wsUrl);

  ws.on('message', (data) => {
    try {
      const payload = JSON.parse(data);
      const tick = payload.data;
      if (!tick || !tick.s) return;
      const asset = tick.s;
      const currentPrice = parseFloat(tick.c);
      const currentVol = parseFloat(tick.v);
      const prev = ticksCache[asset] || { price: currentPrice, volume: currentVol, taker_buy_volume: 0, taker_sell_volume: 0 };

      const priceDelta = currentPrice - (prev.price || currentPrice);
      const volDelta = Math.max(0, currentVol - (prev.volume || currentVol));

      let buyVol = prev.taker_buy_volume || 0;
      let sellVol = prev.taker_sell_volume || 0;

      // Algoritmo HFT Tick-Rule: Asigna el delta de volumen según la dirección del precio
      if (priceDelta > 0) {
        buyVol += volDelta > 0 ? volDelta : 1.0;
      } else if (priceDelta < 0) {
        sellVol += volDelta > 0 ? volDelta : 1.0;
      } else {
        buyVol += (volDelta > 0 ? volDelta : 0.5) * 0.5;
        sellVol += (volDelta > 0 ? volDelta : 0.5) * 0.5;
      }

      // Factor de decaimiento exponencial para priorizar flujo de órdenes reciente
      buyVol *= 0.98;
      sellVol *= 0.98;

      const totalVol = buyVol + sellVol;
      const deltaRatio = totalVol > 0 ? (buyVol - sellVol) / totalVol : 0.0;

      ticksCache[asset] = {
        price: currentPrice,
        volume: currentVol,
        timestamp: Date.now(),
        price_change_pct: parseFloat(tick.P || 0),
        taker_buy_volume: Math.round(buyVol * 100) / 100,
        taker_sell_volume: Math.round(sellVol * 100) / 100,
        delta_ratio: Math.round(deltaRatio * 1000) / 1000
      };
    } catch (err) {
      // Silencioso
    }
  });

  ws.on('close', () => {
    setTimeout(connectWebSocket, 5000);
  });

  ws.on('error', () => {});
}

connectWebSocket();

// ── SERVIDOR HTTP DE ULTRA BAJA LATENCIA (SOLO LECTURA LOCAL 127.0.0.1:8080) ──
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');

  // Health check para el supervisor Sentinel Watchdog (SOP-HFT)
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: "ok", source: "binance_futures_ws", uptime: process.uptime(), timestamp: Date.now() }));
    return;
  }

  // Obtener Ticks del WebSocket de Binance Futures (GET)
  if (req.method === 'GET' && req.url === '/ticks') {
    res.writeHead(200);
    res.end(JSON.stringify(ticksCache));
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Endpoint no encontrado" }));
});

const PORT = 8080;
server.listen(PORT, '127.0.0.1', () => {
  console.log(`🚀 [SIDECAR] Servidor HFT Futures activo en http://127.0.0.1:${PORT}/ticks`);
});
