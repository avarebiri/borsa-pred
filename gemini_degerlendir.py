"""
GEMINI ANALIST - ILERIYE DONUK DEGERLENDIRME
'gemini_log.jsonl'deki gunluk Gemini skorlarini alir, her tarama gununde en
yuksek skorlu N hisseyi (kagit-trade) tutar ve getirisini esit-agirlik "al & tut"
baseline'ina karsi olcer. GERCEK EMIR YOK.

Neden boyle? LLM gecmise backtest EDILEMEZ (model gecmisi bilir -> lookahead).
Bu yuzden performans, sinyallerin loglandigi gunden ILERIYE dogru, gercek
gelecekteki fiyatlarla olculur. Log biriktikce sonuc anlamlanir.

Calistirma:
    python gemini_degerlendir.py           # ilk 10 skoru tut
    python gemini_degerlendir.py 5          # ilk 5 skoru tut

UYARI: Az sayida tarama gunu varken sonuc GURULTUDUR. En az birkac hafta -
tercihen birkac ay - veri birikmeden ciddiye alma. Bu arac 'sistem calisiyor
mu' icindir; 'strateji iyi mi' sorusu zaman ister.
"""
import sys
import json
import datetime

import pandas as pd

import backtest      # veri_indir, sharpe_orani, maksimum_dusus, ISLEM_MALIYETI
import gemini_analist as ga


def log_oku() -> pd.DataFrame:
    """gemini_log.jsonl'i tarih x hisse skor tablosuna cevirir."""
    kayitlar = []
    try:
        with open(ga.LOG_DOSYASI, encoding="utf-8") as f:
            for satir in f:
                try:
                    k = json.loads(satir)
                    kayitlar.append(k)
                except Exception:
                    continue
    except FileNotFoundError:
        return pd.DataFrame()
    if not kayitlar:
        return pd.DataFrame()
    df = pd.DataFrame(kayitlar)
    df["tarih"] = pd.to_datetime(df["zaman"]).dt.date
    # Ayni gun bir hisse birden cok loglandiysa (orn. 'yeni' ile yeniden tarama)
    # EN SON kaydi kullan - append sirasi son = en guncel/zengin.
    df = df.drop_duplicates(subset=["kod", "tarih"], keep="last")
    return df


def secimler(log_df: pd.DataFrame, top_n: int):
    """Her tarama gunu icin en yuksek skorlu top_n hisseyi (AL/pozitif) secer.
    Donus: {tarih: [hisse,...]} ve tum secilen hisse kumesi."""
    secim = {}
    tum = set()
    for tarih, grup in log_df.groupby("tarih"):
        # Sadece pozitif skorlular arasindan en iyileri al (SAT/BEKLE'yi tutma)
        aday = grup[grup["skor"] > 0].sort_values("skor", ascending=False)
        secilen = list(aday["kod"].head(top_n))
        if secilen:
            secim[tarih] = secilen
            tum.update(secilen)
    return secim, tum


def fiyat_getir(hisseler, ilk_tarih):
    """Secilen hisselerin gunluk kapanislarini indirir (ilk taramadan bugune)."""
    seriler = {}
    for isim in hisseler:
        for kod in (f"{isim}.IS", isim):  # once BIST (.IS), sonra ABD (uzantisiz)
            try:
                df = backtest.veri_indir(kod, period="1y")
                if df is not None:
                    seriler[isim] = df["Close"]
                    break
            except Exception:
                continue
    if not seriler:
        return None
    panel = pd.DataFrame(seriler).sort_index()
    panel.index = panel.index.date
    return panel[panel.index >= ilk_tarih]


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 10

    log_df = log_oku()
    if log_df.empty:
        print("gemini_log.jsonl bos. Once 'python gemini_tara.py' calistir.")
        return

    tarama_gunleri = sorted(log_df["tarih"].unique())
    print(f"Gemini degerlendirme  (top {top_n})")
    print(f"Tarama gunu sayisi: {len(tarama_gunleri)}  "
          f"({tarama_gunleri[0]} -> {tarama_gunleri[-1]})")

    if len(tarama_gunleri) < 2:
        print("\n⚠️  Henuz tek gun verisi var - getiri olculemez. Sistem calisiyor;")
        print("   birkac tarama gunu birikince tekrar calistir. Bugunku secim:")
        secim, _ = secimler(log_df, top_n)
        for t, hisseler in secim.items():
            print(f"   {t}: {', '.join(hisseler)}")
        return

    secim, tum_hisseler = secimler(log_df, top_n)
    ilk = tarama_gunleri[0]
    panel = fiyat_getir(tum_hisseler, ilk)
    if panel is None or panel.empty:
        print("Fiyat verisi alinamadi.")
        return

    gunluk = panel.pct_change(fill_method=None)

    # Her gun icin agirlik: o gune ait EN SON tarama secimini kullan (ffill mantigi)
    agirlik = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    secim_gunleri = sorted(secim.keys())
    for i, gun in enumerate(panel.index):
        gecerli = [sg for sg in secim_gunleri if sg <= gun]
        if not gecerli:
            continue
        hisseler = [h for h in secim[gecerli[-1]] if h in agirlik.columns]
        if hisseler:
            agirlik.loc[gun, hisseler] = 1.0 / len(hisseler)

    # Strateji getirisi (dunku agirlik * bugunku getiri) + islem maliyeti
    strat = (agirlik.shift(1) * gunluk.fillna(0)).sum(axis=1)
    turnover = (agirlik - agirlik.shift(1)).abs().sum(axis=1).fillna(0)
    strat -= turnover * backtest.ISLEM_MALIYETI
    # Baseline: taranan tum evrenin esit-agirlik getirisi
    baseline = gunluk.mean(axis=1)

    def ozet(g):
        return ((1 + g).prod() - 1) * 100, backtest.sharpe_orani(g), backtest.maksimum_dusus(g)

    sg, ss, sd = ozet(strat)
    bg, bs, bd = ozet(baseline)

    print(f"\n{'':<22}{'Getiri':>9}{'Sharpe':>8}{'MaxDD':>9}")
    print("-" * 48)
    print(f"{'Gemini top-'+str(top_n):<22}{sg:>8.1f}%{ss:>8.2f}{sd:>8.1f}%")
    print(f"{'Al & Tut (esit)':<22}{bg:>8.1f}%{bs:>8.2f}{bd:>8.1f}%")
    print("-" * 48)
    gun = len(panel.index)
    print(f"\n  {gun} islem gunu uzerinden. Bu HENUZ az; birkac ay birikmeden")
    print(f"  sonucu ciddiye alma. Amac once borunun calistigini gormek.")


if __name__ == "__main__":
    main()
