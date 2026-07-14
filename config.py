"""
Ortak ayarlar dosyasi.
Hisse listesi, strateji parametreleri ve Telegram bilgileri burada.
"""
import os

# .env dosyasini otomatik yukle (python-dotenv yukluyse).
# Boylece config.py'yi elle duzenlemeden TELEGRAM_TOKEN/CHAT_ID okunur.
# Yuklu degilse sessizce gecer; degerleri terminalden de verebilirsin.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# TELEGRAM AYARLARI
# Bu degerleri .env dosyasina yaz, koda dogrudan yazma!
# .env dosyasi ornegi (proje klasorunde .env adli dosya olustur):
#   TELEGRAM_TOKEN=7123456789:AAEabc...
#   TELEGRAM_CHAT_ID=123456789
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# GEMINI (LLM-ANALIST) AYARLARI  - Vertex AI uzerinden
# Kimlik dogrulama: gcloud Application Default Credentials (ADC).
#   Kurulum:  gcloud auth application-default login
# Degerleri .env'den ya da ortam degiskeninden alir; varsayilanlar gcloud
# projenden gelir. AI Studio'ya gecmek istersen GEMINI_BACKEND=aistudio + API key.
# ---------------------------------------------------------------------------
GEMINI_BACKEND = os.getenv("GEMINI_BACKEND", "vertex")          # vertex | aistudio
GEMINI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0581275112")
GEMINI_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")               # sadece aistudio icin
# Analiz modeli. Hizli/ucuz: gemini-2.5-flash ; derin akil: gemini-2.5-pro
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# IZLENECEK HISSELER  (BIST 30 - likit buyuk hisseler)
# YFinance icin .IS uzantisi sart. Listeyi diledigin gibi kisalt/uzat.
# ---------------------------------------------------------------------------
BIST30 = [
    "AKBNK.IS", "ALARK.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS",
    "BIMAS.IS", "BRSAN.IS", "EKGYO.IS", "ENKAI.IS", "EREGL.IS",
    "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS",
    "KCHOL.IS", "KOZAL.IS", "KRDMD.IS", "OYAKC.IS", "PETKM.IS",
    "PGSUS.IS", "SAHOL.IS", "SASA.IS",  "SISE.IS",  "TCELL.IS",
    "THYAO.IS", "TOASO.IS", "TUPRS.IS", "YKBNK.IS", "TTKOM.IS",
]

# ---------------------------------------------------------------------------
# BIST 100 (genis evren)
# Momentum gibi stratejilerin survivorship bias'a karsi daha saglam test
# edilmesi icin daha genis bir liste. NOT: bu da BUGUNUN BIST100'udur,
# yani survivorship bias tamamen ortadan kalkmaz - sadece azalir.
# yfinance'te verisi olmayan/yeni halka arzlar otomatik atlanir.
# ---------------------------------------------------------------------------
BIST100 = [
    "AEFES.IS", "AGHOL.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKFYE.IS",
    "AKSA.IS",  "AKSEN.IS", "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ANSGR.IS",
    "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "AYDEM.IS", "BERA.IS",  "BIENY.IS",
    "BIMAS.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS",
    "CIMSA.IS", "CWENE.IS", "DOAS.IS",  "DOHOL.IS", "ECILC.IS", "ECZYT.IS",
    "EGEEN.IS", "EKGYO.IS", "ENERY.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS",
    "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GLYHO.IS", "GUBRF.IS",
    "GWIND.IS", "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISDMR.IS", "ISGYO.IS",
    "ISMEN.IS", "IZENR.IS", "KARSN.IS", "KCAER.IS", "KCHOL.IS", "KMPUR.IS",
    "KONTR.IS", "KONYA.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS",
    "MAVI.IS",  "MGROS.IS", "MIATK.IS", "MPARK.IS", "ODAS.IS",  "OTKAR.IS",
    "OYAKC.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "REEDR.IS", "SAHOL.IS",
    "SASA.IS",  "SDTTR.IS", "SISE.IS",  "SKBNK.IS", "SMRTG.IS", "SOKM.IS",
    "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS",
    "TSKB.IS",  "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "TURSG.IS",
    "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS",
    "YYLGD.IS", "ZOREN.IS", "ZRGYO.IS", "AGROT.IS",
]

# ---------------------------------------------------------------------------
# ABD HISSELERI (S&P 100 - likit buyuk ABD sirketleri)
# yfinance icin uzanti YOK, dogrudan sembol (AAPL, MSFT...). Para birimi USD.
# Cok-sinifli hisseler yfinance'te tire ile: BRK-B, BF-B.
# NOT: bu da BUGUNUN listesi -> survivorship bias gecerli (ama dusuk enflasyonlu
# USD'de absolute/nakit momentum filtresi TL'nin aksine ANLAMLI calisabilir).
# ---------------------------------------------------------------------------
ABD100 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "BRK-B", "TSLA",
    "AVGO", "JPM",  "LLY",  "V",    "UNH",  "XOM",  "MA",   "JNJ",  "PG",
    "HD",   "COST", "ABBV", "MRK",  "CVX",  "WMT",  "KO",   "PEP",  "BAC",
    "ADBE", "CRM",  "NFLX", "AMD",  "TMO",  "ACN",  "LIN",  "MCD",  "CSCO",
    "ABT",  "DHR",  "WFC",  "TXN",  "QCOM", "DIS",  "INTC", "INTU", "IBM",
    "CAT",  "GE",   "VZ",   "AMGN", "NOW",  "PFE",  "UNP",  "CMCSA", "SPGI",
    "RTX",  "HON",  "LOW",  "GS",   "ISRG", "BKNG", "AXP",  "T",    "NEE",
    "PGR",  "MS",   "BLK",  "ELV",  "SYK",  "MDT",  "GILD", "C",    "BMY",
    "VRTX", "SBUX", "ADP",  "CB",   "MMC",  "DE",   "PLD",  "LRCX", "REGN",
    "TJX",  "MU",   "ETN",  "ADI",  "KLAC", "PANW", "SNPS", "CDNS", "MDLZ",
    "CME",  "SO",   "ZTS",  "MO",   "DUK",  "SHW",  "ICE",  "CL",   "EOG",
    "BSX",  "NKE",  "FDX",  "MMM",  "GD",   "F",    "GM",
]

# Scriptlerin komut satirindan secebilmesi icin evren sozlugu
# (orn. "python momentum.py abd")
EVRENLER = {
    "bist": BIST100,
    "abd": ABD100,
}

# ---------------------------------------------------------------------------
# STRATEJI PARAMETRELERI
# Baslangic stratejisi: Hareketli Ortalama Kesisimi (MA Crossover)
#   - Kisa MA, uzun MA'yi yukari keserse  -> ALIS sinyali
#   - Kisa MA, uzun MA'yi asagi keserse   -> SATIS sinyali
# Bu basit bir baslangic. Amac once boru hattinin calistigini gormek.
# ---------------------------------------------------------------------------
KISA_MA = 20        # kisa hareketli ortalama (gun)
UZUN_MA = 50        # uzun hareketli ortalama (gun)

# TREND FILTRESI (opsiyonel)
# Acikken: sadece fiyat uzun vadeli trend MA'sinin USTUNDEyken ALIS gecerli.
# Amac: dususte (ayi piyasasi) gereksiz al-sat (whipsaw) ve zararlardan kacinmak.
TREND_FILTRE = False    # True yaparsan trend filtresi devreye girer
TREND_MA = 200          # uzun vadeli trend ortalamasi (gun)

# Veri cekme araligi
VERI_PERIYODU = "6mo"    # canli izleme icin son 6 ay yeterli
VERI_ARALIGI = "1d"      # gunluk mumlar

# Backtest icin daha uzun gecmis
BACKTEST_PERIYODU = "3y"
