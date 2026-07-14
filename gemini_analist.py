"""
GEMINI LLM-ANALIST
Bir hissenin son fiyat/teknik verisini Gemini'ye verir; Gemini bir teknik analist
gibi yapilandirilmis (JSON) bir gorus uretir: sinyal + guven + skor + gerekce.
Her cagri 'gemini_log.jsonl' dosyasina yazilir (sonra performansini olcebilmek icin).

GERCEK EMIR YOK. Egitim / kagit-trade / gozlem amaclidir.

Kimlik dogrulama: Vertex AI + ADC (gcloud auth application-default login).
Calistirma:
    python gemini_analist.py            # birkac ornek hisseyi analiz eder
    python gemini_analist.py THYAO.IS   # tek hisse

NOT (cetvel): LLM gecmise backtest EDILEMEZ (model gecmisi bilir -> lookahead).
Bu yuzden analist ILERIYE donuk loglanir; 'skor' alani ortak degerlendirme
motoruna (top-N kagit-trade) baglanabilir.
"""
import sys
import json
import datetime
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

import config
import backtest  # veri_indir
import veri_zengin  # haber + temel veri

LOG_DOSYASI = "gemini_log.jsonl"


# --- Gemini'nin dolduracagi yapilandirilmis cikti semasi -------------------
class HisseSinyali(BaseModel):
    sinyal: Literal["AL", "SAT", "BEKLE"] = Field(description="Kisa vadeli gorus")
    guven: int = Field(ge=0, le=100, description="0-100 arasi guven duzeyi")
    skor: float = Field(
        ge=-1, le=1,
        description="-1 (cok dususu) ile +1 (cok yukselisi) arasi tek sayi; "
                    "siralama/karsilastirma icin kullanilir",
    )
    gerekce: str = Field(description="1-2 cumlelik kisa gerekce, sadece verilen veriye dayali")
    riskler: str = Field(description="Bu gorusu bozabilecek kisa risk notu")


SISTEM_TALIMATI = (
    "Sen disiplinli, temkinli bir hisse analistisisin. Sana bir hissenin TEKNIK "
    "verileri ile (varsa) SON HABERLERI ve TEMEL VERILERI (F/K, buyume, marj, "
    "piyasa degeri vb.) verilir. Uc kaynagi da BIRLIKTE tart: teknik yon momentumu, "
    "temel veri degeri/kaliteyi, haberler ise katalizor/riski gosterir. Sadece sana "
    "verilen bilgiyi kullan, veri UYDURMA; eksik alan olabilir, elindekiyle karar ver. "
    "Teknik ile haber/temel celisirse bunu gerekcede belirt. Sinyal belirsizse 'BEKLE' "
    "de - her hisseye sinyal vermek zorunda degilsin. Bu calisma egitim/kagit-trade "
    "amaclidir, gercek emir verilmez ve yatirim tavsiyesi degildir. Ciktiyi istenen "
    "JSON semasinda ver."
)


# --- Hisseden ozellik cikarma (Gemini'ye verilecek girdi) ------------------
def _g(seri: pd.Series, gun: int):
    """gun kadar onceye gore yuzde getiri (yeterli veri yoksa None)."""
    if len(seri) <= gun:
        return None
    return (seri.iloc[-1] / seri.iloc[-gun - 1] - 1) * 100


def ozellikler(df: pd.DataFrame) -> dict:
    """yfinance df'inden ozet teknik ozellikler uretir."""
    c = df["Close"]
    son = float(c.iloc[-1])
    ma20 = c.rolling(20).mean().iloc[-1]
    ma50 = c.rolling(50).mean().iloc[-1]
    ma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else None
    y52 = float(c.iloc[-252:].max()) if len(c) >= 60 else float(c.max())
    d52 = float(c.iloc[-252:].min()) if len(c) >= 60 else float(c.min())
    hacim_oran = None
    if "Volume" in df.columns and len(df) >= 20:
        v = df["Volume"]
        ort = v.iloc[-20:].mean()
        if ort > 0:
            hacim_oran = float(v.iloc[-1] / ort)

    def yuzde(a, b):
        return None if (a is None or b is None or b == 0) else round((a / b - 1) * 100, 1)

    return {
        "son_fiyat": round(son, 2),
        "getiri_1g_%": round(_g(c, 1), 1) if _g(c, 1) is not None else None,
        "getiri_1h_%": round(_g(c, 5), 1) if _g(c, 5) is not None else None,
        "getiri_1ay_%": round(_g(c, 21), 1) if _g(c, 21) is not None else None,
        "getiri_3ay_%": round(_g(c, 63), 1) if _g(c, 63) is not None else None,
        "fiyat_vs_MA20_%": yuzde(son, ma20),
        "fiyat_vs_MA50_%": yuzde(son, ma50),
        "fiyat_vs_MA200_%": yuzde(son, ma200),
        "52h_yuksege_uzaklik_%": yuzde(son, y52),
        "52h_dusuge_uzaklik_%": yuzde(son, d52),
        "hacim_son_vs_20g_ort": round(hacim_oran, 2) if hacim_oran else None,
    }


# --- Gemini istemcisi ------------------------------------------------------
def istemci():
    """config'e gore Vertex ya da AI Studio istemcisi olusturur."""
    from google import genai
    if config.GEMINI_BACKEND == "aistudio":
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_BACKEND=aistudio ama GEMINI_API_KEY bos.")
        return genai.Client(api_key=config.GEMINI_API_KEY)
    # vertex (ADC kimlik dogrulamasi):  gcloud auth application-default login
    return genai.Client(
        vertexai=True,
        project=config.GEMINI_PROJECT,
        location=config.GEMINI_LOCATION,
    )


def analiz_et(client, kod: str, df: pd.DataFrame, zengin: bool = True) -> HisseSinyali:
    """Bir hisseyi Gemini'ye analiz ettirir, yapilandirilmis sinyal doner.
    zengin=True: teknik veriye ek olarak haber + temel veri de prompt'a eklenir
    (yfinance'ten; hisse basina ekstra cagri = biraz daha yavas)."""
    from google.genai import types

    isim = kod.replace(".IS", "")
    oz = ozellikler(df)
    girdi = (
        f"Hisse: {isim}\n"
        f"Teknik veriler (yuzdeler son fiyata gore):\n"
        + "\n".join(f"  - {k}: {v}" for k, v in oz.items() if v is not None)
    )
    if zengin:
        try:
            girdi += "\n\n" + veri_zengin.metin(veri_zengin.zenginlestir(kod))
        except Exception:
            pass  # zenginlestirme basarisizsa teknikle devam
    girdi += "\n\nTum bu bilgileri tartarak kisa vadeli sinyalini uret."

    cevap = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=girdi,
        config=types.GenerateContentConfig(
            system_instruction=SISTEM_TALIMATI,
            response_mime_type="application/json",
            response_schema=HisseSinyali,
            temperature=0.2,
        ),
    )
    return cevap.parsed


def logla(kod: str, oz: dict, sinyal: HisseSinyali) -> None:
    """Cagriyi JSONL olarak kaydeder (sonra performans olcumu icin)."""
    kayit = {
        "zaman": datetime.datetime.now().isoformat(timespec="seconds"),
        "kod": kod.replace(".IS", ""),
        "model": config.GEMINI_MODEL,
        "son_fiyat": oz.get("son_fiyat"),
        "sinyal": sinyal.sinyal,
        "guven": sinyal.guven,
        "skor": sinyal.skor,
        "gerekce": sinyal.gerekce,
        "riskler": sinyal.riskler,
    }
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def main():
    kodlar = sys.argv[1:] or ["THYAO.IS", "ASELS.IS"]
    print(f"Gemini analist ({config.GEMINI_MODEL}, backend={config.GEMINI_BACKEND})\n")

    try:
        client = istemci()
    except Exception as e:
        print(f"Gemini istemcisi olusturulamadi: {e}")
        print("Vertex icin: gcloud auth application-default login  (ve dogru proje)")
        return

    for kod in kodlar:
        try:
            df = backtest.veri_indir(kod, period="1y")
            if df is None:
                print(f"  {kod}: veri yok, atlandi")
                continue
            oz = ozellikler(df)
            s = analiz_et(client, kod, df)
            logla(kod, oz, s)
            print(f"  {kod.replace('.IS',''):<8} {s.sinyal:<5} "
                  f"(guven {s.guven}, skor {s.skor:+.2f})  {s.gerekce}")
        except Exception as e:
            print(f"  {kod}: HATA -> {e}")

    print(f"\nCagrilar '{LOG_DOSYASI}' dosyasina loglandi.")


if __name__ == "__main__":
    main()
