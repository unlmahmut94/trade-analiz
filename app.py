# ══════════════════════════════════════════════════════════════════════
#  app.py — TradeAnaliz Pro Terminal · v3.0 (EKSİKSİZ TAM SÜRÜM)
# ══════════════════════════════════════════════════════════════════════
#
#  Modüller:
#    mod_gorsel.py       — Global CSS, tema
#    mod_haberler.py     — Haber çekme, çeviri, okuyucu
#    mod_teknik_analiz.py— Teknik indikatör değerleri
#    mod_sirket.py       — Şirket bilgileri
#    mod_tahminler.py    — Analist tahminleri
#    mod_gostergeler.py  — Gösterge rehberi
#    mod_portfoy.py      — Portföy takibi
#    mod_sinyaller.py    — Sinyal görselleştirme
#    mod_filtreleme.py   — Piyasa taraması
#    mod_arama.py        — Hızlı arama
#    mod_yardim.py       — Yardım sekmesi
#    mod_guvenlik.py     — Session, rate limit
#    mod_animasyon.py    — Geçiş efektleri
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import yfinance as yf
import pandas as pd
import json, os
import threading
import time as _time
from mod_dashboard import render_dashboard

# ══════════════════════════════════════════════════════════════════════
#  ARKA PLAN TARAMA MOTORU — Web paneli açık kaldığı sürece çalışır
#  st.cache_resource sayesinde Streamlit her rerun'da YENİ thread açmaz;
#  tarama motoru süreç başına yalnızca 1 kez başlatılır.
# ══════════════════════════════════════════════════════════════════════

@st.cache_resource
def _tarama_motorunu_baslat():
    """Sürekli tarama motorunu (daemon thread) süreç başına 1 kez başlatır."""
    try:
        from otomatik_tarayici import surekli_tarama_dongusu
        _th = threading.Thread(target=surekli_tarama_dongusu, daemon=True, name="scanner-daemon")
        _th.start()
        from mod_logger import yapilandirilmis_logger
        yapilandirilmis_logger("App").info("✅ Tarama motoru arka planda başlatıldı (daemon thread — web paneli açık kaldıkça çalışır)")
        return True
    except Exception as e:
        from mod_logger import yapilandirilmis_logger
        yapilandirilmis_logger("App").warning(f"⚠️ Tarama motoru yüklenemedi: {e}")
        return False


def _arka_plan_taramayi_baslat():
    """Web paneli açılınca tarama motorunu (1 kez) başlatır."""
    _tarama_motorunu_baslat()

from mod_tarama_sekmesi import render_tarama_sekmesi
from mod_yz_arayuz import render_yz_arayuz
from mod_yz_karnesi import render_yz_karnesi 
from mod_bt_arayuz import render_bt_arayuz
from datetime import datetime
from mod_detay_paneli import hisse_analiz_paneli
import analiz
from analiz import tum_hisseleri_tara, tek_hisse_detay, piyasa_havasini_olc
from mod_logger import yapilandirilmis_logger, guvenli_blok
from mod_ortak import (
    hisse_arama_listesi_olustur, render_hisse_arama,
    degisim_renk_ve_ok, degisim_arkaplan,
    session_guvenli_get, session_guvenli_set,
    POPULER_HISSELER, POPULER_HABER_SEMBOLLERI
)
from mod_config import config_al

_app_logger = yapilandirilmis_logger("App")

# Çeviri modülü - güvenli import
CEVIRI_AKTIF = guvenli_blok(
    lambda: __import__('deep_translator', fromlist=['GoogleTranslator']) or True,
    varsayilan_donus=False, modul_adi="App", log_seviyesi="warning"
)

# ── Veri & Grafik ─────────────────────────────────────────────────────
from hisseler_bist   import BIST
from hisseler_sp500  import SP500
from hisseler_nasdaq import NASDAQ
import backtest
from hisse_isimleri  import HISSE_ISIMLERI
from grafik          import (
    tablo_goster, yukselenler_grafik, dusenler_grafik,
    rsi_dagilim_grafik, sinyal_pasta_grafik,
    portfoy_performans_grafik, guclu_al_grafik, ana_grafik
)
import plotly.graph_objects as go

# ── Modüller ──────────────────────────────────────────────────────────
from mod_gorsel       import uygula_tema, sidebar_gizle
from mod_haberler     import haber_paneli, dashboard_haber_paneli, haber_cevir, tum_sistemi_haber_tara
from mod_teknik_analiz import teknik_analiz_paneli
from mod_sirket       import sirket_paneli
from mod_tahminler    import tahminler_paneli
from mod_gostergeler  import gosterge_referansi
from mod_portfoy      import portfoy_yukle, portfoy_kaydet
from mod_yardim       import yardim_paneli
from mod_guvenlik     import session_baslat
from mod_animasyon    import gecis_css, bolum_baslik
try:
    from mod_telegram import telegram_mesaj_gonder
except ImportError:
    def telegram_mesaj_gonder(mesaj):
        pass

# ══════════════════════════════════════════════════════════════════════
#  SAYFA AYARLARI
# ══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="TradeAnaliz Pro",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Tarama motorunu başlat — set_page_config() ilk Streamlit komutu olmalı,
# bu yüzden bu çağrı ondan SONRA yapılır.
_arka_plan_taramayi_baslat()

# 🔥 OPTIMIZE: 5 dakikada bir sessiz arka plan veri yenileme.
# Sayfa sönükleşmesini engellemek için sadece cache temizlenir,
# kullanıcı etkileşimi olmadan veriler güncellenir.


# ── CSS & Animasyonlar ────────────────────────────────────────────────
uygula_tema()
st.markdown("""
<style>
    /* 🔥 RERUN SÖNÜKLEŞMESİNİ ENGELLE */
    body { transition: none !important; }
    .stApp { transition: none !important; opacity: 1 !important; }
    iframe { transition: none !important; }
    
    /* Ana içerik tam genişlik */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
gecis_css()
st.markdown("""
<style>
/* --- TRADEANALİZ ÖZEL ARAMA KUTUSU TASARIMI --- */
div[data-baseweb="select"] > div {
    background-color: rgba(10, 18, 36, 0.8) !important;
    border: 1px solid rgba(77, 184, 255, 0.2) !important;
    border-radius: 8px !important;
    color: #d1d4dc !important;
}
div[data-baseweb="select"] > div:hover {
    border-color: rgba(77, 184, 255, 0.5) !important;
}
div[data-baseweb="select"] > div:focus-within {
    border-color: #f0c040 !important;
    box-shadow: 0 0 8px rgba(240, 192, 64, 0.3) !important;
}
div[data-baseweb="select"] [data-text="true"] {
    color: #787b86 !important;
}
div[data-baseweb="popover"] > div {
    background-color: #0f1c32 !important;
    border: 1px solid rgba(77, 184, 255, 0.2) !important;
    border-radius: 8px !important;
}
ul[role="listbox"] li {
    color: #d1d4dc !important;
    background-color: transparent !important;
    transition: background-color 0.2s ease;
}
ul[role="listbox"] li:hover, ul[role="listbox"] li[aria-selected="true"] {
    background-color: rgba(240, 192, 64, 0.15) !important;
    color: #f0c040 !important;
}
</style>
""", unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════
session_baslat(portfoy_yukle_fn=portfoy_yukle)
   
# ══════════════════════════════════════════════════════════════════════
#  BAŞLIK — Üst logo bar (st.sidebar KULLANILMAZ)
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="padding:16px 0 8px 0;border-bottom:1px solid rgba(30,51,85,0.25);
            background:linear-gradient(180deg,rgba(240,192,64,0.03) 0%,transparent 100%);
            margin-bottom:12px;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div>
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:22px;font-weight:800;
                  color:var(--txt1);letter-spacing:-.03em;">
        Trade<span style="color:var(--gold);">Analiz</span>
      </span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);
                  letter-spacing:.3em;margin-left:12px;text-transform:uppercase;">
        Pro Terminal · v3.1
      </span>
    </div>
    <div id="canli-saat-ust" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--txt3);letter-spacing:.1em;">
      --:--:--
    </div>
  </div>
</div>
<script>
(function updateClockTop() {{
  var now = new Date();
  var h = now.getHours().toString().padStart(2,'0');
  var m = now.getMinutes().toString().padStart(2,'0');
  var s = now.getSeconds().toString().padStart(2,'0');
  var el = document.getElementById('canli-saat-ust');
  if(el) el.textContent = '🟢 SYS · ' + h + ':' + m + ':' + s + ' · LIVE';
  setTimeout(updateClockTop, 1000);
}})();
</script>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  HIZLI ARAMA ÇUBUĞU (üst bar altında inline) — Premium Selectbox
# ══════════════════════════════════════════════════════════════════════
c_ara1, c_ara2 = st.columns([1, 5])
with c_ara1:
    st.caption("🔎 Hızlı Arama")
with c_ara2:
    hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
    populerler = [
        "THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.",
        "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation",
        "KCHOL.IS - Koç Holding", "TSLA - Tesla Inc.",
        "META - Meta Platforms", "AMZN - Amazon.com",
        "MSFT - Microsoft Corp.", "GOOGL - Alphabet Inc."
    ]
    kalanlar = [h for h in hisse_secenekleri if h not in populerler]
    arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

    sb_ara = st.selectbox(
        "Hızlı Arama",
        options=arama_listesi,
        index=None,
        placeholder="🔍 Hisse adı veya sembol yazın... (THYAO, AAPL, Garanti...)",
        key="sb_ara_smart",
        label_visibility="collapsed"
    )

    if sb_ara and "---" not in sb_ara:
        secilen_sembol = sb_ara.split(" - ")[0]
        if st.session_state.get("secilen_hisse") != secilen_sembol:
            st.session_state.secilen_hisse = secilen_sembol
            st.session_state.aktif_sekme = 2  # ANALİZ sekmesine otomatik geç
            st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  SEKMELER — 🔥 OPTİMİZE: Sadece aktif sekme render edilir
# ══════════════════════════════════════════════════════════════════════

TAB_ISIMLERI = [
    "DASHBOARD", "TARAMA", "ANALİZ", "YZ (ML)", 
    "KARNE", "TEST", "PORTFÖY", "HABER", "YARDIM"
]

# Session state'te aktif sekmeyi tut
if "aktif_sekme" not in st.session_state:
    st.session_state.aktif_sekme = 0

# Sekme butonlarını hızlı CSS-only yatay menü olarak göster
cols = st.columns(len(TAB_ISIMLERI))
for i, (col, isim) in enumerate(zip(cols, TAB_ISIMLERI)):
    with col:
        is_active = (st.session_state.aktif_sekme == i)
        btn_style = (
            "background:rgba(240,192,64,0.1);color:var(--gold);font-weight:700;"
            if is_active else
            "background:transparent;color:var(--txt3);"
        )
        st.markdown(f"""
        <style>
        div[data-testid="stElementContainer"]:has(button[key="tab_btn_{i}"]) {{
            margin-bottom: -1px !important;
        }}
        button[key="tab_btn_{i}"] {{
            width: 100% !important;
            {btn_style}
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
            border-radius: 6px !important;
            padding: 8px 2px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 7px !important;
            letter-spacing: .04em !important;
            cursor: pointer !important;
            transition: all .15s ease !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }}
        button[key="tab_btn_{i}"]:hover {{
            border: none !important;
            color: var(--gold) !important;
            background: rgba(240,192,64,0.08) !important;
            outline: none !important;
            box-shadow: none !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button(isim, key=f"tab_btn_{i}", use_container_width=True):
            st.session_state.aktif_sekme = i
            st.rerun()

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# 🔥 SADECE AKTİF SEKMEYİ RENDER ET — Diğerleri hiç çalıştırılmaz
aktif = st.session_state.aktif_sekme

if aktif == 0:
    render_dashboard()

elif aktif == 1:
    render_tarama_sekmesi()

elif aktif == 2:
    # ── HİSSE ANALİZİ ──
    _, ara_col2, _ = st.columns([1, 3, 1])
    with ara_col2:
        hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
        populerler = ["THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.", "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation", "KCHOL.IS - Koç Holding"]
        kalanlar = [h for h in hisse_secenekleri if h not in populerler]
        arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

        tab2_secim = st.selectbox("Hisse Ara veya Seç:", options=arama_listesi, index=None, placeholder="🔍 Analiz etmek istediğiniz hisseyi seçin...", key="tab2_hisse_smart", label_visibility="collapsed")
        
        if tab2_secim and "---" not in tab2_secim:
            secilen_sembol = tab2_secim.split(" - ")[0]
            if st.session_state.get("secilen_hisse") != secilen_sembol:
                st.session_state.secilen_hisse = secilen_sembol
                st.rerun()
    if st.session_state.secilen_hisse:
        hisse_analiz_paneli(st.session_state.secilen_hisse, key_prefix="tab2")
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-family:'Sora',sans-serif;font-size:44px;font-weight:800;color:var(--border);">
            HİSSE ANALİZİ
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                      letter-spacing:.2em;margin-top:12px;text-transform:uppercase;">
            Yukarıdan hisse ara veya dashboard'dan tıkla
          </div>
        </div>
        """, unsafe_allow_html=True)

elif aktif == 3:
    render_yz_arayuz()

elif aktif == 4:
    render_yz_karnesi()

elif aktif == 5:
    render_bt_arayuz()

elif aktif == 6:
    from mod_portfoy import portfoy_paneli
    portfoy_paneli()

elif aktif == 7:
    # ── HABERLER ──
    bolum_baslik("Piyasa Haberleri")
    h1, h2 = st.columns([4, 1])
    with h1:
        h_hisse = st.text_input("Hisse Sembolü", placeholder="Hisse sembolü girin... (Örn: AAPL, THYAO.IS)",
                                 label_visibility="collapsed", key="h_hisse")
    with h2:
        if st.button("HABERLERİ GETİR", use_container_width=True):
            if h_hisse:
                st.session_state.haber_pop = h_hisse.strip().upper()

    st.markdown("---")
    st.markdown('<span class="section-label">Hızlı Erişim</span>', unsafe_allow_html=True)
    pop_s = [
        "THYAO.IS","GARAN.IS","AAPL","NVDA","TSLA","META",
        "AMZN","MSFT","GOOGL","PLTR","COIN","RBLX",
        "AMD","NFLX","SNOW","CRWD","BABA","SHOP"
    ]
    for row in range(0, len(pop_s), 6):
        cols = st.columns(6)
        for i in range(6):
            idx = row + i
            if idx < len(pop_s):
                sym = pop_s[idx]
                with cols[i]:
                    if st.button(sym.replace(".IS",""), key=f"h_pop_{sym}", use_container_width=True):
                        st.session_state.haber_pop = sym

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    secili_sembol = st.session_state.get("haber_pop") or "AAPL"
    
    st.markdown(f'<span class="section-label" style="color:var(--gold);">{secili_sembol} - Genişletilmiş Haber Akışı</span>', unsafe_allow_html=True)
    
    # 🔥 OPTİMİZE: Haberleri cache'le (5dk)
    @st.cache_data(ttl=300, show_spinner=False)
    def _haber_cache(sembol):
        return tum_sistemi_haber_tara((sembol,))
    
    with st.spinner(f"{secili_sembol} için küresel kaynaklar taranıyor..."):
        ozel_haberler = _haber_cache(secili_sembol)
        
    if ozel_haberler:
        goruldu = set()
        h_cols = st.columns(2)
        kutu_sayaci = 0
        
        for hb in ozel_haberler:
            if not hb["baslik"] or hb["baslik"] in goruldu:
                continue
            goruldu.add(hb["baslik"])
            if kutu_sayaci >= 16: break
            
            with h_cols[kutu_sayaci % 2]:
                st.markdown(f"""
                <div style="background:rgba(10,18,36,0.6);border:1px solid rgba(255,255,255,0.05);
                            border-top:2px solid var(--blue);border-radius:8px;padding:16px;margin-bottom:14px;
                            height:140px; overflow:hidden; position:relative;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--gold);margin-bottom:8px;">
                    ⏱ {hb['zaman']} &nbsp;<span style="color:rgba(255,255,255,0.2)">|</span>&nbsp; <span style="color:var(--txt3)">{hb['yayinci']}</span>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:600;color:var(--txt1);line-height:1.4;margin-bottom:8px;">
                    {hb['baslik']}
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt2);line-height:1.5; opacity:0.8;">
                    {hb.get('ozet', 'Haberin detaylarını okumak için kaynağa gidin.')[:90]}...
                  </div>
                  {'<a href="' + hb["url"] + '" target="_blank" style="position:absolute; bottom:12px; right:16px; font-family:JetBrains Mono,monospace;font-size:9px;color:var(--gold);text-decoration:none;letter-spacing:.1em; background:rgba(240,192,64,0.1); padding:4px 8px; border-radius:4px;">KAYNAĞA GİT ↗</a>' if hb.get("url") else ''}
                </div>
                """, unsafe_allow_html=True)
            kutu_sayaci += 1
    else:
        st.info("Bu hisse için şu anda yeni bir haber akışı bulunmuyor.")

elif aktif == 8:
    yardim_paneli()

# === PIYASA DENETCISI (??) SOHBET PENCERESI ===
def _ajan_konum_oku():
    import json, os
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ajan_konum.json')
    varsayilan = {'dock': 'right', 'top': 80}
    if not os.path.exists(yol):
        return varsayilan
    try:
        with open(yol, 'r', encoding='utf-8') as f:
            d = json.load(f)
            varsayilan.update(d)
    except Exception:
        pass
    return varsayilan


def _ajan_konum_yaz(veri):
    import json, os
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ajan_konum.json')
    try:
        with open(yol, 'w', encoding='utf-8') as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _ajan_arka_plan_baslat():
    if st.session_state.get('_ajan_bg_started'):
        return
    st.session_state['_ajan_bg_started'] = True
    try:
        import threading, time
        from denetci_ajan import denetim_calistir
        def _dongu():
            while True:
                time.sleep(900)
                try:
                    denetim_calistir(telegram_bildir=False)
                except Exception:
                    pass
        threading.Thread(target=_dongu, daemon=True, name='piyasa-denetci-daemon').start()
        try:
            from trade_ia_telegram import telegram_dinleyici_dongusu
            threading.Thread(target=telegram_dinleyici_dongusu, daemon=True, name="trade-ia-telegram-daemon").start()
        except Exception:
            pass

    except Exception:
        pass


def render_piyasa_denetcisi_ui():
    _ajan_arka_plan_baslat()
    try:
        from denetci_ajan import (
            kuyrugu_getir,
            sohbet_gecmisi_getir,
            onayla_oneriyi,
            reddet_oneriyi,
            kullanici_mesaji_isle,
            denetim_calistir,
        )
    except Exception as e:
        st.warning('Piyasa Denetcisi yuklenemedi: ' + str(e))
        return

    if 'piyasa_denetci_acik' not in st.session_state:
        st.session_state['piyasa_denetci_acik'] = False
    if 'ajan_konum' not in st.session_state:
        st.session_state['ajan_konum'] = _ajan_konum_oku()

    konum = st.session_state['ajan_konum']
    dock = konum.get('dock', 'right')
    top_px = int(konum.get('top', 80))

    kuyruk = kuyrugu_getir()
    bekleyenler = [x for x in kuyruk if x.get('durum') == 'BEKLIYOR']
    etiket = '📈 ' + str(len(bekleyenler)) if bekleyenler else '📈'

    side_css = 'left: 16px; right: auto;' if dock == 'left' else 'right: 16px; left: auto;'
    st.markdown('''
        <style>
        .st-key-btn_piyasa_denetci_toggle {
            position: fixed !important;
            top: ''' + str(top_px) + '''px !important;
            ''' + side_css + '''
            z-index: 999999 !important;
            width: auto !important;
        }
        .st-key-btn_piyasa_denetci_toggle button {
            min-height: 44px !important;
            height: 44px !important;
            padding: 0 14px !important;
            font-size: 16px !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            background: #0f172a !important;
            color: #f8fafc !important;
            border: 1px solid rgba(148,163,184,0.5) !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.35) !important;
        }
        </style>
    ''', unsafe_allow_html=True)

    if st.button(etiket, key='btn_piyasa_denetci_toggle', help='Piyasa Denetcisi Penceresini Ac / Kapat'):
        st.session_state['piyasa_denetci_acik'] = not st.session_state['piyasa_denetci_acik']
        st.rerun()

    if not st.session_state['piyasa_denetci_acik']:
        return

    if dock == 'left':
        ana_kol, yan_kol = st.columns([4, 6])
        pencere_kol = ana_kol
    else:
        yan_kol, ana_kol = st.columns([6, 4])
        pencere_kol = ana_kol

    with pencere_kol:
        with st.container(border=True):
            h1, h2, h3, h4 = st.columns([4, 2, 2, 2])
            with h1:
                st.markdown('### 📈 Piyasa Denetcisi')
                st.caption('Konum: ' + ('SOL' if dock == 'left' else 'SAG') + ' | Bekleyen: ' + str(len(bekleyenler)))
            with h2:
                if st.button('Sola Al', key='btn_ajan_sol'):
                    konum['dock'] = 'left'
                    st.session_state['ajan_konum'] = konum
                    _ajan_konum_yaz(konum)
                    st.rerun()
            with h3:
                if st.button('Saga Al', key='btn_ajan_sag'):
                    konum['dock'] = 'right'
                    st.session_state['ajan_konum'] = konum
                    _ajan_konum_yaz(konum)
                    st.rerun()
            with h4:
                if st.button('✕ Kapat', key='btn_ajan_kapat'):
                    st.session_state['piyasa_denetci_acik'] = False
                    st.rerun()

            if st.button('Simdi Denetle', key='btn_ajan_simdi_tara'):
                ozet = denetim_calistir(telegram_bildir=False)
                st.success('Yeni: ' + str(ozet['yeni_uyarilar']) + ' | Kuyruk: ' + str(ozet['toplam_kuyruk']))
                st.rerun()

            st.markdown('**Bekleyen Oneriler (Cozeyim mi?)**')
            if not bekleyenler:
                st.info('Su an onay bekleyen yeni bir uyari yok.')
            else:
                for item in bekleyenler:
                    oid = str(item.get('id', ''))
                    baslik = str(item.get('baslik', ''))
                    sorun = str(item.get('sorun', ''))
                    cozum = str(item.get('cozum', ''))
                    st.markdown('- **' + oid + ' - ' + baslik + '**: ' + sorun + '  \n  *Oneri:* ' + cozum)
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button('Onayla ve Coz', key='onayla_' + oid):
                            sonuc = onayla_oneriyi(oid)
                            st.success(sonuc)
                            st.rerun()
                    with b2:
                        if st.button('Reddet', key='reddet_' + oid):
                            sonuc = reddet_oneriyi(oid)
                            st.info(sonuc)
                            st.rerun()

            st.divider()
            st.markdown('**Sohbet Gecmisi**')
            for m in sohbet_gecmisi_getir()[-10:]:
                rol = m.get('kim') or ('📈 Denetci' if m.get('rol') == 'ajan' else 'Sen')
                st.markdown('**' + rol + '** *(' + str(m.get('zaman', '')) + ')*: ' + str(m.get('mesaj', '')))

            with st.form('form_piyasa_denetci_sohbet', clear_on_submit=True):



                # --- Etiketsiz Ozet + Evet/Hayir Kutucugu + Serbest Yazma ---
                try:
                    from denetci_ajan import mesaj_ve_onay_isle as _mvo_isle, taslak_oku as _t_oku, taslak_onayla as _t_onayla, taslak_reddet as _t_reddet
                    _aktif_taslak = _t_oku()
                    if _aktif_taslak:
                        st.info('Bunu mu demek istediniz?\n\n**' + str(_aktif_taslak.get('ozet', '')) + '**\n\nIsterseniz asagidaki **Evet / Hayir** kutucuklarina basin veya hicbirine basmadan dogrudan yeni yazinizi girin.')
                        c_evet, c_hayir = st.columns(2)
                        with c_evet:
                            if st.button('Evet', key='btn_taslak_evet', use_container_width=True):
                                _t_onayla(kaynak='Web')
                                st.rerun()
                        with c_hayir:
                            if st.button('Hayir', key='btn_taslak_hayir', use_container_width=True):
                                _t_reddet(kaynak='Web')
                                st.rerun()
                except Exception:
                    pass
                girdi = st.text_input('Mesaj yaz (@denetci, @ollama veya @ikisi):', key='input_ajan_mesaj')
                gonderildi = st.form_submit_button('Gonder')
                if gonderildi and girdi:
                    kullanici_mesaji_isle(girdi)
                    st.rerun()


try:
    render_piyasa_denetcisi_ui()
except Exception:
    pass
