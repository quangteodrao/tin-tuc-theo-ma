"""
T8 -- Trang tin theo ma co phieu.
Chon mot ma trong danh muc demo, xem tin cong khai da duoc gan ma (tang article_tickers).

Chay web that:      streamlit run app_t8.py
Chi kiem tra ket noi (khong can cai streamlit): python3 app_t8.py --check

Cau hinh (khong hardcode key trong code):
  - Khi chay tren Streamlit Community Cloud: dat trong Settings -> Secrets:
        SUPABASE_URL = "https://aujpikjkxjpzlkaaatqm.supabase.co"
        SUPABASE_KEY = "sb_publishable_...."   (publishable key, an toan dung o trinh duyet)
  - Khi chay tren may minh: dat bien moi truong SUPABASE_URL / SUPABASE_KEY,
    hoac copy .env.example thanh .env roi nap bang `export $(cat .env | xargs)`.

Publishable key la key duoc Supabase thiet ke de dung cong khai o phia trinh duyet/client
(khac voi service_role key -- key do TUYET DOI khong duoc dua vao code nay).
Ba bang app nay doc (tickers, articles, article_tickers) da bat RLS cho phep
"ai cung doc duoc" (public SELECT) vi day chi la tin cong khai, khong phai du lieu danh muc rieng tu.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

import requests

VN_TZ = timezone(timedelta(hours=7))

DEFAULT_SUPABASE_URL = "https://aujpikjkxjpzlkaaatqm.supabase.co"


def get_config():
    """Lay SUPABASE_URL / SUPABASE_KEY tu Streamlit secrets (khi deploy) hoac bien moi truong (khi chay tay)."""
    url = None
    key = None
    try:
        import streamlit as st  # import cuc bo de --check khong bat buoc phai cai streamlit
        if hasattr(st, "secrets"):
            url = st.secrets.get("SUPABASE_URL", None)
            key = st.secrets.get("SUPABASE_KEY", None)
    except Exception:
        pass
    url = url or os.environ.get("SUPABASE_URL") or DEFAULT_SUPABASE_URL
    key = key or os.environ.get("SUPABASE_KEY")
    return url, key


def fetch_tickers(base_url: str, api_key: str):
    resp = requests.get(
        f"{base_url}/rest/v1/tickers",
        params={"select": "symbol,name,sector", "active": "eq.true", "order": "symbol.asc"},
        headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_articles_for_symbol(base_url: str, api_key: str, symbol: str, limit: int = 30):
    resp = requests.get(
        f"{base_url}/rest/v1/article_tickers",
        params={
            "select": "symbol,matched_by,articles(title,summary,source,url,published_at)",
            "symbol": f"eq.{symbol}",
            "order": "articles(published_at).desc",
            "limit": str(limit),
        },
        headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def format_vn_time(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    dt_vn = dt.astimezone(VN_TZ)
    return dt_vn.strftime("%H:%M %d/%m/%Y")


def run_check():
    """Kiem tra ket noi that toi Supabase, khong can cai streamlit. Dung truoc khi deploy."""
    url, key = get_config()
    if not key:
        print("LOI: chua co SUPABASE_KEY. Dat bien moi truong SUPABASE_KEY (publishable key) roi chay lai.")
        sys.exit(1)
    print(f"Dang goi thu {url} ...")
    tickers = fetch_tickers(url, key)
    print(f"OK - lay duoc {len(tickers)} ma: {[t['symbol'] for t in tickers]}")
    if tickers:
        sym = tickers[0]["symbol"]
        rows = fetch_articles_for_symbol(url, key, sym, limit=5)
        print(f"OK - ma {sym} co {len(rows)} bai tin gan nhat (lay toi da 5 de kiem tra):")
        for r in rows:
            a = r["articles"]
            print(f"  - [{r['matched_by']}] {format_vn_time(a['published_at'])} | {a['source']} | {a['title']}")
    print("Ket noi thanh cong. Chay `streamlit run app_t8.py` de xem web that.")


def run_app():
    import streamlit as st

    st.set_page_config(page_title="Tin theo ma", page_icon="📰", layout="centered")

    url, key = get_config()
    if not key:
        st.error(
            "Chua cau hinh SUPABASE_KEY. Vao Settings -> Secrets (Streamlit Community Cloud) "
            "hoac dat bien moi truong SUPABASE_KEY (publishable key) roi tai lai trang."
        )
        st.stop()

    st.title("📰 Tin theo mã cổ phiếu")
    st.caption("Công cụ theo dõi nội bộ — không phải khuyến nghị đầu tư.")

    try:
        tickers = fetch_tickers(url, key)
    except Exception as e:
        st.error(f"Không gọi được Supabase: {e}")
        st.stop()

    if not tickers:
        st.warning("Chưa có mã nào trong danh sách theo dõi.")
        st.stop()

    labels = [f"{t['symbol']} — {t['name']} ({t['sector']})" for t in tickers]
    symbol_by_label = {label: t["symbol"] for label, t in zip(labels, tickers)}
    chosen_label = st.selectbox("Chọn mã", labels)
    symbol = symbol_by_label[chosen_label]

    try:
        rows = fetch_articles_for_symbol(url, key, symbol, limit=30)
    except Exception as e:
        st.error(f"Không lấy được tin cho mã {symbol}: {e}")
        st.stop()

    st.subheader(f"Tin liên quan {symbol} ({len(rows)} bài)")

    if not rows:
        st.info(f"Chưa có bài tin nào được gắn cho mã {symbol}.")
        return

    matched_label = {"symbol": "khớp mã", "name": "khớp tên đầy đủ", "alias": "khớp tên gọi khác"}

    for r in rows:
        a = r["articles"]
        with st.container(border=True):
            st.markdown(f"**[{a['title']}]({a['url']})**")
            badge = matched_label.get(r["matched_by"], r["matched_by"])
            st.caption(f"{a['source']} · {format_vn_time(a['published_at'])} · {badge}")
            if a.get("summary"):
                st.write(a["summary"])


def main():
    if "--check" in sys.argv:
        run_check()
    else:
        # Streamlit chay lai toan bo file moi lan tuong tac, nen phan giao dien
        # chi thuc su chay khi duoc goi qua `streamlit run`.
        run_app()


if __name__ == "__main__":
    main()
