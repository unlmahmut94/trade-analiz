#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════
  grafik_tv.py — GERÇEK TRADINGVIEW GÖRÜNÜMLÜ GRAFİK (Lightweight Charts)
══════════════════════════════════════════════════════════════════════
  TradingView'in kendi resmi açık kaynak grafik motoru (Lightweight Charts)
  kullanılarak birebir TradingView görünümlü grafik üretir.

  • Mum grafiği (TradingView renkleri: #089981 / #f23645)
  • Hacim histogramı
  • MA20/50/200, EMA9/21, Bollinger, VWAP, PSAR overlay
  • RSI + MACD alt panelleri
  • 🤖 "YZ İLE ÇİZ" butonu → destek/direnç, Fibonacci, trend,
    formasyonlar (İkili Dip/Tepe, OBO, Ters OBO, Üçgenler, BB Sıkışma)
    hepsi GRAFİĞİN ÜZERİNE çizilir.

  NOT: Eski Plotly grafikleri (grafik.py / grafik_html.py) kopya olarak
  durur ve bu modül tarafından kullanılmaz; yalnızca tespit fonksiyonları
  (hazır hesaplama mantığı) yeniden kullanılır.
══════════════════════════════════════════════════════════════════════
"""

import os
import json
import math
import webbrowser
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

# Hazır tespit/hesap mantığını grafik_html.py'den yeniden kullan
from grafik_html import (
    _teknik_gostergeleri_hesapla,
    _formasyon_cizimleri,
    _fibonacci_seviyeleri,
)

# ── RENK PALETİ (TradingView Dark) ───────────────────────────────────
YESIL   = "#089981"
KIRMIZI = "#f23645"
ALTIN   = "#f5cc6a"
MAVI    = "#2962FF"
TURUNCU = "#FF6D00"
MOR     = "#7e57c2"
GRI     = "#787b86"
BEYAZ   = "#d1d4dc"
BG      = "#131722"


# ══════════════════════════════════════════════════════════════════════
#  YARDIMCILAR
# ══════════════════════════════════════════════════════════════════════

def _ts_str(ts) -> str:
    """Zaman damgasını Lightweight Charts'ın istediği 'YYYY-MM-DD' yapar."""
    try:
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return str(ts)


def _sayi(x):
    """Değeri güvenli float'a çevirir; None/NaN/Inf → None."""
    if x is None:
        return None
    try:
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None

def _kutuphane_js_oku() -> str:
    """Lightweight Charts JS kütüphanesini oku (HTML içine gömmek için)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "lightweight-charts.standalone.production.js")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return (f.read()
                    .replace("</script", "<\\/script")
                    .replace("<!--", "<\\!--"))
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════
#  VERİ → JSON (Lightweight Charts formatı)
# ══════════════════════════════════════════════════════════════════════

def _df_to_lw_json(data: pd.DataFrame) -> Dict:
    """OHLCV + göstergeleri Lightweight Charts'ın beklediği JSON'a çevirir."""
    idx = data.index
    candles: List[Dict] = []
    volumes: List[Dict] = []

    for i, ts in enumerate(idx):
        o = _sayi(data["Open"].iloc[i])
        h = _sayi(data["High"].iloc[i])
        l = _sayi(data["Low"].iloc[i])
        c = _sayi(data["Close"].iloc[i])
        if o is None or h is None or l is None or c is None:
            continue
        t = _ts_str(ts)
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})

        v = _sayi(data["Volume"].iloc[i]) if "Volume" in data.columns else 0.0
        if v is None:
            v = 0.0
        volumes.append({
            "time": t, "value": v,
            "color": YESIL if c >= o else KIRMIZI,
        })

    def _line(col: str) -> List[Dict]:
        if col not in data.columns:
            return []
        out = []
        for i, ts in enumerate(idx):
            v = _sayi(data[col].iloc[i])
            if v is None:
                continue
            out.append({"time": _ts_str(ts), "value": round(v, 4)})
        return out

    overlays: Dict[str, List[Dict]] = {}
    for col in ("MA20", "MA50", "MA200", "EMA9", "EMA21",
                "BB_upper", "BB_middle", "BB_lower", "VWAP", "PSAR"):
        overlays[col] = _line(col)

    rsi = _line("RSI")

    macd = {"hist": [], "macd": _line("MACD"), "signal": _line("MACD_Signal")}
    if "MACD_Hist" in data.columns:
        for i, ts in enumerate(idx):
            v = _sayi(data["MACD_Hist"].iloc[i])
            if v is None:
                continue
            macd["hist"].append({
                "time": _ts_str(ts), "value": round(v, 4),
                "color": YESIL if v >= 0 else KIRMIZI,
            })

    return {
        "candles": candles,
        "volumes": volumes,
        "overlays": overlays,
        "rsi": rsi,
        "macd": macd,
    }

# ══════════════════════════════════════════════════════════════════════
#  ÇİZİMLER (formasyon/seviye) → JSON
# ══════════════════════════════════════════════════════════════════════

def _cizimleri_json(cizimler: Dict, data: pd.DataFrame) -> Dict:
    """_formasyon_cizimleri çıktısını JS'in çizebileceği JSON'a dönüştürür."""
    idx = data.index

    def t(pos):
        try:
            if isinstance(pos, (int, np.integer)):
                return _ts_str(idx[int(pos)])
        except Exception:
            pass
        return _ts_str(pos)

    out = {
        "destekler": [], "direncler": [], "fibonacci": [],
        "trendler": [], "markers": [], "price_lines": [], "lejant": [],
        "formasyon_sayisi": 0,
    }

    # ── DESTEK / DİRENÇ ──
    if "destekler" in cizimler:
        for s in cizimler["destekler"].get("seviyeler", []):
            out["destekler"].append({
                "price": round(float(s), 4), "color": YESIL, "title": f"D {float(s):.2f}",
            })
    if "direncler" in cizimler:
        for r in cizimler["direncler"].get("seviyeler", []):
            out["direncler"].append({
                "price": round(float(r), 4), "color": KIRMIZI, "title": f"R {float(r):.2f}",
            })

    # ── FIBONACCI ──
    if "fibonacci" in cizimler:
        fib = cizimler["fibonacci"]
        sev = _fibonacci_seviyeleri(fib["dip"], fib["tepe"])
        fib_renkler = [GRI, MAVI, TURUNCU, YESIL, KIRMIZI, MOR, GRI, GRI, GRI]
        for i, (isim, seviye) in enumerate(sev.items()):
            out["fibonacci"].append({
                "price": round(float(seviye), 4),
                "color": fib_renkler[i % len(fib_renkler)],
                "title": f"Fib {isim}",
            })
        out["lejant"].append({"color": MAVI, "label": "Fibonacci Retracement"})

    # ── TREND ÇİZGİLERİ ──
    if cizimler.get("trend_yukselen"):
        tr = cizimler["trend_yukselen"]
        out["trendler"].append({
            "color": YESIL, "label": "↗ Yükselen Trend",
            "points": [
                {"time": t(tr["baslangic"]), "value": round(float(tr["bas_deger"]), 4)},
                {"time": t(tr["bitis"]), "value": round(float(tr["bit_deger"]), 4)},
            ],
        })
        out["lejant"].append({"color": YESIL, "label": "↗ Yükselen Trend"})
    if cizimler.get("trend_alcalan"):
        tr = cizimler["trend_alcalan"]
        out["trendler"].append({
            "color": KIRMIZI, "label": "↘ Alçalan Trend",
            "points": [
                {"time": t(tr["baslangic"]), "value": round(float(tr["bas_deger"]), 4)},
                {"time": t(tr["bitis"]), "value": round(float(tr["bit_deger"]), 4)},
            ],
        })
        out["lejant"].append({"color": KIRMIZI, "label": "↘ Alçalan Trend"})

    # ── İKİLİ DİP (W) ──
    if cizimler.get("ikili_dip"):
        dd = cizimler["ikili_dip"]
        for i in dd["indices"]:
            out["markers"].append({
                "time": t(i), "position": "belowBar", "shape": "arrowUp",
                "color": YESIL, "text": "W",
            })
        out["price_lines"].append({
            "price": round(float(dd["boyun"]), 4), "color": YESIL,
            "title": f"Boyun {float(dd['boyun']):.2f}",
        })
        out["price_lines"].append({
            "price": round(float(dd["hedef"]), 4), "color": YESIL,
            "title": f"🎯 {float(dd['hedef']):.2f}",
        })
        out["lejant"].append({"color": YESIL, "label": "İkili Dip (W)"})
        out["formasyon_sayisi"] += 1

    # ── İKİLİ TEPE (M) ──
    if cizimler.get("ikili_tepe"):
        dt = cizimler["ikili_tepe"]
        for i in dt["indices"]:
            out["markers"].append({
                "time": t(i), "position": "aboveBar", "shape": "arrowDown",
                "color": KIRMIZI, "text": "M",
            })
        out["price_lines"].append({
            "price": round(float(dt["boyun"]), 4), "color": KIRMIZI,
            "title": f"Boyun {float(dt['boyun']):.2f}",
        })
        out["price_lines"].append({
            "price": round(float(dt["hedef"]), 4), "color": KIRMIZI,
            "title": f"🎯 {float(dt['hedef']):.2f}",
        })
        out["lejant"].append({"color": KIRMIZI, "label": "İkili Tepe (M)"})
        out["formasyon_sayisi"] += 1

    # ── OMUZ-BAŞ-OMUZ (OBO) ──
    if cizimler.get("obo"):
        ob = cizimler["obo"]
        for i, lbl in zip(ob["indices"], ("S", "B", "S")):
            out["markers"].append({
                "time": t(i), "position": "aboveBar", "shape": "circle",
                "color": KIRMIZI, "text": lbl,
            })
        out["price_lines"].append({
            "price": round(float(ob["boyun"]), 4), "color": KIRMIZI,
            "title": f"Boyun {float(ob['boyun']):.2f}",
        })
        out["price_lines"].append({
            "price": round(float(ob["hedef"]), 4), "color": KIRMIZI,
            "title": f"🎯 {float(ob['hedef']):.2f}",
        })
        out["lejant"].append({"color": KIRMIZI, "label": "Omuz-Baş-Omuz (OBO)"})
        out["formasyon_sayisi"] += 1

    # ── TERS OBO ──
    if cizimler.get("ters_obo"):
        to = cizimler["ters_obo"]
        for i, lbl in zip(to["indices"], ("S", "B", "S")):
            out["markers"].append({
                "time": t(i), "position": "belowBar", "shape": "circle",
                "color": YESIL, "text": lbl,
            })
        out["price_lines"].append({
            "price": round(float(to["boyun"]), 4), "color": YESIL,
            "title": f"Boyun {float(to['boyun']):.2f}",
        })
        out["price_lines"].append({
            "price": round(float(to["hedef"]), 4), "color": YESIL,
            "title": f"🎯 {float(to['hedef']):.2f}",
        })
        out["lejant"].append({"color": YESIL, "label": "Ters OBO"})
        out["formasyon_sayisi"] += 1

    # ── YÜKSELEN ÜÇGEN ──
    if cizimler.get("yukselen_ucgen"):
        yt = cizimler["yukselen_ucgen"]
        out["price_lines"].append({
            "price": round(float(yt["direnc"]), 4), "color": YESIL,
            "title": f"▲ {float(yt['direnc']):.2f}",
        })
        out["lejant"].append({"color": YESIL, "label": "Yükselen Üçgen"})
        out["formasyon_sayisi"] += 1

    # ── ALÇALAN ÜÇGEN ──
    if cizimler.get("alcalan_ucgen"):
        at = cizimler["alcalan_ucgen"]
        out["price_lines"].append({
            "price": round(float(at["destek"]), 4), "color": KIRMIZI,
            "title": f"▼ {float(at['destek']):.2f}",
        })
        out["lejant"].append({"color": KIRMIZI, "label": "Alçalan Üçgen"})
        out["formasyon_sayisi"] += 1

    # ── BB SIKIŞMA ──
    if cizimler.get("bb_sikisma"):
        bb = cizimler["bb_sikisma"]
        out["price_lines"].append({
            "price": round(float(bb["ust"]), 4), "color": ALTIN,
            "title": f"BB Üst {float(bb['ust']):.2f}",
        })
        out["price_lines"].append({
            "price": round(float(bb["alt"]), 4), "color": ALTIN,
            "title": f"BB Alt {float(bb['alt']):.2f}",
        })
        out["lejant"].append({"color": ALTIN, "label": "BB Sıkışması"})
        out["formasyon_sayisi"] += 1

    return out

# ══════════════════════════════════════════════════════════════════════
#  HTML ŞABLONU (Lightweight Charts)
# ══════════════════════════════════════════════════════════════════════

_HTML_A = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__SEMBOL__ · TradeAnaliz TradingView</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a1222; color:#d1d4dc; font-family:'Trebuchet MS', Roboto, sans-serif; }
.topbar { display:flex; align-items:center; gap:18px; padding:10px 16px; background:#0e182c; border-bottom:1px solid rgba(30,51,85,0.4); }
.brand { font-weight:800; font-size:15px; letter-spacing:-0.5px; color:#eef2f7; white-space:nowrap; }
.brand span { color:#f0c040; }
.sym-name { font-size:20px; font-weight:800; color:#eef2f7; }
.sym-full { font-size:11px; color:#787b86; margin-left:6px; }
.price { margin-left:auto; text-align:right; }
.price .val { font-size:20px; font-weight:700; color:#eef2f7; }
.price .chg { font-size:13px; font-weight:600; }
.time { font-size:11px; color:#5a6d85; font-family:monospace; white-space:nowrap; }
.toolbar { display:flex; align-items:center; gap:14px; padding:10px 16px; background:#131722; border-bottom:1px solid rgba(30,51,85,0.3); flex-wrap:wrap; }
.ai-btn { background:linear-gradient(135deg,#f0c040,#b8882a); color:#060b14; border:none; border-radius:8px; padding:10px 18px; font-weight:800; font-size:13px; cursor:pointer; letter-spacing:0.3px; font-family:inherit; }
.ai-btn:hover { filter:brightness(1.08); }
.ai-btn.active { background:linear-gradient(135deg,#ff4f6d,#b3304a); color:#fff; }
.hint { font-size:11px; color:#787b86; }
.legend { position:fixed; right:16px; top:120px; width:240px; background:rgba(14,24,44,0.96); border:1px solid rgba(30,51,85,0.55); border-radius:10px; padding:12px; z-index:50; box-shadow:0 8px 30px rgba(0,0,0,0.5); max-height:70vh; overflow:auto; }
.lg-title { font-size:10px; letter-spacing:1.5px; color:#f0c040; font-weight:700; margin-bottom:6px; }
.lg-counts { font-size:10px; color:#8a9bb5; margin-bottom:8px; line-height:1.5; }
.lg-item { display:flex; align-items:center; gap:8px; font-size:12px; color:#d1d4dc; padding:3px 0; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; }
#chart { width:100%; height:560px; background:#131722; }
#rsiChart, #macdChart { width:100%; }
.sub-label { padding:6px 12px 0; font-size:10px; letter-spacing:1px; color:#787b86; background:#131722; font-family:monospace; }
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">📊 TRADEANALİZ <span>PRO</span></div>
  <div>
    <span class="sym-name">__SEMBOL__</span>
    <span class="sym-full">__SEMBOL_TAM__</span>
  </div>
  <div class="price">
    <span class="val">__SON_FIYAT__</span><br>
    <span class="chg" style="color:__DEGISIM_RENK__">__DEGISIM_IKON__ __DEGISIM__%</span>
  </div>
  <div class="time">__ZAMAN__</div>
</div>
<div class="toolbar">
  <button id="aiBtn" class="ai-btn" onclick="aiCiz()">🤖 YZ İLE ÇİZ (Destek/Direnç · Fibonacci · Formasyon)</button>
  <div class="hint">YZ tek tıkla sistemdeki tüm seviyeleri ve formasyonları grafiğin üzerine çizer.</div>
</div>
<div id="legend" class="legend" style="display:none;"></div>
<div id="chart"></div>
<div class="sub-label">RSI (14)</div>
<div id="rsiChart"></div>
<div class="sub-label">MACD (12,26,9)</div>
<div id="macdChart"></div>
__KUTUPHANE_SCRIPT__
<script>
const DATA = __JSON_DATA__;
"""

_HTML_B = r"""
// ── Ana grafik ──────────────────────────────────────────────────────
function lwOpts(el, h) {
  return {
    width: document.getElementById(el).clientWidth || 800,
    height: h,
    layout: {
      background: { type: 'solid', color: '#131722' },
      textColor: '#787b86',
      fontFamily: "'Trebuchet MS', Roboto, Ubuntu, sans-serif",
      fontSize: 12,
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.04)' },
      horzLines: { color: 'rgba(255,255,255,0.04)' },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: 'rgba(255,255,255,0.12)' },
    timeScale: { borderColor: 'rgba(255,255,255,0.12)', timeVisible: false },
    localization: { locale: 'tr-TR' },
  };
}

const chart = LightweightCharts.createChart(document.getElementById('chart'), lwOpts('chart', 560));

const candle = chart.addCandlestickSeries({
  upColor: '#089981', downColor: '#f23645',
  borderUpColor: '#089981', borderDownColor: '#f23645',
  wickUpColor: '#089981', wickDownColor: '#f23645',
});
candle.setData(DATA.candles);

const vol = chart.addHistogramSeries({
  priceFormat: { type: 'volume' }, priceScaleId: 'vol',
  priceLineVisible: false, lastValueVisible: false,
});
chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
vol.setData(DATA.volumes);

const OVERLAY_COLORS = {
  MA20: '#f5cc6a', MA50: '#2962FF', MA200: '#ff6d00',
  EMA9: '#00bcd4', EMA21: '#e91e63',
  BB_upper: 'rgba(120,123,134,0.8)', BB_middle: 'rgba(120,123,134,0.8)', BB_lower: 'rgba(120,123,134,0.8)',
  VWAP: '#7e57c2', PSAR: '#ff9800',
};
for (const k in DATA.overlays) {
  const pts = DATA.overlays[k];
  if (!pts || !pts.length) continue;
  const s = chart.addLineSeries({
    color: OVERLAY_COLORS[k] || '#787b86', lineWidth: 1,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  });
  s.setData(pts);
}

chart.timeScale().fitContent();

// ── RSI alt paneli ──────────────────────────────────────────────────
const rsiChart = LightweightCharts.createChart(document.getElementById('rsiChart'), lwOpts('rsiChart', 170));
const rsi = rsiChart.addLineSeries({ color: '#7e57c2', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
rsi.setData(DATA.rsi);
rsi.createPriceLine({ price: 70, color: '#f23645', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '70' });
rsi.createPriceLine({ price: 30, color: '#089981', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '30' });
rsi.createPriceLine({ price: 50, color: '#787b86', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '50' });

// ── MACD alt paneli ─────────────────────────────────────────────────
const macdChart = LightweightCharts.createChart(document.getElementById('macdChart'), lwOpts('macdChart', 170));
const macdHist = macdChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
macdHist.setData(DATA.macd.hist);
const macdLine = macdChart.addLineSeries({ color: '#2962FF', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
macdLine.setData(DATA.macd.macd);
const macdSig = macdChart.addLineSeries({ color: '#FF6D00', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
macdSig.setData(DATA.macd.signal);
macdHist.createPriceLine({ price: 0, color: '#787b86', lineWidth: 1, lineStyle: 1, axisLabelVisible: false, title: '' });

// ── Zaman ekseni senkronizasyonu ────────────────────────────────────
chart.timeScale().subscribeVisibleLogicalRangeChange(function (range) {
  if (range) {
    rsiChart.timeScale().setVisibleLogicalRange(range);
    macdChart.timeScale().setVisibleLogicalRange(range);
  }
});
"""

_HTML_C = r"""
// ── 🤖 YZ İLE ÇİZ ───────────────────────────────────────────────────
let cizildi = false;
let fiyatCizgileri = [];
let trendSerileri = [];

function renderLegend() {
  const cz = DATA.cizimler;
  const el = document.getElementById('legend');
  let h = '<div class="lg-title">🤖 YZ TESPİTLERİ</div>';
  h += '<div class="lg-counts">🟢 ' + cz.destekler.length + ' destek · 🔴 ' + cz.direncler.length +
       ' direnç · 📏 ' + cz.fibonacci.length + ' fib · 📐 ' + cz.trendler.length +
       ' trend · 📊 ' + cz.formasyon_sayisi + ' formasyon</div>';
  cz.lejant.forEach(function (l) {
    h += '<div class="lg-item"><span class="dot" style="background:' + l.color + '"></span>' + l.label + '</div>';
  });
  el.innerHTML = h;
  el.style.display = 'block';
}

function aiCiz() {
  if (cizildi) { aiTemizle(); return; }
  const cz = DATA.cizimler;
  const all = cz.destekler.concat(cz.direncler, cz.fibonacci, cz.price_lines);
  all.forEach(function (p) {
    const pl = candle.createPriceLine({
      price: p.price, color: p.color, lineWidth: 1, lineStyle: 2,
      axisLabelVisible: true, title: p.title,
    });
    fiyatCizgileri.push(pl);
  });
  cz.trendler.forEach(function (t) {
    const s = chart.addLineSeries({
      color: t.color, lineWidth: 1, lineStyle: 2,
      priceLineVisible: false, lastValueVisible: false,
    });
    s.setData(t.points);
    trendSerileri.push(s);
  });
  if (cz.markers && cz.markers.length) { candle.setMarkers(cz.markers); }
  renderLegend();
  cizildi = true;
  document.getElementById('aiBtn').innerHTML = '🧹 TEMİZLE';
  document.getElementById('aiBtn').classList.add('active');
}

function aiTemizle() {
  fiyatCizgileri.forEach(function (p) { candle.removePriceLine(p); });
  trendSerileri.forEach(function (s) { chart.removeSeries(s); });
  candle.setMarkers([]);
  fiyatCizgileri = [];
  trendSerileri = [];
  document.getElementById('legend').style.display = 'none';
  cizildi = false;
  document.getElementById('aiBtn').innerHTML = '🤖 YZ İLE ÇİZ (Destek/Direnç · Fibonacci · Formasyon)';
  document.getElementById('aiBtn').classList.remove('active');
}

// ── Responsive ──────────────────────────────────────────────────────
window.addEventListener('resize', function () {
  const w = document.getElementById('chart').clientWidth;
  chart.applyOptions({ width: w });
  rsiChart.applyOptions({ width: w });
  macdChart.applyOptions({ width: w });
});
</script>
</body>
</html>
"""

_HTML_SABLON = _HTML_A + _HTML_B + _HTML_C

# ══════════════════════════════════════════════════════════════════════
#  ANA FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════

def tradingview_lw_html(data: pd.DataFrame, sembol: str) -> str:
    """
    TradingView görünümlü (Lightweight Charts) HTML string üretir.
    Kütüphane HTML içine GÖMÜLÜR → Streamlit iframe dahil her ortamda çalışır.
    """
    if data is None or data.empty:
        raise ValueError(f"⚠️ {sembol} için veri bulunamadı!")

    data = _teknik_gostergeleri_hesapla(data.copy())

    # ── Meta bilgiler ──
    son = _sayi(data["Close"].iloc[-1]) or 0.0
    prev = _sayi(data["Close"].iloc[-2]) if len(data) >= 2 else son
    deg = (son - prev) / prev * 100 if prev else 0.0
    deg_renk = YESIL if deg >= 0 else KIRMIZI
    deg_ikon = "▲" if deg >= 0 else "▼"
    safe_sym = sembol.replace(".IS", "")

    # ── Veri + çizimleri JSON'a çevir ──
    lw = _df_to_lw_json(data)
    cizimler = _formasyon_cizimleri(data)
    cz = _cizimleri_json(cizimler, data)

    payload = {
        "candles": lw["candles"],
        "volumes": lw["volumes"],
        "overlays": lw["overlays"],
        "rsi": lw["rsi"],
        "macd": lw["macd"],
        "cizimler": cz,
    }
    json_str = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    # Kütüphaneyi göm (offline + iframe uyumlu)
    kutuphane_js = _kutuphane_js_oku()
    if kutuphane_js:
        kutuphane_script = f"<script>{kutuphane_js}</script>"
    else:
        kutuphane_script = (
            '<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/'
            'dist/lightweight-charts.standalone.production.js"></script>'
        )

    return (_HTML_SABLON
            .replace("__KUTUPHANE_SCRIPT__", kutuphane_script)
            .replace("__DEGISIM_RENK__", deg_renk)
            .replace("__DEGISIM_IKON__", deg_ikon)
            .replace("__DEGISIM__", f"{abs(deg):.2f}")
            .replace("__SON_FIYAT__", f"{son:.2f}")
            .replace("__SEMBOL_TAM__", sembol)
            .replace("__SEMBOL__", safe_sym)
            .replace("__ZAMAN__", datetime.now().strftime("%d.%m.%Y %H:%M"))
            .replace("__JSON_DATA__", json_str))


def tradingview_lw_grafik_olustur(
    data: pd.DataFrame,
    sembol: str,
    output_dir: Optional[str] = None,
    otomatik_ac: bool = False,
) -> str:
    """
    TradingView görünümlü HTML üretir, dosyaya kaydeder ve isteğe bağlı açar.

    Returns:
        HTML dosya yolu
    """
    html = tradingview_lw_html(data, sembol)

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)

    safe_file = sembol.replace(".", "_").replace("^", "")
    dosya_adi = f"tv_{safe_file}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    dosya_yolu = os.path.join(output_dir, dosya_adi)
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ TradingView (Lightweight) grafik kaydedildi: {dosya_yolu}")

    if otomatik_ac:
        webbrowser.open(f"file://{os.path.abspath(dosya_yolu)}")

    return dosya_yolu


def veri_cek_ve_lw_grafik_ac(
    sembol: str,
    period: str = "6mo",
    interval: str = "1d",
    output_dir: Optional[str] = None,
    otomatik_ac: bool = True,
) -> str:
    """
    Yahoo Finance'den veri çeker → Lightweight Charts grafiği oluşturur → açar.

    Parametreler:
        sembol: Hisse sembolü (örn: "THYAO.IS", "AAPL")
        period: "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"
        interval: "1d", "1wk", "1mo"
        output_dir: Çıktı dizini
        otomatik_ac: Tarayıcıda aç
    """
    ticker = yf.Ticker(sembol)
    data = ticker.history(period=period, interval=interval)
    if data is None or data.empty:
        raise ValueError(f"⚠️ {sembol} için veri bulunamadı!")

    return tradingview_lw_grafik_olustur(
        data, sembol, output_dir=output_dir, otomatik_ac=otomatik_ac,
    )


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "THYAO.IS"
    try:
        dosya = veri_cek_ve_lw_grafik_ac(sym, period="6mo", interval="1d", otomatik_ac=True)
        print(f"✅ Tamam: {dosya}")
    except Exception as ex:
        print(f"❌ Hata: {ex}")







