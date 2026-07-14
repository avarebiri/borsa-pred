"""
BACKTEST  (gecmis veride strateji testi)
Ayni MA kesisim stratejisini son 3 yilin verisinde calistirir ve
"Bu kurala uysaydim ne olurdu?" sorusunu cevaplar.

GERCEK PARA YOK. Sadece gecmis fiyatlarla simulasyon.

Calistirma:
    python backtest.py

Cikti: her hisse icin strateji getirisi vs "al ve tut" getirisi,
ayrica risk metrikleri (maksimum dususe / Sharpe / kazanan islem orani).

NOT (survivorship bias): config.BIST30 BUGUNUN endeks listesidir; 3 yil
geriye uygulanir. Gecmiste endekste olmayan/sonradan eklenen hisseler
sonucu iyimser gosterir. Sonuclari bu kisitla yorumla.
"""
import yfinance as yf
import pandas as pd
import config
import strateji

# Basit islem maliyeti varsayimi (komisyon + kayma). Gercekci olmak icin onemli.
ISLEM_MALIYETI = 0.002  # her alis/satista %0.2

# Yillik isgunu sayisi (Sharpe yillistirma icin)
YIL_ISGUNU = 252


def maksimum_dusus(strateji_getiri: pd.Series) -> float:
    """Strateji ozsermaye egrisinin gordugu en buyuk tepe-dip dususu (%)."""
    ozsermaye = (1 + strateji_getiri).cumprod()
    tepe = ozsermaye.cummax()
    dd = (ozsermaye / tepe - 1.0).min()  # en negatif deger
    return float(dd) * 100 if pd.notna(dd) else 0.0


def sharpe_orani(strateji_getiri: pd.Series) -> float:
    """Yillistirilmis Sharpe (risksiz getiri ~0 varsayimiyla)."""
    std = strateji_getiri.std()
    if not std or pd.isna(std) or std == 0:
        return 0.0
    return float(strateji_getiri.mean() / std) * (YIL_ISGUNU ** 0.5)


def islem_istatistikleri(aktif: pd.Series, strateji_getiri: pd.Series):
    """
    Round-trip islemleri ayirir, her birinin getirisini toplar ve
    kazanan islem oranini hesaplar. 'aktif' = o gun pozisyondaysak 1.
    Donus: (islem_sayisi, kazanan_orani_yuzde)
    """
    trade_getirileri = []
    mevcut = None
    for a, g in zip(aktif, strateji_getiri):
        if a == 1:
            mevcut = (mevcut or 0.0) + g  # gunluk getiri toplami (isaret icin yeterli)
        elif mevcut is not None:
            trade_getirileri.append(mevcut)
            mevcut = None
    if mevcut is not None:
        trade_getirileri.append(mevcut)

    if not trade_getirileri:
        return 0, 0.0
    kazanan = sum(1 for t in trade_getirileri if t > 0)
    return len(trade_getirileri), kazanan / len(trade_getirileri) * 100


def metrikleri_hesapla(df: pd.DataFrame) -> dict:
    """
    'Close' ve 'sinyal' sutunlari olan bir df'ten getiri + risk metriklerini
    hesaplar. (Indirme/sinyal uretimi disarida yapilir; bu sayede tarama da
    ayni hesabi kullanir -> backtest ile tarama birebir tutarli kalir.)
    Donus: strateji/al_tut/islem/max_dd/sharpe/kazanan_oran iceren dict.
    """
    df = df.copy()

    # Pozisyon: ALIS sinyalinden sonra 1 (hissedeyiz), SATIS'tan sonra 0 (nakitteyiz)
    pozisyon = 0
    pozisyonlar = []
    for s in df["sinyal"]:
        if s == 1:
            pozisyon = 1
        elif s == -1:
            pozisyon = 0
        pozisyonlar.append(pozisyon)
    df["pozisyon"] = pozisyonlar

    # Gunluk getiri
    df["gunluk_getiri"] = df["Close"].pct_change().fillna(0)
    # Strateji getirisi: sadece pozisyondaysak (bir onceki gunun pozisyonu) getiri aliriz
    df["aktif"] = df["pozisyon"].shift(1).fillna(0)
    df["strateji_getiri"] = df["aktif"] * df["gunluk_getiri"]

    # Islem maliyetini dus (pozisyon her degistiginde)
    df["islem"] = df["pozisyon"].diff().abs().fillna(0)
    df["strateji_getiri"] -= df["islem"] * ISLEM_MALIYETI

    # Kumulatif getiriler
    strateji_toplam = (1 + df["strateji_getiri"]).prod() - 1
    al_tut_toplam = (1 + df["gunluk_getiri"]).prod() - 1
    islem_sayisi = int(df["islem"].sum())

    # Risk metrikleri
    max_dd = maksimum_dusus(df["strateji_getiri"])
    sharpe = sharpe_orani(df["strateji_getiri"])
    _, kazanan_oran = islem_istatistikleri(df["aktif"], df["strateji_getiri"])

    return {
        "strateji": strateji_toplam * 100,
        "al_tut": al_tut_toplam * 100,
        "islem": islem_sayisi,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "kazanan_oran": kazanan_oran,
    }


def veri_indir(kod: str, period=None):
    """Bir hissenin gecmis verisini ceker, sutunlari duzlestirir. Yetersizse None.
    period None ise config.BACKTEST_PERIYODU kullanilir (orn. '8y', 'max')."""
    df = yf.download(
        kod, period=period or config.BACKTEST_PERIYODU,
        interval="1d", progress=False, auto_adjust=True,
    )
    if df.empty or len(df) < config.UZUN_MA + 10:
        return None
    if df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    return df


def tek_hisse_backtest(kod: str):
    """Bir hisse icin stratejiyi (config'deki varsayilan parametrelerle) test eder."""
    df = veri_indir(kod)
    if df is None:
        return None
    df = strateji.sinyalleri_hesapla(df)
    r = metrikleri_hesapla(df)
    r["kod"] = kod.replace(".IS", "")
    return r


def main():
    print(f"Backtest baslıyor... ({config.BACKTEST_PERIYODU}, "
          f"MA{config.KISA_MA}/MA{config.UZUN_MA})\n")
    print(f"{'Hisse':<8}{'Strateji':>11}{'Al&Tut':>11}{'Islem':>7}"
          f"{'MaxDD':>9}{'Sharpe':>8}{'Kazan%':>8}")
    print("-" * 62)

    sonuclar = []
    for kod in config.BIST30:
        try:
            r = tek_hisse_backtest(kod)
            if r is None:
                continue
            sonuclar.append(r)
            print(f"{r['kod']:<8}{r['strateji']:>10.1f}%{r['al_tut']:>10.1f}%"
                  f"{r['islem']:>7}{r['max_dd']:>8.1f}%{r['sharpe']:>8.2f}"
                  f"{r['kazanan_oran']:>7.0f}%")
        except Exception as e:
            print(f"{kod:<8}  hata: {e}")

    if not sonuclar:
        print("\nHic sonuc alinamadi (internet/veri sorunu olabilir).")
        return

    # Ozet
    n = len(sonuclar)
    ort_strateji = sum(r["strateji"] for r in sonuclar) / n
    ort_al_tut = sum(r["al_tut"] for r in sonuclar) / n
    ort_max_dd = sum(r["max_dd"] for r in sonuclar) / n
    ort_sharpe = sum(r["sharpe"] for r in sonuclar) / n
    ort_kazanan = sum(r["kazanan_oran"] for r in sonuclar) / n
    strateji_kazanan = sum(1 for r in sonuclar if r["strateji"] > r["al_tut"])

    print("-" * 62)
    print(f"\n📊 OZET ({n} hisse):")
    print(f"  Ortalama strateji getirisi : {ort_strateji:>7.1f}%")
    print(f"  Ortalama al&tut getirisi   : {ort_al_tut:>7.1f}%")
    print(f"  Ortalama maksimum dusus    : {ort_max_dd:>7.1f}%  (ne kadar sifira yakin o kadar iyi)")
    print(f"  Ortalama Sharpe            : {ort_sharpe:>7.2f}  (>1 iyi, <0 kotu)")
    print(f"  Ortalama kazanan islem     : {ort_kazanan:>7.0f}%")
    print(f"  Strateji {strateji_kazanan}/{n} hissede al&tut'u yendi")
    print(f"\n  ⚠️  Survivorship bias: liste bugunun BIST30'u; gecmise uygulaninca")
    print(f"     sonuclar iyimser cikabilir. MA kesisimi basit bir baslangictir ve")
    print(f"     cogu zaman 'al ve tut'u yenmez - bu normal ve ogretici.")


if __name__ == "__main__":
    main()
