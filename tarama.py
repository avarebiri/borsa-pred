"""
PARAMETRE TARAMASI (strateji guclendirme)
Farkli MA kombinasyonlarini ve trend filtresini AYNI gecmis veride
karsilastirir. Amac: tahmin yerine veriyle "hangi ayar daha iyi?" sorusuna
cevap aramak.

Her hisse YALNIZCA BIR KEZ indirilir; tum kombinasyonlar ayni df uzerinde
hesaplanir (hizli ve adil). Metrikler backtest.py ile birebir aynidir.

Calistirma:
    python tarama.py

UYARI (asiri uydurma / overfitting): En iyi gorunen ayari secip "buldum"
demek tehlikelidir - gecmise en cok uyan ayar gelecekte calismayabilir.
Buradaki amac stratejinin DAVRANISINI anlamak, sihirli sayi bulmak degil.
"""
import yfinance as yf
import config
import strateji
import backtest

# Denenecek kombinasyonlar: (kisa_MA, uzun_MA, trend_MA, etiket)
# trend_MA = 0 -> trend filtresi kapali
KOMBINASYONLAR = [
    (20,  50,   0, "MA20/50  (mevcut)"),
    (20,  50, 200, "MA20/50  + trend200"),
    (10,  30,   0, "MA10/30  (hizli)"),
    (20, 100,   0, "MA20/100 (yavas)"),
    (50, 200,   0, "MA50/200 (golden cross)"),
    (50, 200, 200, "MA50/200 + trend200"),
]


def main():
    print(f"Parametre taramasi... ({config.BACKTEST_PERIYODU}, {len(config.BIST30)} hisse)")
    print("Veriler indiriliyor (her hisse bir kez)...\n")

    # 1) Tum hisseleri bir kez indir
    veriler = {}
    for kod in config.BIST30:
        try:
            df = backtest.veri_indir(kod)
            if df is not None:
                veriler[kod] = df
        except Exception:
            pass
    print(f"{len(veriler)} hisse verisi hazir.\n")

    if not veriler:
        print("Veri alinamadi (internet/veri sorunu).")
        return

    # 2) Al & tut referansi (parametreden bagimsiz, bir kez hesapla)
    al_tut_listesi = []
    for df in veriler.values():
        r = backtest.metrikleri_hesapla(strateji.sinyalleri_hesapla(df, 20, 50, 0))
        al_tut_listesi.append(r["al_tut"])
    ort_al_tut = sum(al_tut_listesi) / len(al_tut_listesi)

    # 3) Her kombinasyonu test et
    print(f"{'Strateji':<26}{'Getiri':>9}{'Sharpe':>8}{'MaxDD':>9}"
          f"{'Kazan%':>8}{'Islem':>7}{'A&T yendi':>11}")
    print("-" * 78)

    en_iyi = None
    for kisa, uzun, trend, etiket in KOMBINASYONLAR:
        sonuclar = []
        for df in veriler.values():
            if len(df) < uzun + 10:
                continue
            try:
                d = strateji.sinyalleri_hesapla(df, kisa, uzun, trend)
                sonuclar.append(backtest.metrikleri_hesapla(d))
            except Exception:
                continue
        if not sonuclar:
            continue
        n = len(sonuclar)
        ort_get = sum(r["strateji"] for r in sonuclar) / n
        ort_shp = sum(r["sharpe"] for r in sonuclar) / n
        ort_dd = sum(r["max_dd"] for r in sonuclar) / n
        ort_kaz = sum(r["kazanan_oran"] for r in sonuclar) / n
        ort_islem = sum(r["islem"] for r in sonuclar) / n
        yendi = sum(1 for r in sonuclar if r["strateji"] > r["al_tut"])

        print(f"{etiket:<26}{ort_get:>8.1f}%{ort_shp:>8.2f}{ort_dd:>8.1f}%"
              f"{ort_kaz:>7.0f}%{ort_islem:>7.1f}{yendi:>6}/{n}")

        # "En iyi"yi Sharpe (riske gore getiri) ile sec - tek basina getiriden saglikli
        if en_iyi is None or ort_shp > en_iyi[1]:
            en_iyi = (etiket, ort_shp)

    print("-" * 78)
    print(f"\n  Referans: ortalama AL & TUT getirisi = {ort_al_tut:.1f}%")
    if en_iyi:
        print(f"  En yuksek Sharpe: {en_iyi[0]}  (Sharpe {en_iyi[1]:.2f})")
    print(f"\n  ⚠️  Bu bir kesin sonuc DEGIL. Yavas MA'lar daha az islem yapar ve")
    print(f"     test suresinin bir kismini 'isinmada' gecirir; karsilastirmayi")
    print(f"     bu kisitla yorumla. Survivorship bias da hala gecerli.")


if __name__ == "__main__":
    main()
