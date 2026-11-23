import sqlite3, os

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
SINIR_TARIH = "2026-07-01 00:00:00"

conn = sqlite3.connect(DB_YOLU)
c = conn.cursor()

c.execute("PRAGMA table_info(ai_sinyaller)")
sutunlar = [row[1] for row in c.fetchall()]
sutun_str = ", ".join(sutunlar)

c.execute("CREATE TABLE IF NOT EXISTS ai_sinyaller_arsiv AS SELECT * FROM ai_sinyaller WHERE 0")

c.execute("SELECT COUNT(*) FROM ai_sinyaller WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'", (SINIR_TARIH,))
adet = c.fetchone()[0]

if adet > 0:
    c.execute(f"INSERT OR IGNORE INTO ai_sinyaller_arsiv ({sutun_str}) SELECT {sutun_str} FROM ai_sinyaller WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'", (SINIR_TARIH,))
    c.execute("DELETE FROM ai_sinyaller WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'", (SINIR_TARIH,))
    conn.commit()
    conn.execute("VACUUM;")
    print(f"BASARILI: {adet} adet islem arsivlendi!")
else:
    print("BILGI: Arsivlenecek kayit bulunamadi.")
conn.close()
