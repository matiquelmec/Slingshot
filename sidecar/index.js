const WebSocket = require('ws');
const http = require('http');

// 13 Activos Canónicos SSoT (SOP-125, SOP-147 & SOP-150: Binance USDⓈ-M Perpetual Futures WS)
const assets = [
  "btcusdt", "ethusdt", "solusdt", "bnbusdt", "linkusdt",
  "xrpusdt", "xauusdt", "suiusdt", "injusdt", "nearusdt",
  "fetusdt", "atomusdt", "tiausdt"
];

// Memoria caché local en microsegundos para Ticks con Order Flow Delta (@aggTrade real)
const ticksCache = {};
// Memoria caché L2 de 20 niveles en tiempo real (@depth20@100ms)
const depthCache = {};

assets.forEach(asset => {
  const sym = asset.toUpperCase();
  ticksCache[sym] = {
    price: 0,
    volume: 0,
    timestamp: 0,
    taker_buy_volume: 0,
    taker_sell_volume: 0,
    delta_ratio: 0.0,
    price_change_pct: 0.0,
    cvd_source: "aggTrade"
  };
  depthCache[sym] = {
    symbol: sym,
    is_live: false,
    imbalance: 0.0,
    spread_bps: 0.0,
    sentiment: "NEUTRAL",
    bids: [],
    asks: [],
    hot_bids: [],
    hot_asks: [],
    timestamp: 0
  };
});

function buildDepthSnapshot(sym, rawBids, rawAsks) {
  const bids = (rawBids || []).slice(0, 20).map(lvl => ({
    price: parseFloat(lvl[0]),
    volume: parseFloat(lvl[1]),
    type: "SUPPORT"
  })).filter(x => Number.isFinite(x.price) && Number.isFinite(x.volume) && x.volume > 0);

  const asks = (rawAsks || []).slice(0, 20).map(lvl => ({
    price: parseFloat(lvl[0]),
    volume: parseFloat(lvl[1]),
    type: "RESISTANCE"
  })).filter(x => Number.isFinite(x.price) && Number.isFinite(x.volume) && x.volume > 0);

  if (bids.length === 0 || asks.length === 0) return null;

  const bestBid = bids[0].price;
  const bestAsk = asks[0].price;
  const mid = (bestBid + bestAsk) / 2;
  const spreadBps = mid > 0 ? ((bestAsk - bestBid) / mid) * 10000 : 0;

  const bidVolUsd = bids.reduce((acc, b) => acc + b.price * b.volume, 0);
  const askVolUsd = asks.reduce((acc, a) => acc + a.price * a.volume, 0);
  const totalVolUsd = bidVolUsd + askVolUsd;
  const imbalance = totalVolUsd > 0 ? (bidVolUsd - askVolUsd) / totalVolUsd : 0;

  const maxVol = Math.max(...bids.map(b => b.volume), ...asks.map(a => a.volume), 1e-9);
  const hotBids = [...bids]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 6)
    .map(b => ({ ...b, heat: Math.round((b.volume / maxVol) * 100) }));
  const hotAsks = [...asks]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 6)
    .map(a => ({ ...a, heat: Math.round((a.volume / maxVol) * 100) }));

  const sentiment = imbalance >= 0.12 ? "BULLISH" : (imbalance <= -0.12 ? "BEARISH" : "NEUTRAL");

  return {
    symbol: sym,
    is_live: true,
    imbalance: Math.round(imbalance * 1000) / 1000,
    spread_bps: Math.round(spreadBps * 100) / 100,
    sentiment,
    bids,
    asks,
    hot_bids: hotBids,
    hot_asks: hotAsks,
    timestamp: Date.now()
  };
}

let reconnectDelayMs = 2000;

// ── CONEXIÓN WEBSOCKET MULTIPLEXADA A BINANCE USDⓈ-M FUTURES (SOP-150) ──
function connectWebSocket() {
  const streams = assets.flatMap(asset => [
    `${asset}@ticker`,
    `${asset}@aggTrade`,
    `${asset}@depth20@100ms`
  ]).join('/');
  const wsUrl = `wss://fstream.binance.com/stream?streams=${streams}`;

  console.log(`📡 [SIDECAR v2] Conectando a Binance Futures WS (@ticker + @aggTrade + @depth20@100ms)...`);
  const ws = new WebSocket(wsUrl);

  ws.on('open', () => {
    reconnectDelayMs = 2000;
  });

  ws.on('message', (raw) => {
    try {
      const payload = JSON.parse(raw);
      const stream = payload.stream || "";
      const msg = payload.data;
      if (!msg) return;

      if (stream.endsWith('@ticker') && msg.s) {
        const sym = msg.s.toUpperCase();
        const prev = ticksCache[sym] || { taker_buy_volume: 0, taker_sell_volume: 0, delta_ratio: 0 };
        ticksCache[sym] = {
          ...prev,
          price: parseFloat(msg.c),
          volume: parseFloat(msg.v),
          timestamp: Date.now(),
          price_change_pct: parseFloat(msg.P || 0),
          cvd_source: "aggTrade"
        };
      } else if (stream.endsWith('@aggTrade') && msg.s) {
        const sym = msg.s.toUpperCase();
        const prev = ticksCache[sym] || { price: 0, volume: 0, taker_buy_volume: 0, taker_sell_volume: 0, price_change_pct: 0 };
        const qty = parseFloat(msg.q || 0);
        const tradePrice = parseFloat(msg.p || prev.price || 0);
        // m === true -> buyer is market maker -> seller is aggressive taker
        let buyVol = (prev.taker_buy_volume || 0) * 0.992;
        let sellVol = (prev.taker_sell_volume || 0) * 0.992;
        if (msg.m === true) {
          sellVol += qty;
        } else {
          buyVol += qty;
        }
        const totalVol = buyVol + sellVol;
        const deltaRatio = totalVol > 0 ? (buyVol - sellVol) / totalVol : 0.0;

        ticksCache[sym] = {
          ...prev,
          price: tradePrice > 0 ? tradePrice : prev.price,
          timestamp: Date.now(),
          taker_buy_volume: Math.round(buyVol * 100) / 100,
          taker_sell_volume: Math.round(sellVol * 100) / 100,
          delta_ratio: Math.round(deltaRatio * 1000) / 1000,
          cvd_source: "aggTrade"
        };
      } else if (stream.includes('@depth20')) {
        const sym = stream.split('@')[0].toUpperCase();
        const snap = buildDepthSnapshot(sym, msg.b || msg.bids, msg.a || msg.asks);
        if (snap) {
          depthCache[sym] = snap;
        }
      }
    } catch (err) {
      // Silencioso en ruta crítica HFT
    }
  });

  ws.on('close', () => {
    setTimeout(connectWebSocket, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30000);
  });

  ws.on('error', () => {});
}

connectWebSocket();

// ── SERVIDOR HTTP DE ULTRA BAJA LATENCIA (SOLO LECTURA LOCAL 127.0.0.1:8080) ──
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');

  const urlPath = (req.url || '').split('?')[0];

  // Health check para el supervisor Sentinel Watchdog (SOP-HFT)
  if (req.method === 'GET' && urlPath === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({
      status: "ok",
      source: "binance_futures_ws",
      streams: ["ticker", "aggTrade", "depth20@100ms"],
      uptime: process.uptime(),
      timestamp: Date.now()
    }));
    return;
  }

  // Obtener Ticks + CVD exacto (@aggTrade)
  if (req.method === 'GET' && urlPath === '/ticks') {
    res.writeHead(200);
    res.end(JSON.stringify(ticksCache));
    return;
  }

  // Obtener Depth L2 de los 13 activos
  if (req.method === 'GET' && urlPath === '/depth') {
    res.writeHead(200);
    res.end(JSON.stringify(depthCache));
    return;
  }

  // Obtener Depth L2 de un activo específico (< 1ms)
  if (req.method === 'GET' && urlPath.startsWith('/depth/')) {
    const sym = urlPath.replace('/depth/', '').replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    const snap = depthCache[sym];
    if (snap) {
      res.writeHead(200);
      res.end(JSON.stringify(snap));
    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: "Símbolo no encontrado en Universo Canónico", symbol: sym }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Endpoint no encontrado" }));
});

const PORT = 8080;
server.listen(PORT, '127.0.0.1', () => {
  console.log(`🚀 [SIDECAR v2] Servidor HFT Futures activo en http://127.0.0.1:${PORT} (/ticks, /depth)`);
});
