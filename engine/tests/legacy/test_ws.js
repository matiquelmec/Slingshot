const WebSocket = require('ws');

const BASE_URL = 'http://127.0.0.1:8000';
const BASE_WS = 'ws://127.0.0.1:8000';
const API_KEY = 'slingshot_secure_key_v10'; // Default key

async function main() {
    console.log("1. Fetching auth token...");
    try {
        const res = await fetch(`${BASE_URL}/api/v1/auth/token?api_key=${API_KEY}`);
        if (!res.ok) {
            console.error("Failed to fetch token. Status:", res.status);
            return;
        }
        const data = await res.json();
        const token = data.token;
        console.log("Token retrieved successfully:", token);

        console.log("\n2. Connecting to WebSocket stream for BTCUSDT...");
        const wsUrl = `${BASE_WS}/api/v1/stream/BTCUSDT?token=${token}&interval=15m`;
        const ws = new WebSocket(wsUrl);

        ws.on('open', () => {
            console.log("WebSocket connection established! Waiting for messages...");
        });

        let msgCount = 0;
        ws.on('message', (message) => {
            msgCount++;
            const parsed = JSON.parse(message);
            console.log(`\n[MSG #${msgCount}] Type: ${parsed.type}`);
            
            if (parsed.type === 'smc_data') {
                console.log("SMC Data Payload keys:", Object.keys(parsed.data || {}));
                console.log("Order Blocks:", JSON.stringify(parsed.data?.order_blocks, null, 2));
                console.log("FVGs:", JSON.stringify(parsed.data?.fvgs, null, 2));
            } else if (parsed.type === 'radar_update') {
                console.log("Radar update size:", parsed.data?.length);
            } else if (parsed.type === 'tactical_update') {
                console.log("Tactical update asset:", parsed.data?.asset);
                console.log("Tactical update signals:", parsed.data?.signals);
            }
            
            if (msgCount >= 5) {
                console.log("\nTest completed. Closing connection...");
                ws.close();
                process.exit(0);
            }
        });

        ws.on('error', (err) => {
            console.error("WS Error:", err);
        });

        ws.on('close', (code, reason) => {
            console.log(`WebSocket closed. Code: ${code}, Reason: ${reason.toString()}`);
        });

    } catch (e) {
        console.error("Error during execution:", e);
    }
}

main();
