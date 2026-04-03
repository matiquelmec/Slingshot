import os
import yfinance as yf

# Probar si el cambio de ruta soluciona el error (77) de Curl
CERT_PATH = r"C:\tmp\cacert.pem"
os.environ['CURL_CA_BUNDLE'] = CERT_PATH
os.environ['REQUESTS_CA_BUNDLE'] = CERT_PATH
os.environ['SSL_CERT_FILE'] = CERT_PATH

print(f"Testing with cert path: {CERT_PATH}")
try:
    tick = yf.Ticker("BTC-USD")
    hist = tick.history(period="1d")
    if not hist.empty:
        print("✅ SUCCESS (BTC-USD): Data fetched!")
    else:
        print("❌ FAILED (BTC-USD): Hist empty")
    
    tick = yf.Ticker("DX=F")
    hist = tick.history(period="1d")
    if not hist.empty:
        print("✅ SUCCESS (DX=F): Data fetched!")
    else:
        # Quizá por ser fin de semana o feriado o horario?
        print("❌ FAILED (DX=F): Hist empty (likely market closed or ticker issue)")
except Exception as e:
    print(f"❌ FAILED with error: {e}")
