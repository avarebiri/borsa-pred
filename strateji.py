"""
Ortak yardimci fonksiyonlar:
  - strateji sinyali hesaplama (tek yerde, hem canli hem backtest kullanir)
  - Telegram'a mesaj gonderme
Strateji mantigini TEK yerde tutmak onemli: boylece backtest ettigin sey
ile canlida calisan sey birebir ayni olur.
"""
import urllib.request
import urllib.parse
import pandas as pd
import config


def sinyalleri_hesapla(df: pd.DataFrame, kisa=None, uzun=None, trend=None) -> pd.DataFrame:
    """
    Verilen fiyat verisine MA'lari ve sinyalleri ekler.
    df    : en az 'Close' sutunu olan bir DataFrame (yfinance ciktisi)
    kisa  : kisa MA periyodu (None -> config.KISA_MA)
    uzun  : uzun MA periyodu (None -> config.UZUN_MA)
    trend : trend filtresi MA periyodu. 0/None -> filtre kapali.
            None ise config'e bakar (TREND_FILTRE acikken TREND_MA).
    Donus: ayni df + 'MA_kisa', 'MA_uzun', 'sinyal' (+varsa 'MA_trend') sutunlari
      sinyal:  1 = ALIS gunu,  -1 = SATIS gunu,  0 = bir sey yok
    """
    kisa = kisa if kisa is not None else config.KISA_MA
    uzun = uzun if uzun is not None else config.UZUN_MA
    if trend is None:
        trend = config.TREND_MA if config.TREND_FILTRE else 0

    df = df.copy()
    df["MA_kisa"] = df["Close"].rolling(kisa).mean()
    df["MA_uzun"] = df["Close"].rolling(uzun).mean()

    # MA'lar dolmadan once sinyal uretME (isinma donemi).
    # Bu donemde ilgili MA'lar NaN'dir; ustunde'yi de NaN birakiyoruz ki
    # isinma sinirinda 0->1 gecisi sahte bir ALIS sinyali uretmesin.
    gecerli = df["MA_uzun"].notna()  # uzun MA, kisa'dan sonra dolar
    # kisa MA, uzun MA'nin ustunde mi?
    ust = df["MA_kisa"] > df["MA_uzun"]

    # Trend filtresi: ek olarak fiyat trend MA'sinin ustunde olmali.
    if trend and trend > 0:
        df["MA_trend"] = df["Close"].rolling(trend).mean()
        gecerli = gecerli & df["MA_trend"].notna()
        ust = ust & (df["Close"] > df["MA_trend"])

    df["ustunde"] = ust.where(gecerli).astype(float)
    # durum degisimi: 0->1 olunca kesisim yukari (ALIS), 1->0 olunca asagi (SATIS)
    # ilk gecerli gunun diff'i NaN cikar -> fillna(0): sinir sahte sinyali olusmaz
    df["sinyal"] = df["ustunde"].diff().fillna(0)
    # diff: +1 -> ALIS, -1 -> SATIS, 0 -> degisim yok
    return df


def son_sinyal(df: pd.DataFrame):
    """
    En son gunde bir sinyal var mi kontrol eder.
    Donus: "ALIS", "SATIS" veya None
    """
    if df.empty or "sinyal" not in df.columns:
        return None
    son = df["sinyal"].iloc[-1]
    if son == 1:
        return "ALIS"
    elif son == -1:
        return "SATIS"
    return None


def telegram_gonder(mesaj: str) -> bool:
    """
    Telegram'a mesaj gonderir. Basariliysa True doner.
    Token/chat_id yoksa ekrana yazar (test modu).
    """
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[TELEGRAM AYARLANMAMIS - mesaj ekrana yaziliyor]")
        print(mesaj)
        print("-" * 40)
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    veri = urllib.parse.urlencode({
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
    }).encode()

    try:
        with urllib.request.urlopen(url, data=veri, timeout=10) as cevap:
            return cevap.status == 200
    except Exception as e:
        print(f"Telegram gonderim hatasi: {e}")
        return False
