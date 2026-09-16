const WebSocket = require('ws');
const http = require('http');
const crypto = require('crypto');

// Configuración de los 20 activos VIP del Escáner
const assets = [
  "btcusdt", "ethusdt", "solusdt", "xrpusdt", "ltcusdt", 
  "linkusdt", "adausdt", "dotusdt", "avaxusdt", "nearusdt", 
  "ftmusdt", "atomusdt", "uniusdt", "opusdt", "arbusdt", 
  "injusdt", "wifusdt", "dogeusdt", "aptusdt", "suiusdt"
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

// Configuración de credenciales de Bitunix
const BITUNIX_API_KEY = process.env.BITUNIX_API_KEY || "";
const BITUNIX_SECRET_KEY = process.env.BITUNIX_SECRET_KEY || "";
const IS_DRY_RUN = process.env.DRY_RUN === "true";

// ── CONEXIÓN WEBSOCKET PERSISTENTE A BINANCE ──
function connectWebSocket() {
  const streams = assets.map(asset => `${asset}@ticker`).join('/');
  const wsUrl = `wss://stream.binance.com:9443/stream?streams=${streams}`;
  
  console.log(`📡 [SIDECAR] Conectando a WebSocket de Binance...`);
  const ws = new WebSocket(wsUrl);
  
  ws.on('message', (data) => {
    try {
      const payload = JSON.parse(data);
      const tick = payload.data;
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

// ── GENERADOR DE FIRMA CRIPTOGRÁFICA BITUNIX HFT (Crypto Nativo C++) ──
function generateBitunixSignature(nonce, timestamp, queryStr, bodyStr) {
  const digestInput = `${nonce}${timestamp}${BITUNIX_API_KEY}${queryStr}${bodyStr}`;
  const hash1 = crypto.createHash('sha256').update(digestInput, 'utf-8').digest('hex');
  const signature = crypto.createHash('sha256').update(hash1 + BITUNIX_SECRET_KEY, 'utf-8').digest('hex');
  return signature;
}

// ── SERVIDOR HTTP DE ULTRA BAJA LATENCIA ──
const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');
  
  // A. Obtener Ticks del WebSocket de Binance (GET)
  if (req.method === 'GET' && req.url === '/ticks') {
    res.writeHead(200);
    res.end(JSON.stringify(ticksCache));
    return;
  }
  
  // B. Ejecución de Órdenes HFT (POST /execute)
  if (req.method === 'POST' && req.url === '/execute') {
    let bodyData = '';
    req.on('data', chunk => {
      bodyData += chunk.toString();
    });
    
    req.on('end', async () => {
      try {
        const payload = JSON.parse(bodyData);
        
        // Simulación Dry Run (Firma en memoria)
        if (IS_DRY_RUN || payload.dry_run || !BITUNIX_API_KEY) {
          const mockOrderId = `hft_node_ord_${crypto.randomBytes(4).toString('hex')}`;
          res.writeHead(200);
          res.end(JSON.stringify({
            code: 0,
            msg: "Success (HFT NODE DRY RUN)",
            data: { orderId: mockOrderId, status: "FILLED" }
          }));
          return;
        }

        const path = "/api/v1/futures/order/place"; // Endpoint oficial de Bitunix
        const timestamp = Date.now().toString();
        const nonce = crypto.randomBytes(16).toString('hex');
        
        // Formatear cuerpo estrictamente
        const orderBody = {
          symbol: payload.symbol,
          action: payload.action, // BUY / SELL
          price: payload.price.toString(),
          amount: payload.amount.toString(),
          type: "MARKET", // Por defecto HFT entra a mercado para evitar slippage
          leverage: payload.leverage
        };

        const bodyStr = JSON.stringify(orderBody);
        const sign = generateBitunixSignature(nonce, timestamp, "", bodyStr);

        // Envío asíncrono no-bloqueante a Bitunix
        const fetch = require('https');
        const options = {
          hostname: 'fapi.bitunix.com',
          path: path,
          method: 'POST',
          headers: {
            'api-key': BITUNIX_API_KEY,
            'nonce': nonce,
            'timestamp': timestamp,
            'sign': sign,
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(bodyStr)
          },
          timeout: 4000
        };

        const postReq = fetch.request(options, (postRes) => {
          let responseBody = '';
          postRes.on('data', chunk => responseBody += chunk);
          postRes.on('end', () => {
            res.writeHead(postRes.statusCode);
            res.end(responseBody);
          });
        });

        postReq.on('error', (err) => {
          res.writeHead(500);
          res.end(JSON.stringify({ code: -1, msg: err.message }));
        });

        postReq.write(bodyStr);
        postReq.end();

      } catch (err) {
        res.writeHead(400);
        res.end(JSON.stringify({ code: -2, msg: `Malformed request: ${err.message}` }));
      }
    });
    return;
  }
  
  res.writeHead(404);
  res.end(JSON.stringify({ error: "Endpoint no encontrado" }));
});

const PORT = 8080;
server.listen(PORT, '127.0.0.1', () => {
  console.log(`🚀 [SIDECAR] Servidor HFT activo en http://127.0.0.1:${PORT}/ticks`);
});
