import os
import time
import json
import urllib.request
from datetime import datetime

from denetci_ajan import kullanici_mesaji_isle, kuyrugu_getir, onayla_oneriyi, reddet_oneriyi

OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_offset.json")


def _ayar_oku():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip()
    env_dosya = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if (not token or not chat_id) and os.path.exists(env_dosya):
        try:
            with open(env_dosya, "r", encoding="utf-8", errors="ignore") as f:
                for satir in f:
                    s = satir.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip().strip('"').strip("'")
                    v = v.strip().strip('"').strip("'")
                    if k == "TELEGRAM_TOKEN" and not token:
                        token = v
                    elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                        chat_id = v
        except Exception:
            pass
    return token, chat_id


def _offset_oku():
    if not os.path.exists(OFFSET_FILE):
        return None
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("offset")
    except Exception:
        return None


def _offset_yaz(offset_val):
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump({"offset": offset_val, "guncelleme": datetime.now().isoformat()}, f)
    except Exception:
        pass


def telegram_yanit_gonder(token, chat_id, metin):
    if not token or not chat_id or not metin:
        return
    parca_boyutu = 3800
    for i in range(0, len(metin), parca_boyutu):
        parca = metin[i:i + parca_boyutu]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": parca}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as _:
                pass
        except Exception:
            pass


def telegram_komut_isle(mesaj_metni):
    from denetci_ajan import mesaj_ve_onay_isle
    txt = (mesaj_metni or "").strip()
    if not txt:
        return ""
    yukari = txt.upper()
    if yukari.startswith("/ONAYLA ") or yukari.startswith("ONAYLA "):
        oid = txt.split(None, 1)[1].strip()
        return onayla_oneriyi(oid)
    if yukari.startswith("/RED ") or yukari.startswith("RED "):
        oid = txt.split(None, 1)[1].strip()
        return reddet_oneriyi(oid)
    if yukari == "/KUYRUK":
        bekleyen = [x for x in kuyrugu_getir() if x.get("durum") == "BEKLIYOR"]
        if not bekleyen:
            return "Onay bekleyen IA kaydi bulunmuyor."
        return "Bekleyen IA Kayitlari:\n" + "\n".join([f"- {x['id']}: {x.get('baslik')} ({x.get('cozum')})" for x in bekleyen])
    sonuc = mesaj_ve_onay_isle(txt, kaynak="Telegram")
    if sonuc.get("durum") == "onay_bekliyor":
        return f"Bunu mu demek istediniz?\n{sonuc.get('ozet', '')}\n\nOnaylamak icin EVET, iptal icin HAYIR yazin veya dogrudan yeni mesajinizi gonderin."
    return sonuc.get("yanit", "")


def telegram_guncellemeleri_isle_bir_kez():
    token, chat_id = _ayar_oku()
    if not token:
        return 0
    offset = _offset_oku()
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=2"
    if offset is not None:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return 0

    if not data.get("ok"):
        return 0

    islenen = 0
    for upd in data.get("result", []):
        upd_id = upd.get("update_id")
        if upd_id is not None:
            _offset_yaz(int(upd_id) + 1)
        msg = upd.get("message") or upd.get("edited_message") or {}
        gelen_chat = str((msg.get("chat") or {}).get("id", "")).strip()
        metin = (msg.get("text") or "").strip()
        if not metin:
            continue
        if chat_id and gelen_chat and gelen_chat != chat_id:
            continue
        yanit = telegram_komut_isle(metin)
        if yanit and gelen_chat:
            telegram_yanit_gonder(token, gelen_chat, yanit)
            islenen += 1
    return islenen


def telegram_dinleyici_dongusu(aralik_sn=5):
    while True:
        try:
            telegram_guncellemeleri_isle_bir_kez()
        except Exception:
            pass
        time.sleep(aralik_sn)


if __name__ == "__main__":
    print("Trade IA Telegram dinleyicisi baslatildi...")
    telegram_dinleyici_dongusu(aralik_sn=5)
