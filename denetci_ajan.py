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
    oneri_id = f"A-{idx:03d}"
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


def kullanici_mesaji_isle(mesaj):
    metin = (mesaj or "").strip()
    if not metin:
        return ""
    sohbet_ekle("kullanici", metin)
    ust = metin.upper()

    if ust in ("TARA", "DENETLE", "KONTROL"):
        ozet = denetim_calistir(telegram_bildir=False)
        yanit = f"Denetim tamamlandi. Yeni uyari: {ozet['yeni_uyarilar']} | Toplam kuyruk: {ozet['toplam_kuyruk']}."
        sohbet_ekle("ajan", yanit)
        return yanit

    if ust in ("DURUM", "OZET"):
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cur = conn.cursor()
        toplam = cur.execute("SELECT COUNT(*) FROM ai_sinyaller").fetchone()[0]
        dagilim = cur.execute("SELECT durum, COUNT(*) FROM ai_sinyaller GROUP BY durum").fetchall()
        conn.close()
        bekleyen_oneri = [x["id"] for x in kuyrugu_getir() if x.get("durum") == "BEKLIYOR"]
        yanit = f"DB Toplam: {toplam} | Dagilim: {dagilim} | Bekleyen Ajan Onerisi: {bekleyen_oneri}"
        sohbet_ekle("ajan", yanit)
        return yanit

    yanit = (
        "Mesajini aldim. Hizli komutlar: 'DURUM' (sistem ve DB ozeti), 'TARA' (anlik denetim). "
        "Bekleyen bir oneriyi asagidaki 'Onayla ve Coz' butonuyla onaylayabilirsin."
    )
    sohbet_ekle("ajan", yanit)
    return yanit
