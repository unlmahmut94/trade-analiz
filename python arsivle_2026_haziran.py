import sqlite3
import os

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
SINIR_TARIH = "2026-07-01 00:00:00"  # 2026 6. ay ve öncesi bu tarihten küçüktür

def arsivle():
    if not os.path.exists(DB_YOLU):
        print("❌ ai_hafiza.db bulunamadı!")
        return

    conn = sqlite3.connect(DB_YOLU)
    c = conn.cursor()

    # 1. Arşiv tablosunu ana tablo ile birebir aynı yapıda oluştur
    c.execute('''CREATE TABLE IF NOT EXISTS ai_sinyaller_arsiv
                 (id INTEGER PRIMARY KEY,
                  tarih TEXT,
                  hisse TEXT,
                  sinyal_tipi TEXT,
                  giris_fiyati REAL,
                  hedef_fiyat REAL,
                  stop_fiyat REAL,
                  durum TEXT,
                  kapanis_fiyati REAL)''')

    # 2. 2026 Haziran ve öncesinde kapanmış (BEKLIYOR olmayan) kayıtları say
    c.execute("""
        SELECT COUNT(*) FROM ai_sinyaller 
        WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'
    """, (SINIR_TARIH,))
    adet = c.fetchone()[0]

    if adet == 0:
        print("ℹ️ Arşivlenecek (2026 Haziran ve öncesi kapanmış) kayıt bulunamadı.")
        conn.close()
        return

    # 3. Kayıtları arşiv tablosuna kopyala
    c.execute("""
        INSERT OR IGNORE INTO ai_sinyaller_arsiv 
        (id, tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyat, durum, kapanis_fiyati)
        SELECT id, tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyat, durum, kapanis_fiyati
        FROM ai_sinyaller
        WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'
    """, (SINIR_TARIH,))

    # 4. Arşive aktarılan kayıtları ana tablodan sil
    c.execute("""
        DELETE FROM ai_sinyaller 
        WHERE tarih < ? AND durum NOT LIKE 'BEK%IYOR'
    """, (SINIR_TARIH,))

    conn.commit()
    conn.execute("VACUUM;")  # Veritabanı boyutunu küçült ve optimize et
    conn.close()

    print(f"✅ Başarılı! {adet} adet eski işlem 'ai_sinyaller_arsiv' tablosuna taşındı ve ana karneden çıkarıldı.")

if __name__ == "__main__":
    arsivle()