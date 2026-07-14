"""
VERI ZENGINLESTIRME
Gemini analistine SADECE fiyat/teknik degil, HABER + TEMEL VERI de vermek icin.
Boylece LLM, momentum/MA taramasinin yapamayacagi bir sey yapabilir (aksi halde
gizli bir teknik tarayiciya indirgenir).

Kaynak: yfinance (ucretsiz). BIST haberleri cogunlukla Ingilizce ama alakali.
Veri her hisse icin garanti degildir; eksikse sessizce atlanir.
"""
import datetime
import yfinance as yf


def _yas_gun(pub):
    """Haber tarihini (epoch int ya da ISO str) 'kac gun once'ye cevirir."""
    if pub is None:
        return None
    try:
        if isinstance(pub, (int, float)):
            t = datetime.datetime.fromtimestamp(pub, tz=datetime.timezone.utc)
        else:
            t = datetime.datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
        simdi = datetime.datetime.now(tz=datetime.timezone.utc)
        return (simdi - t).days
    except Exception:
        return None


def _biçim_büyük(x):
    """marketCap gibi buyuk sayiyi kisa okunur hale getirir (455B TL vb.)."""
    if not x:
        return None
    for esik, ek in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if x >= esik:
            return f"{x / esik:.1f}{ek}"
    return str(int(x))


def zenginlestir(kod: str, haber_n=5, haber_max_gun=14) -> dict:
    """Bir hisse icin {haberler: [(baslik, yas_gun)...], temel: {...}} dondurur.
    Tek Ticker nesnesiyle hem haber hem temel veriyi ceker. Hata olursa bos doner."""
    sonuc = {"haberler": [], "temel": {}}
    try:
        t = yf.Ticker(kod)
    except Exception:
        return sonuc

    # --- Haberler ---
    try:
        for h in (t.news or []):
            c = h.get("content", h)  # yeni/eski yfinance formati
            baslik = c.get("title") or h.get("title")
            if not baslik:
                continue
            pub = c.get("pubDate") or h.get("providerPublishTime")
            yas = _yas_gun(pub)
            if yas is not None and yas > haber_max_gun:
                continue  # cok eski haberi alma
            sonuc["haberler"].append((baslik.strip(), yas))
            if len(sonuc["haberler"]) >= haber_n:
                break
    except Exception:
        pass

    # --- Temel veriler ---
    try:
        info = t.info or {}
        yuzde = lambda v: round(v * 100, 1) if isinstance(v, (int, float)) else None
        sonuc["temel"] = {
            "sektor": info.get("sector"),
            "F/K (trailing)": info.get("trailingPE"),
            "F/K (forward)": info.get("forwardPE"),
            "PD/DD": info.get("priceToBook"),
            "kar_marji_%": yuzde(info.get("profitMargins")),
            "gelir_buyume_%": yuzde(info.get("revenueGrowth")),
            "kar_buyume_%": yuzde(info.get("earningsGrowth")),
            "piyasa_degeri": _biçim_büyük(info.get("marketCap")),
            "temettu_verim_%": info.get("dividendYield"),
        }
        # None alanlari temizle
        sonuc["temel"] = {k: v for k, v in sonuc["temel"].items() if v is not None}
    except Exception:
        pass

    return sonuc


def metin(zengin: dict) -> str:
    """zenginlestir ciktisini Gemini prompt'una eklenecek metne cevirir."""
    parcalar = []
    if zengin.get("temel"):
        parcalar.append("Temel veriler:")
        for k, v in zengin["temel"].items():
            parcalar.append(f"  - {k}: {v}")
    if zengin.get("haberler"):
        parcalar.append("Son haberler (baslik / kac gun once):")
        for baslik, yas in zengin["haberler"]:
            yas_str = f"{yas}g once" if yas is not None else "tarih yok"
            parcalar.append(f"  - [{yas_str}] {baslik}")
    if not parcalar:
        return "(haber/temel veri bulunamadi)"
    return "\n".join(parcalar)


if __name__ == "__main__":
    import sys
    for kod in sys.argv[1:] or ["THYAO.IS", "AAPL"]:
        print(f"\n===== {kod} =====")
        print(metin(zenginlestir(kod)))
