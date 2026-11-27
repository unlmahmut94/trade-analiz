import json
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil

KOK = Path(__file__).resolve().parent
DB_YOLU = KOK / "ai_hafiza.db"
YEDEK_DB_YOLU = KOK / "ai_hafiza_yedek.db"
YEDEK_KLASOR = KOK / "yedekler"
TAKIP_JSON = KOK / "bekleyen_takip_raporu.json"


def _tarih_farki_gun(tarih_str) -> float | None:
    if not tarih_str:
        return None
    s = str(tarih_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        return max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
    except Exception:
        return None


def _risk_hesapla(row: dict) -> tuple[str, int, list[str]]:
    puan = 0
    nedenler = []
    giris = row.get("giris_fiyati")
    hedef = row.get("hedef_fiyat")
    stop = row.get("stop_fiyati")
    gun = _tarih_farki_gun(row.get("tarih"))

    try:
        if giris is not None and str(giris).strip() != "":
            g_val = float(giris)
        else:
            g_val = 0.0

        if stop is not None and str(stop).strip() != "":
            s_val = float(stop)
        else:
            s_val = 0.0

        if hedef is not None and str(hedef).strip() != "":
            h_val = float(hedef)
        else:
            h_val = 0.0

        if g_val > 0 and s_val > 0:
            stop_pct = abs(g_val - s_val) / g_val * 100.0
            if stop_pct >= 6.0:
                puan += 35
                nedenler.append(f"genis stop %{stop_pct:.1f}")
            elif stop_pct >= 3.0:
                puan += 15
                nedenler.append(f"orta stop %{stop_pct:.1f}")
            else:
                puan += 5
                nedenler.append(f"dar stop %{stop_pct:.1f}")
        elif g_val > 0:
            puan += 15
            nedenler.append("stop fiyat yok")

        if g_val > 0 and h_val > 0:
            hedef_pct = abs(h_val - g_val) / g_val * 100.0
            if hedef_pct >= 10.0:
                puan += 20
                nedenler.append(f"hedef uzakligi %{hedef_pct:.1f}")
            else:
                nedenler.append(f"hedef %{hedef_pct:.1f}")
    except (TypeError, ValueError):
        puan += 15
        nedenler.append("fiyat verisi eksik")

    if gun is not None:
        if gun >= 14:
            puan += 30
            nedenler.append(f"{int(gun)} gunluk")
        elif gun >= 3:
            puan += 15
            nedenler.append(f"{int(gun)} gunluk")
        else:
            nedenler.append(f"{gun:.1f} gunluk")

    if puan >= 45:
        seviye = "YUKSEK"
    elif puan >= 20:
        seviye = "ORTA"
    else:
        seviye = "DUSUK"
    return seviye, puan, nedenler


def bekleyen_tara_ve_yorumla(db_yolu: Path = DB_YOLU, limit_oncelik: int = 10) -> dict:
    con = sqlite3.connect(db_yolu)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tum_sayilar = {
        "ai_sinyaller": cur.execute("SELECT COUNT(*) FROM ai_sinyaller").fetchone()[0],
        "ai_sinyaller_arsiv": cur.execute("SELECT COUNT(*) FROM ai_sinyaller_arsiv").fetchone()[0],
    }
    rows = [dict(r) for r in cur.execute("SELECT * FROM ai_sinyaller ORDER BY id ASC").fetchall()]
    con.close()

    bekleyenler = []
    durum_dagilimi = {}
    for r in rows:
        d = str(r.get("durum") or "belirsiz")
        durum_dagilimi[d] = durum_dagilimi.get(d, 0) + 1
        if "bekl" in d.lower() or "aktif" in d.lower() or "pending" in d.lower():
            seviye, puan, nedenler = _risk_hesapla(r)
            bekleyenler.append({**r, "risk_seviyesi": seviye, "risk_puani": puan, "risk_nedenleri": nedenler})

    bekleyenler.sort(key=lambda x: x["risk_puani"], reverse=True)
    risk_ozet = {
        "YUKSEK": sum(1 for x in bekleyenler if x["risk_seviyesi"] == "YUKSEK"),
        "ORTA": sum(1 for x in bekleyenler if x["risk_seviyesi"] == "ORTA"),
        "DUSUK": sum(1 for x in bekleyenler if x["risk_seviyesi"] == "DUSUK"),
    }
    return {
        "tablo_sayilari": tum_sayilar,
        "durum_dagilimi": durum_dagilimi,
        "bekleyen_toplam": len(bekleyenler),
        "risk_ozet": risk_ozet,
        "oncelikli_yuksek_risk": bekleyenler[:limit_oncelik],
        "bekleyen_takip_raporu_mevcut": TAKIP_JSON.exists(),
    }


def bekleyen_yedek_al(db_yolu: Path = DB_YOLU) -> dict:
    YEDEK_KLASOR.mkdir(parents=True, exist_ok=True)
    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    con = sqlite3.connect(db_yolu)
    con.row_factory = sqlite3.Row
    sinyaller = [dict(r) for r in con.execute("SELECT * FROM ai_sinyaller ORDER BY id ASC").fetchall()]
    arsiv = [dict(r) for r in con.execute("SELECT * FROM ai_sinyaller_arsiv ORDER BY id ASC").fetchall()]
    con.close()

    json_yol = YEDEK_KLASOR / f"bekleyen_yedek_{damga}.json"
    json_yol.write_text(
        json.dumps(
            {"olusturulma": damga, "ai_sinyaller": sinyaller, "ai_sinyaller_arsiv": arsiv},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if db_yolu.exists():
        shutil.copy2(db_yolu, YEDEK_DB_YOLU)

    return {
        "json_yedek": str(json_yol.relative_to(KOK)),
        "yedek_db": str(YEDEK_DB_YOLU.relative_to(KOK)),
        "yedeklenen_sinyal_sayisi": len(sinyaller),
    }


def bekleyen_arsivle_veya_zaman_asimi(
    gun_siniri: int = 14,
    sadece_dusuk_orta_risk: bool = True,
    db_yolu: Path = DB_YOLU,
) -> dict:
    yedek = bekleyen_yedek_al(db_yolu)
    con = sqlite3.connect(db_yolu)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = [dict(r) for r in cur.execute("SELECT * FROM ai_sinyaller ORDER BY id ASC").fetchall()]

    arsivlenecek_idler = []
    for r in rows:
        d = str(r.get("durum") or "")
        if "bekl" not in d.lower():
            continue
        gun = _tarih_farki_gun(r.get("tarih"))
        if gun is None or gun < gun_siniri:
            continue
        seviye, _, _ = _risk_hesapla(r)
        if sadece_dusuk_orta_risk and seviye == "YUKSEK":
            continue
        arsivlenecek_idler.append(r["id"])

    tasinan = 0
    if arsivlenecek_idler:
        placeholders = ",".join("?" for _ in arsivlenecek_idler)
        try:
            cur.execute("BEGIN")
            cur.execute(
                f"""
                INSERT INTO ai_sinyaller_arsiv
                    (id, tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyati, durum, kapanis_fiyati)
                SELECT
                    id, tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyati,
                    'zaman_asimi_arsiv',
                    kapanis_fiyati
                FROM ai_sinyaller
                WHERE id IN ({placeholders})
                """,
                arsivlenecek_idler,
            )
            cur.execute(f"DELETE FROM ai_sinyaller WHERE id IN ({placeholders})", arsivlenecek_idler)
            tasinan = cur.rowcount
            con.commit()
        except Exception:
            con.rollback()
            con.close()
            raise

    son_sinyal = cur.execute("SELECT COUNT(*) FROM ai_sinyaller").fetchone()[0]
    son_arsiv = cur.execute("SELECT COUNT(*) FROM ai_sinyaller_arsiv").fetchone()[0]
    con.close()

    return {
        "yedek_bilgisi": yedek,
        "gun_siniri": gun_siniri,
        "tasinan_kayit_sayisi": tasinan,
        "guncel_ai_sinyaller": son_sinyal,
        "guncel_ai_sinyaller_arsiv": son_arsiv,
    }


if __name__ == "__main__":
    yedek = bekleyen_yedek_al()
    print("Yedek alindi:", yedek)
    rapor = bekleyen_tara_ve_yorumla(limit_oncelik=5)
    print("Risk ozeti:", rapor["risk_ozet"])
    for item in rapor["oncelikli_yuksek_risk"]:
        print(f"  - #{item['id']} {item.get('hisse')} ({item.get('tarih')}): {item['risk_seviyesi']} [{', '.join(item['risk_nedenleri'])}]")
