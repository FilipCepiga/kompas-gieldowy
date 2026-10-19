#!/usr/bin/env python3
"""Pobiera notowania dzienne z Yahoo Finance, liczy wskaźniki i zapisuje data.json.

Uruchom:  python3 fetch_data.py
Tylko biblioteka standardowa — nic nie trzeba instalować.
"""
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).with_name("data.json")

# (symbol Yahoo, nazwa, rynek)
UNIVERSE = [
    ("PKN.WA", "Orlen", "GPW"),
    ("PKO.WA", "PKO BP", "GPW"),
    ("PZU.WA", "PZU", "GPW"),
    ("PEO.WA", "Bank Pekao", "GPW"),
    ("KGH.WA", "KGHM", "GPW"),
    ("CDR.WA", "CD Projekt", "GPW"),
    ("ALE.WA", "Allegro", "GPW"),
    ("LPP.WA", "LPP", "GPW"),
    ("DNP.WA", "Dino Polska", "GPW"),
    ("MBK.WA", "mBank", "GPW"),
    ("OPL.WA", "Orange Polska", "GPW"),
    ("PGE.WA", "PGE", "GPW"),
    ("KRU.WA", "Kruk", "GPW"),
    ("KTY.WA", "Grupa Kęty", "GPW"),
    ("ALR.WA", "Alior Bank", "GPW"),
    ("BDX.WA", "Budimex", "GPW"),
    ("PCO.WA", "Pepco", "GPW"),
    ("CPS.WA", "Cyfrowy Polsat", "GPW"),
    ("ZAB.WA", "Żabka", "GPW"),
    ("AAPL", "Apple", "USA"),
    ("MSFT", "Microsoft", "USA"),
    ("NVDA", "Nvidia", "USA"),
    ("AMZN", "Amazon", "USA"),
    ("GOOGL", "Alphabet", "USA"),
    ("META", "Meta", "USA"),
    ("TSLA", "Tesla", "USA"),
    ("SPY", "ETF S&P 500", "USA"),
]

UA = {"User-Agent": "Mozilla/5.0"}


def fetch(symbol, rng="2y"):
    js = None
    for attempt, host in enumerate(("query1", "query2", "query1")):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                js = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    res = js["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = []
    for t, o, h, l, c, v in zip(res["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"]):
        if None in (o, h, l, c):
            continue
        rows.append((t, o, h, l, c, v or 0))
    return res["meta"], rows


def sma(xs, n):
    out = [None] * len(xs)
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rsi(closes, n=14):
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / n, losses / n
    out[n] = 100 - 100 / (1 + ag / al) if al else 100.0
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        out[i] = 100 - 100 / (1 + ag / al) if al else 100.0
    return out


def atr(highs, lows, closes, n=14):
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    out = [None] * len(closes)
    if len(trs) < n:
        return out
    a = sum(trs[:n]) / n
    out[n - 1] = a
    for i in range(n, len(trs)):
        a = (a * (n - 1) + trs[i]) / n
        out[i] = a
    return out


def setup_at(i, c, s50, s200, r):
    """Reguła 'pullback w trendzie': cena nad SMA50 > SMA200, RSI cofnęło się w strefę 35–50."""
    if None in (s50[i], s200[i], r[i]):
        return False
    return c[i] > s50[i] > s200[i] and 35 <= r[i] <= 50


def backtest(c, h, l, s50, s200, r, a, horizon=20):
    """Dla każdego dnia z sygnałem sprawdza, czy pierwszy padł cel (+3 ATR) czy stop (-2 ATR)."""
    wins = losses = open_ = 0
    i = 0
    last = len(c) - 1
    while i < last:
        if setup_at(i, c, s50, s200, r) and a[i]:
            entry, stop, target = c[i], c[i] - 2 * a[i], c[i] + 3 * a[i]
            outcome = None
            for j in range(i + 1, min(i + 1 + horizon, len(c))):
                if l[j] <= stop:
                    outcome = "L"
                    break
                if h[j] >= target:
                    outcome = "W"
                    break
            if outcome == "W":
                wins += 1
            elif outcome == "L":
                losses += 1
            else:
                open_ += 1
            i += 5  # nie licz tego samego ruchu kilka razy
        else:
            i += 1
    return {"wins": wins, "losses": losses, "undecided": open_}


def analyse(symbol, name, market):
    meta, rows = fetch(symbol)
    if len(rows) < 60:
        raise ValueError("za mało danych")
    t = [x[0] for x in rows]
    h = [x[2] for x in rows]
    l = [x[3] for x in rows]
    c = [x[4] for x in rows]
    v = [x[5] for x in rows]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    r = rsi(c)
    a = atr(h, l, c)
    vavg = sma(v, 20)
    i = len(c) - 1

    def chg(k):
        return (c[i] / c[i - k] - 1) * 100 if i - k >= 0 else None

    hi52 = max(h[-252:])
    lo52 = min(l[-252:])
    vol_ratio = v[i] / vavg[i - 1] if vavg[i - 1] else None

    flags = []
    if s50[i] and s200[i]:
        if c[i] > s50[i] > s200[i]:
            flags.append(("trend_up", "Trend wzrostowy", "Cena nad średnią 50-dniową, a ta nad 200-dniową."))
        elif c[i] < s50[i] < s200[i]:
            flags.append(("trend_down", "Trend spadkowy", "Cena pod średnią 50-dniową, a ta pod 200-dniową."))
    if r[i] is not None:
        if r[i] < 30:
            flags.append(("oversold", "Mocno wyprzedana", f"RSI {r[i]:.0f} — po silnych spadkach. Nie znaczy, że zaraz odbije."))
        elif r[i] > 70:
            flags.append(("overbought", "Mocno wykupiona", f"RSI {r[i]:.0f} — po silnych wzrostach. Ryzyko korekty rośnie."))
    if vol_ratio and vol_ratio >= 2:
        flags.append(("volume", "Nietypowy wolumen", f"Obrót {vol_ratio:.1f}× większy niż średnio. Coś się dzieje — sprawdź wiadomości."))
    for k in range(0, 3):
        j = i - k
        if s50[j] and s50[j - 1] and c[j - 1] < s50[j - 1] and c[j] > s50[j]:
            flags.append(("cross_up", "Przebicie SMA50 w górę", "Cena w ostatnich dniach wybiła się nad średnią 50-dniową."))
            break
        if s50[j] and s50[j - 1] and c[j - 1] > s50[j - 1] and c[j] < s50[j]:
            flags.append(("cross_down", "Przebicie SMA50 w dół", "Cena w ostatnich dniach spadła pod średnią 50-dniową."))
            break
    if h[i] >= hi52 * 0.999:
        flags.append(("high52", "Szczyt 52 tygodni", "Najwyżej od roku."))
    if l[i] <= lo52 * 1.001:
        flags.append(("low52", "Dołek 52 tygodni", "Najniżej od roku."))

    setup = setup_at(i, c, s50, s200, r)
    keys = {f[0] for f in flags}
    if setup:
        status = "setup"
    elif keys & {"trend_down", "cross_down", "low52"}:
        status = "avoid"
    elif keys & {"trend_up", "cross_up", "high52"}:
        status = "watch"
    else:
        status = "neutral"

    bt = backtest(c, h, l, s50, s200, r, a)

    n_spark = 130
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "currency": meta.get("currency", "PLN"),
        "asOf": datetime.fromtimestamp(t[i], timezone.utc).strftime("%Y-%m-%d"),
        "price": round(c[i], 4),
        "chg1d": chg(1),
        "chg5d": chg(5),
        "chg1m": chg(21),
        "sma20": s20[i],
        "sma50": s50[i],
        "sma200": s200[i],
        "rsi": r[i],
        "atr": a[i],
        "atrPct": a[i] / c[i] * 100 if a[i] else None,
        "volRatio": vol_ratio,
        "hi52": hi52,
        "lo52": lo52,
        "flags": [{"key": k, "label": lb, "why": w} for k, lb, w in flags],
        "status": status,
        "plan": {
            "entry": c[i],
            "stop": c[i] - 2 * a[i],
            "target": c[i] + 3 * a[i],
        } if a[i] else None,
        "backtest": bt,
        "closes": [round(x, 4) for x in c[-n_spark:]],
        "sma50s": [round(x, 4) if x else None for x in s50[-n_spark:]],
        "dates": [datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%d") for x in t[-n_spark:]],
    }


def main():
    items, errors = [], []
    for sym, name, mkt in UNIVERSE:
        try:
            items.append(analyse(sym, name, mkt))
            print("ok ", sym)
        except Exception as e:  # pojedyncza spółka nie może zatrzymać całości
            errors.append({"symbol": sym, "error": str(e)})
            print("ERR", sym, e)
        time.sleep(0.4)

    fx = {}
    for pair in ("USDPLN=X",):
        try:
            meta, rows = fetch(pair, "5d")
            fx[pair[:6]] = rows[-1][4]
        except Exception as e:
            errors.append({"symbol": pair, "error": str(e)})

    def r(x):
        if isinstance(x, float):
            return None if math.isnan(x) else round(x, 4)
        if isinstance(x, dict):
            return {k: r(v) for k, v in x.items()}
        if isinstance(x, list):
            return [r(v) for v in x]
        return x

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "source": "Yahoo Finance, notowania dzienne",
        "fx": fx,
        "items": r(items),
        "errors": errors,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"zapisano {OUT.name}: {len(items)} instrumentów, {len(errors)} błędów")


if __name__ == "__main__":
    main()
