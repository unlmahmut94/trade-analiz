from supabase import create_client
import os


def _config_oku(anahtar: str) -> str:
    """Önce ortam değişkenini, sonra Streamlit secrets'ı okur. Yoksa boş döner."""
    deger = os.environ.get(anahtar, "")
    if deger:
        return deger
    try:
        import streamlit as st
        return st.secrets.get(anahtar, "") or ""
    except Exception:
        return ""


# Önce GitHub Actions ortamından (env) okumayı dene, yoksa Streamlit secrets'a bak
SUPABASE_URL = _config_oku("SUPABASE_URL")
SUPABASE_KEY = _config_oku("SUPABASE_KEY")

# Kimlik bilgileri yoksa istemci OLUŞTURMA — import çökmesin, tarama yine çalışsın.
SUPABASE_AKTIF = bool(SUPABASE_URL and SUPABASE_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_AKTIF else None