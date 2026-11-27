import json
import os
import time
import urllib.request

from denetci_ajan import (
    kullanici_mesaji_isle,
    kuyrugu_getir,
    mesaj_ve_onay_isle,
    onayla_oneriyi,
    reddet_oneriyi,
    taslak_oku,
    taslak_onayla,
    taslak_reddet,
)

OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_offset.txt")


def _offset_oku():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip() or "0")
        except Exception:
            return 0
    return 0


def _offset_yaz(val):
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            f.write(str(int(val)))
    except Exception:
        pass


def telegram_yanit_gonder(token, chat_id, metin, butonlar=None):
    if not token or not chat_id or not metin:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload_dict = {"chat_id": chat_id, "text": str(metin)[:4000]}
    if butonlar:
        payload_dict["reply_markup"] = {"inline_keyboard": butonlar}
    payload = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as _:
            pass
    except Exception:
        pass


def _callback_cevapla(token, callback_id, metin=""):
    if not token or not callback_id:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = json.dumps({"callback_query_id": callback_id, "text": metin}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as _:
            pass
    except Exception:
        pass


def _butonlari_kaldir(token, chat_id, message_id):
    if not token or not chat_id or not message_id:
        return
    url = f"https://api.telegram.org/bot{token}/editMessageReplyMarkup"
    payload = json.dumps(
        {"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}}
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as _:
            pass
    except Exception:
        pass


def telegram_komut_isle(mesaj_metni):
    txt = (mesaj_metni or "").strip()
    if not txt:
        return "", None

    kucuk = txt.lower()
    if not taslak_oku() and kucuk in ("tamam", "ok", "peki", "tesekkurler", "te?ekk?rler", "sagol", "sa?ol", "e"):
        return "Anlasildi, yeni bir komut veya soru yazabilirsin.", None

    yukari = txt.upper()
    if yukari.startswith("/ONAYLA ") or yukari.startswith("ONAYLA "):
        oid = txt.split(None, 1)[1].strip()
        return onayla_oneriyi(oid), None
    if yukari.startswith("/RED ") or yukari.startswith("RED "):
        oid = txt.split(None, 1)[1].strip()
        return reddet_oneriyi(oid), None
    if yukari == "/KUYRUK":
        bekleyen = [x for x in kuyrugu_getir() if x.get("durum") == "BEKLIYOR"]
        if not bekleyen:
            return "Onay bekleyen IA kaydi bulunmuyor.", None
        return "Bekleyen IA Kayitlari:\n" + "\n".join(
            [f"- {x['id']}: {x.get('baslik')} ({x.get('cozum')})" for x in bekleyen]
        ), None

    sonuc = mesaj_ve_onay_isle(txt, kaynak="Telegram")
    if sonuc.get("durum") == "onay_bekliyor":
        butonlar = [
            [
                {"text": "? Evet", "callback_data": "taslak_evet"},
                {"text": "? Hay?r", "callback_data": "taslak_hayir"},
            ]
        ]
        mesaj = f"Bunu mu demek istediniz?\n{sonuc.get('ozet', '')}"
        return mesaj, butonlar

    return sonuc.get("yanit", ""), None


def telegram_guncellemeleri_isle_bir_kez():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    izinli_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        return 0

    offset = _offset_oku()
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=2&offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return 0

    if not data.get("ok"):
        return 0

    islenen = 0
    for upd in data.get("result", []):
        uid = upd.get("update_id", 0)
        if uid >= offset:
            _offset_yaz(uid + 1)

        # 1) Inline buton tiklamasi (Evet / Hayir)
        cb = upd.get("callback_query")
        if cb:
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            cb_msg = cb.get("message") or {}
            gelen_chat = str((cb_msg.get("chat") or {}).get("id") or "")
            msg_id = cb_msg.get("message_id")
            if izinli_chat and gelen_chat and gelen_chat != izinli_chat:
                continue
            _butonlari_kaldir(token, gelen_chat, msg_id)
            if cb_data == "taslak_evet":
                _callback_cevapla(token, cb_id, "Onaylandi, calistiriliyor...")
                yanit = taslak_onayla(kaynak="Telegram")
                telegram_yanit_gonder(token, gelen_chat, yanit)
            elif cb_data == "taslak_hayir":
                _callback_cevapla(token, cb_id, "Iptal edildi.")
                yanit = taslak_reddet(kaynak="Telegram")
                telegram_yanit_gonder(token, gelen_chat, yanit)
            islenen += 1
            continue

        # 2) Normal yazili mesaj
        msg = upd.get("message") or {}
        gelen_chat = str((msg.get("chat") or {}).get("id") or "")
        metin = msg.get("text") or ""
        if izinli_chat and gelen_chat and gelen_chat != izinli_chat:
            continue
        yanit, butonlar = telegram_komut_isle(metin)
        if yanit and gelen_chat:
            telegram_yanit_gonder(token, gelen_chat, yanit, butonlar=butonlar)
            islenen += 1

    return islenen


def telegram_dinleyici_dongusu(aralik_sn=3):
    while True:
        try:
            telegram_guncellemeleri_isle_bir_kez()
        except Exception:
            pass
        time.sleep(aralik_sn)


if __name__ == "__main__":
    print("Trade IA Telegram dinleyicisi (buton destekli) baslatildi...")
    telegram_dinleyici_dongusu(aralik_sn=3)
