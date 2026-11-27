import os
import json
import sqlite3
import datetime
import shutil
import py_compile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ai_hafiza.db")
KUYRUK_PATH = os.path.join(BASE_DIR, "ajan_kuyrugu.json")
SOHBET_PATH = os.path.join(BASE_DIR, "ajan_sohbet.json")
YEDEK_DIR = os.path.join(BASE_DIR, "ajan_yedekler")

KRITIK_DOSYALAR = [
    "app.py",
    "mod_hafiza.py",
    "otomatik_tarayici.py",
    "mod_kripto_scalp.py",
    "mod_piyasa_takvimi.py",
    "mod_telegram.py",
    "mod_haberler.py",
]


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json_oku(path, varsayilan):
    if not os.path.exists(path):
        return varsayilan
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return varsayilan


def _json_yaz(path, veri):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)


def _telegram_gonder_guvenli(metin):
    try:
        from mod_telegram import telegram_mesaj_gonder
        telegram_mesaj_gonder(metin)
        return True
    except Exception as e:
        print(f"[AJAN-TELEGRAM] Gonderim atlandi: {e}")
        return False


def sohbet_gecmisi_getir():
    return _json_oku(SOHBET_PATH, [])


def sohbet_ekle(rol, mesaj):
    gecmis = sohbet_gecmisi_getir()
    gecmis.append({"zaman": _simdi(), "rol": rol, "mesaj": mesaj})
    gecmis = gecmis[-100:]
    _json_yaz(SOHBET_PATH, gecmis)
    return gecmis


def kuyrugu_getir():
    return _json_oku(KUYRUK_PATH, [])


def _uyari_ekle_veya_guncelle(kuyruk, kod, baslik, sorun, cozum_aciklama, eylem_tipi, telegram_bildir=True):
    for item in kuyruk:
        if item.get("kod") == kod and item.get("durum") == "BEKLIYOR":
            item["son_gorulme"] = _simdi()
            return False

    idx = len(kuyruk) + 1
    oneri_id = "IA" if idx == 1 else f"IA{idx - 1}"
    kayit = {
        "id": oneri_id,
        "kod": kod,
        "baslik": baslik,
        "sorun": sorun,
        "cozum": cozum_aciklama,
        "eylem": eylem_tipi,
        "durum": "BEKLIYOR",
        "olusturma": _simdi(),
        "son_gorulme": _simdi(),
    }
    kuyruk.append(kayit)
    mesaj = (
        f"<b>🤖 Ajan Uyarisi ({oneri_id})</b>\n"
        f"<b>{baslik}</b>\n"
        f"Sorun: {sorun}\n"
        f"Oneri: {cozum_aciklama}\n"
        f"<i>Cozeyim mi? Ajan penceresinden onaylayabilirsin.</i>"
    )
    sohbet_ekle("ajan", f"[{oneri_id}] {baslik}\nSorun: {sorun}\nNasil cozeriz: {cozum_aciklama}\nCozeyim mi?")
    if telegram_bildir:
        _telegram_gonder_guvenli(mesaj)
    return True


def denetim_calistir(telegram_bildir=True):
    kuyruk = kuyrugu_getir()
    yeni_uyarilar = 0

    for dosya in KRITIK_DOSYALAR:
        yol = os.path.join(BASE_DIR, dosya)
        if not os.path.exists(yol):
            continue
        try:
            py_compile.compile(yol, doraise=True)
        except Exception as e:
            if _uyari_ekle_veya_guncelle(
                kuyruk,
                kod=f"SYNTAX_{dosya}",
                baslik=f"{dosya} Sozdizimi Hatasi",
                sorun=str(e),
                cozum_aciklama=f"{dosya} dosyasinda sozdizimi hatasi bulundu; yedek alinip incelenmeli.",
                eylem_tipi="BILGI_RAPOR",
                telegram_bildir=telegram_bildir,
            ):
                yeni_uyarilar += 1

    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=15)
            cur = conn.cursor()

            hatali_fiyat = cur.execute("""
                SELECT COUNT(*) FROM ai_sinyaller
                WHERE giris_fiyati IS NULL OR giris_fiyati <= 0
                   OR hedef_fiyat IS NULL OR hedef_fiyat <= 0
                   OR stop_fiyat IS NULL OR stop_fiyat <= 0
                   OR hedef_fiyat <= giris_fiyati
                   OR stop_fiyat >= giris_fiyati
            """).fetchone()[0]

            bekleyen_sayisi = cur.execute(
                "SELECT COUNT(*) FROM ai_sinyaller WHERE durum LIKE 'BEK%YOR'"
            ).fetchone()[0]

            conn.close()

            if hatali_fiyat > 0:
                if _uyari_ekle_veya_guncelle(
                    kuyruk,
                    kod="DB_HATALI_FIYAT",
                    baslik="Veritabaninda Hatali/Ters Fiyatli Sinyaller",
                    sorun=f"ai_sinyaller icinde {hatali_fiyat} adet gecersiz veya ters fiyat/hedef/stop kaydi tespit edildi.",
                    cozum_aciklama="Yedek alip bu hatali kayitlari ai_sinyaller tablosundan temizleyeyim mi?",
                    eylem_tipi="TEMIZLE_HATALI_SINYAL",
                    telegram_bildir=telegram_bildir,
                ):
                    yeni_uyarilar += 1

            if bekleyen_sayisi > 150:
                if _uyari_ekle_veya_guncelle(
                    kuyruk,
                    kod="DB_BEKLEYEN_YIGILMA",
                    baslik="Bekleyen Sinyal Sayisi Yuksek",
                    sorun=f"Su an {bekleyen_sayisi} adet BEKLIYOR durumunda sinyal birikmis gorunuyor.",
                    cozum_aciklama="30 gunden eski BEKLIYOR kayitlarini yedek alip arsiv/zaman asimina cekeyim mi?",
                    eylem_tipi="ARSIVLE_ESKI_BEKLEYEN",
                    telegram_bildir=telegram_bildir,
                ):
                    yeni_uyarilar += 1

        except Exception as e:
            if _uyari_ekle_veya_guncelle(
                kuyruk,
                kod="DB_ERISIM_HATA",
                baslik="Veritabani Kontrol Hatasi",
                sorun=str(e),
                cozum_aciklama="ai_hafiza.db baglantisi ve tablo yapisi kontrol edilmeli.",
                eylem_tipi="BILGI_RAPOR",
                telegram_bildir=telegram_bildir,
            ):
                yeni_uyarilar += 1

    try:
        from mod_piyasa_takvimi import borsa_acik_mi
        bist = borsa_acik_mi("BIST")
        nasdaq = borsa_acik_mi("NASDAQ")
        kripto = borsa_acik_mi("KRIPTO")
        if not bist and not nasdaq and kripto:
            _uyari_ekle_veya_guncelle(
                kuyruk,
                kod="PIYASA_SADECE_KRIPTO",
                baslik="Borsa Saatleri Bilgilendirmesi",
                sorun="BIST ve NASDAQ kapali; yalnizca 7/24 acik olan Kripto piyasasi aktif.",
                cozum_aciklama="Kapali borsalarda gereksiz sinyal kaydi acilmamasi icin mevcut piyasa kilidi aktif tutuluyor.",
                eylem_tipi="BILGI_RAPOR",
                telegram_bildir=False,
            )
    except Exception:
        pass

    _json_yaz(KUYRUK_PATH, kuyruk)
    return {"yeni_uyarilar": yeni_uyarilar, "toplam_kuyruk": len(kuyruk)}


def _db_yedek_al():
    os.makedirs(YEDEK_DIR, exist_ok=True)
    damga = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    hedef = os.path.join(YEDEK_DIR, f"ai_hafiza_{damga}.db")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, hedef)
    return hedef


def onayla_oneriyi(oneri_id):
    kuyruk = kuyrugu_getir()
    hedef_kayit = None
    for item in kuyruk:
        if item.get("id") == oneri_id:
            hedef_kayit = item
            break

    if not hedef_kayit:
        return "Oneri bulunamadi."

    eylem = hedef_kayit.get("eylem")
    sonuc_mesaj = ""

    if eylem == "TEMIZLE_HATALI_SINYAL":
        yedek = _db_yedek_al()
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM ai_sinyaller
            WHERE giris_fiyati IS NULL OR giris_fiyati <= 0
               OR hedef_fiyat IS NULL OR hedef_fiyat <= 0
               OR stop_fiyat IS NULL OR stop_fiyat <= 0
               OR hedef_fiyat <= giris_fiyati
               OR stop_fiyat >= giris_fiyati
        """)
        silinen = cur.rowcount
        conn.commit()
        conn.close()
        sonuc_mesaj = f"Yedek alindi ({os.path.basename(yedek)}). {silinen} hatali/ters sinyal silindi."

    elif eylem == "ARSIVLE_ESKI_BEKLEYEN":
        yedek = _db_yedek_al()
        sinir = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cur = conn.cursor()
        cur.execute("""
            UPDATE ai_sinyaller
            SET durum = 'ZAMAN_ASIMI'
            WHERE durum LIKE 'BEK%YOR' AND tarih < ?
        """, (sinir,))
        guncellenen = cur.rowcount
        conn.commit()
        conn.close()
        sonuc_mesaj = f"Yedek alindi ({os.path.basename(yedek)}). 30 gunden eski {guncellenen} bekleyen sinyal ZAMAN_ASIMI yapildi."

    else:
        sonuc_mesaj = f"[{oneri_id}] Bilgilendirme kaydi onaylandi; otomatik dosya degisikligi gerekmedi."

    hedef_kayit["durum"] = "ONAYLANDI"
    hedef_kayit["islem_zamani"] = _simdi()
    _json_yaz(KUYRUK_PATH, kuyruk)
    sohbet_ekle("ajan", f"Onaylandi ({oneri_id}): {sonuc_mesaj}")
    return sonuc_mesaj


def reddet_oneriyi(oneri_id):
    kuyruk = kuyrugu_getir()
    for item in kuyruk:
        if item.get("id") == oneri_id:
            item["durum"] = "REDDEDILDI"
            item["islem_zamani"] = _simdi()
            _json_yaz(KUYRUK_PATH, kuyruk)
            sohbet_ekle("ajan", f"Reddedildi ({oneri_id}): Islem uygulanmadi.")
            return f"[{oneri_id}] Reddedildi."
    return "Oneri bulunamadi."



def _yerel_llm_sor(kullanici_sorusu, sistem_ozeti):
    import urllib.request
    import json as _json
    try:
        req_tags = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req_tags, timeout=2) as resp:
            tags_data = _json.loads(resp.read().decode("utf-8"))
        modeller = [m.get("name") for m in tags_data.get("models", []) if m.get("name")]
        if not modeller:
            return None
        secilen_model = modeller[0]
        for tercih in ("qwen2.5-coder", "qwen2.5", "llama3.1", "llama3", "gemma2"):
            eslesen = [m for m in modeller if tercih in m.lower()]
            if eslesen:
                secilen_model = eslesen[0]
                break

        prompt = (
            "Sen bir finans analiz ve sistem denetci asistanisin. Kisa, net ve Turkce yanit ver.\n"
            f"Sistem Durumu: {sistem_ozeti}\n"
            f"Kullanici Mesaji: {kullanici_sorusu}"
        )
        payload = _json.dumps({
            "model": secilen_model,
            "prompt": prompt,
            "stream": False
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            cevap = _json.loads(r.read().decode("utf-8")).get("response", "").strip()
        if cevap:
            return f"[{secilen_model}] {cevap}"
    except Exception:
        return None
    return None




def _ortak_gecmis_metni(limit=12):
    gecmis = sohbet_gecmisi_getir()[-limit:]
    satirlar = []
    for m in gecmis:
        kim = m.get("kim") or ("Denetci" if m.get("rol") == "ajan" else "Sen")
        satirlar.append(f"[{m.get('zaman', '')}] {kim}: {m.get('mesaj', '')}")
    return "\n".join(satirlar)


def _sistem_durum_ozeti():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.cursor()
        toplam_s = cur.execute("SELECT COUNT(*) FROM ai_sinyaller").fetchone()[0]
        bekleyen_s = cur.execute("SELECT COUNT(*) FROM ai_sinyaller WHERE durum LIKE 'BEK%YOR'").fetchone()[0]
        conn.close()
    except Exception as e:
        return f"DB okuma hatasi: {e}"
    kuyruk = kuyrugu_getir()
    bekleyen_ia = [f"{x['id']} ({x.get('baslik')})" for x in kuyruk if x.get("durum") == "BEKLIYOR"]
    return f"Toplam sinyal: {toplam_s}, Bekleyen sinyal: {bekleyen_s}, Onay bekleyen IA: {bekleyen_ia or 'Yok'}"


def _denetci_yanit_uret(metin):
    yukari = metin.upper().strip()
    if yukari.startswith("ONAYLA "):
        oid = metin.split(None, 1)[1].strip()
        return onayla_oneriyi(oid)
    if yukari.startswith("RED ") or yukari.startswith("REDDET "):
        oid = metin.split(None, 1)[1].strip()
        return reddet_oneriyi(oid)
    if "TARA" in yukari or "DENETLE" in yukari:
        ozet = denetim_calistir(telegram_bildir=False)
        return f"Denetim tamamlandi. Yeni uyari: {ozet['yeni_uyarilar']} | Kuyruktaki toplam kayit: {ozet['toplam_kuyruk']} | {_sistem_durum_ozeti()}"
    if "DURUM" in yukari or "OZET" in yukari:
        return _sistem_durum_ozeti()
    return f"Emir alindi ({_sistem_durum_ozeti()}). Onay bekleyen kayitlar icin 'ONAYLA IA' veya 'TARA' / 'DURUM' yazabilirsin."


def _ollama_yanit_uret(metin, denetci_notu=""):
    import urllib.request
    import json as _json
    ortak_sohbet = _ortak_gecmis_metni(limit=12)
    sistem_ozeti = _sistem_durum_ozeti()
    try:
        req_tags = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req_tags, timeout=2) as resp:
            tags_data = _json.loads(resp.read().decode("utf-8"))
        modeller = [m.get("name") for m in tags_data.get("models", []) if m.get("name")]
        if not modeller:
            return "Ollama servisi acik ancak henuz model indirilmemis (Ollama_TradeIA_Baslat.bat ile indirilebilir)."
        secilen_model = modeller[0]
        for tercih in ("qwen2.5-coder", "qwen2.5", "llama3.1", "llama3", "gemma2"):
            eslesen = [m for m in modeller if tercih in m.lower()]
            if eslesen:
                secilen_model = eslesen[0]
                break

        prompt = (
            "Sen Trade IA sistemindeki yerel yapay zeka uzmanisin (Ollama). "
            "Sistemde bir de kural tabanli 'Denetci' ajani var ve ikiniz ayni sohbet odasindasiniz. "
            "Kullanicinin izni olmadan dosya veya veritabani degisikligi yapma; oneri sun ve izin iste. "
            "Kisa, net ve Turkce yanit ver.\n\n"
            f"Guncel Sistem Ozeti: {sistem_ozeti}\n"
            f"Ortak Sohbet ve Emir Gecmisi:\n{ortak_sohbet}\n"
        )
        if denetci_notu:
            prompt += f"Denetcinin Az Onceki Ciktisi: {denetci_notu}\n"
        prompt += f"Kullanicinin Son Mesaji: {metin}"

        payload = _json.dumps({
            "model": secilen_model,
            "prompt": prompt,
            "stream": False
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=35) as r:
            cevap = _json.loads(r.read().decode("utf-8")).get("response", "").strip()
        if cevap:
            return f"[{secilen_model}] {cevap}"
    except Exception:
        return "Ollama su an kapali (aktif etmek icin Ollama_TradeIA_Baslat.bat dosyasini acabilirsin)."
    return "Ollama yanit uretemedi."



def sohbet_gecmisi_kaydet(gecmis):
    import json as _json
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ajan_sohbet.json")
    with open(yol, "w", encoding="utf-8") as f:
        _json.dump(gecmis[-200:], f, ensure_ascii=False, indent=2)


def kullanici_mesaji_isle(mesaj, kaynak="Web"):
    metin = (mesaj or "").strip()
    if not metin:
        return ""
    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gecmis = sohbet_gecmisi_getir()
    gecmis.append({"rol": "kullanici", "kim": f"Sen ({kaynak})", "zaman": zaman, "mesaj": metin})

    alcak = metin.lower()
    hedef = "ikisi"
    temiz_metin = metin
    if "@denetci" in alcak and "@ollama" not in alcak:
        hedef = "denetci"
        temiz_metin = metin.replace("@denetci", "").replace("@DENETCI", "").strip() or "DURUM"
    elif "@ollama" in alcak and "@denetci" not in alcak:
        hedef = "ollama"
        temiz_metin = metin.replace("@ollama", "").replace("@OLLAMA", "").strip() or "Durumu yorumla"
    elif "@ikisi" in alcak:
        hedef = "ikisi"
        temiz_metin = metin.replace("@ikisi", "").replace("@IKISI", "").strip() or "DURUM"

    yanitlar = []
    denetci_cevabi = ""

    if hedef in ("denetci", "ikisi"):
        denetci_cevabi = _denetci_yanit_uret(temiz_metin)
        gecmis.append({
            "rol": "ajan",
            "kim": "Denetci",
            "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mesaj": denetci_cevabi,
        })
        yanitlar.append(f"Denetci: {denetci_cevabi}")

    if hedef in ("ollama", "ikisi"):
        ollama_cevabi = _ollama_yanit_uret(temiz_metin, denetci_notu=denetci_cevabi)
        gecmis.append({
            "rol": "ajan",
            "kim": "Ollama",
            "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mesaj": ollama_cevabi,
        })
        yanitlar.append(f"Ollama: {ollama_cevabi}")

    sohbet_gecmisi_kaydet(gecmis)
    return "\n\n".join(yanitlar)


TASLAK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "onay_taslagi.json")


def _niyet_ve_hedef_cozumle(metin):
    alcak = (metin or "").lower().strip()
    if "@denetci" in alcak and "@ollama" not in alcak:
        hedef = "denetci"
        temiz = metin.replace("@denetci", "").replace("@DENETCI", "").strip() or "DURUM"
        return hedef, temiz, True
    if "@ollama" in alcak and "@denetci" not in alcak:
        hedef = "ollama"
        temiz = metin.replace("@ollama", "").replace("@OLLAMA", "").strip() or "Durumu yorumla"
        return hedef, temiz, True
    if "@ikisi" in alcak:
        hedef = "ikisi"
        temiz = metin.replace("@ikisi", "").replace("@IKISI", "").strip() or "DURUM"
        return hedef, temiz, True

    komut_anahtar = ("tara", "denetle", "durum", "ozet", "kuyruk", "onayla", "red", "reddet", "temizle", "yedek")
    yorum_anahtar = ("yorumla", "analiz", "neden", "nasil", "strateji", "risk", "oner", "tavsiye", "degerlendir")

    komut_var = any(k in alcak for k in komut_anahtar)
    yorum_var = any(k in alcak for k in yorum_anahtar)

    if komut_var and yorum_var:
        hedef = "ikisi"
    elif komut_var:
        hedef = "denetci"
    elif yorum_var:
        hedef = "ollama"
    else:
        hedef = "ikisi"

    return hedef, metin.strip(), False


def _niyet_ozeti_olustur(hedef, temiz_metin):
    hedef_etiket = {"denetci": "Denetci", "ollama": "Ollama", "ikisi": "Denetci + Ollama"}.get(hedef, "Denetci + Ollama")
    yukari = temiz_metin.upper()
    if "TARA" in yukari or "DENETLE" in yukari:
        eylem = "Sistem ve veritabani denetimi calistirmak"
    elif "DURUM" in yukari or "OZET" in yukari:
        eylem = "Guncel sinyal, bekleyen kayit ve IA kuyruk durumunu getirmek"
    elif yukari.startswith("ONAYLA "):
        eylem = f"'{temiz_metin}' onerisini onaylayip uygulamak"
    else:
        eylem = f"'{temiz_metin}' istegini islemek"
    return f"Anlasilan ozet: {eylem} | Gorevli: {hedef_etiket}"


def taslak_oku():
    if not os.path.exists(TASLAK_FILE):
        return None
    try:
        with open(TASLAK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("aktif") else None
    except Exception:
        return None


def taslak_yaz(taslak_dict):
    try:
        with open(TASLAK_FILE, "w", encoding="utf-8") as f:
            json.dump(taslak_dict, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def taslak_temizle():
    if os.path.exists(TASLAK_FILE):
        try:
            os.remove(TASLAK_FILE)
        except Exception:
            pass


def _dogrudan_calistir(hedef, temiz_metin, orijinal_mesaj, kaynak="Web"):
    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gecmis = sohbet_gecmisi_getir()
    gecmis.append({"rol": "kullanici", "kim": f"Sen ({kaynak})", "zaman": zaman, "mesaj": orijinal_mesaj})

    yanitlar = []
    denetci_cevabi = ""

    if hedef in ("denetci", "ikisi"):
        denetci_cevabi = _denetci_yanit_uret(temiz_metin)
        gecmis.append({
            "rol": "ajan",
            "kim": "Denetci",
            "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mesaj": denetci_cevabi,
        })
        yanitlar.append(f"Denetci: {denetci_cevabi}")

    if hedef in ("ollama", "ikisi"):
        ollama_cevabi = _ollama_yanit_uret(temiz_metin, denetci_notu=denetci_cevabi)
        gecmis.append({
            "rol": "ajan",
            "kim": "Ollama",
            "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mesaj": ollama_cevabi,
        })
        yanitlar.append(f"Ollama: {ollama_cevabi}")

    sohbet_gecmisi_kaydet(gecmis)
    return "\n\n".join(yanitlar)


def taslak_onayla(kaynak="Web"):
    t = taslak_oku()
    if not t:
        return "Onay bekleyen taslak bulunmuyor."
    taslak_temizle()
    return _dogrudan_calistir(t.get("hedef", "ikisi"), t.get("temiz_metin", ""), t.get("orijinal_mesaj", ""), kaynak=kaynak)


def taslak_reddet(kaynak="Web"):
    t = taslak_oku()
    taslak_temizle()
    if not t:
        return "Iptal edilecek taslak bulunmuyor."
    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gecmis = sohbet_gecmisi_getir()
    gecmis.append({"rol": "kullanici", "kim": f"Sen ({kaynak})", "zaman": zaman, "mesaj": "Hayir (taslak iptal)"})
    gecmis.append({"rol": "ajan", "kim": "Denetci", "zaman": zaman, "mesaj": "Taslak iptal edildi. Yeni istegini yazabilirsin."})
    sohbet_gecmisi_kaydet(gecmis)
    return "Taslak iptal edildi. Yeni istegini yazabilirsin."


def mesaj_ve_onay_isle(mesaj, kaynak="Web", dogrudan_onay=False):
    metin = (mesaj or "").strip()
    if not metin:
        return {"durum": "bos", "yanit": ""}

    # Kullanici ayrica 'evet' veya 'hayir' yazarsa taslagi isler
    kucuk = metin.lower()
    if taslak_oku() and kucuk in ("evet", "evet.", "onay", "tamam"):
        return {"durum": "calisti", "yanit": taslak_onayla(kaynak=kaynak)}
    if taslak_oku() and kucuk in ("hayir", "hay?r", "iptal", "vazgec", "vazge?"):
        return {"durum": "iptal", "yanit": taslak_reddet(kaynak=kaynak)}

    hedef, temiz_metin, etiket_acik = _niyet_ve_hedef_cozumle(metin)
    if dogrudan_onay or etiket_acik:
        taslak_temizle()
        return {"durum": "calisti", "yanit": _dogrudan_calistir(hedef, temiz_metin, metin, kaynak=kaynak)}

    ozet = _niyet_ozeti_olustur(hedef, temiz_metin)
    taslak = {
        "aktif": True,
        "orijinal_mesaj": metin,
        "temiz_metin": temiz_metin,
        "hedef": hedef,
        "ozet": ozet,
        "kaynak": kaynak,
        "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    taslak_yaz(taslak)
    return {"durum": "onay_bekliyor", "ozet": ozet, "taslak": taslak, "yanit": ""}
