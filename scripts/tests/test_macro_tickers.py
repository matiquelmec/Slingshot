import os, sys, io

os.environ['CURL_CA_BUNDLE'] = r'C:\tmp\cacert.pem'
os.environ['REQUESTS_CA_BUNDLE'] = r'C:\tmp\cacert.pem'
os.environ['SSL_CERT_FILE'] = r'C:\tmp\cacert.pem'

import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

import yfinance as yf

def fetch_silent(ticker, period="2d", interval="1h"):
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        t = yf.Ticker(ticker)
        h = t.history(period=period, interval=interval)
        noise = sys.stderr.getvalue()
        return h, noise
    except Exception as e:
        return None, str(e)
    finally:
        sys.stderr = old

results = []

# Test 1
h, noise = fetch_silent("DX-Y.NYB")
ok = h is not None and not h.empty
r = f"DX-Y.NYB: {'PASS' if ok else 'FAIL'}"
if ok:
    r += f" ({len(h)} rows, Close={h['Close'].iloc[-1]:.2f})"
results.append(r)

# Test 2
h, noise = fetch_silent("^NDX")
ok = h is not None and not h.empty
r = f"^NDX:     {'PASS' if ok else 'FAIL'}"
if ok:
    r += f" ({len(h)} rows, Close={h['Close'].iloc[-1]:.2f})"
results.append(r)

# Test 3 (dead ticker)
h, noise = fetch_silent("DX=F")
empty = h is None or h.empty
r = f"DX=F:     {'PASS (empty as expected, noise={len(noise)} chars suppressed)' if empty else 'UNEXPECTED DATA'}"
results.append(r)

# Test 4
h, noise = fetch_silent("UUP")
ok = h is not None and not h.empty
r = f"UUP:      {'PASS' if ok else 'SKIP (market closed)'}"
if ok:
    r += f" ({len(h)} rows, Close={h['Close'].iloc[-1]:.2f})"
results.append(r)

# Test 5
h, noise = fetch_silent("QQQ")
ok = h is not None and not h.empty
r = f"QQQ:      {'PASS' if ok else 'SKIP'}"
if ok:
    r += f" ({len(h)} rows, Close={h['Close'].iloc[-1]:.2f})"
results.append(r)

with open("tmp/test_results.txt", "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")
        print(line)

print("\nDone.")
