"""
MOMENTUM (ROLATIF GUC) BACKTEST
Cross-sectional momentum: her ay sonunda hisseleri gecmis getirisine gore
sirala, en GUCLU N hisseyi esit agirlikla tut, ay boyunca tut, tekrar dengele.

Neden? Trend takibi (MA kesisimi) bogada al&tut'u yenemedi cunku nakte geciyor.
Momentum nakte gecmez; hep en guclu hisselerde kalir. Bogada al&tut'u GERCEKTEN
yenme sansi olan yaklasim budur. Burada bunu VERIYLE sinariz.

Calistirma:
    python momentum.py

UYARI: Momentumun riski sert donuslerdir (momentum crash). Ayrica bu test de
survivorship bias tasir (bugunun BIST30'u). Sonucu mucize degil, bir hipotez
testi olarak oku.
"""
import sys
import pandas as pd
import config
import backtest  # veri_indir, sharpe_orani, maksimum_dusus, ISLEM_MALIYETI


def fiyat_paneli(evren=None, period=None):
    """Verilen evrendeki hisselerin Close serisini tek DataFrame'de toplar."""
    if evren is None:
        evren = config.BIST100
    seriler = {}
    for kod in evren:
        try:
            df = backtest.veri_indir(kod, period=period)
            if df is not None:
                seriler[kod.replace(".IS", "")] = df["Close"]
        except Exception:
            pass
    if not seriler:
        return None
    return pd.DataFrame(seriler).sort_index()


def momentum_backtest(panel, lookback=120, skip=20, top_n=5, mutlak_filtre=False):
    """
    panel        : gunluk Close paneli (sutun=hisse)
    lookback     : momentum bakis penceresi (isgunu) ~120 = 6 ay
    skip         : son 'skip' gunu atla (kisa vadeli geri donus etkisini ele) ~20 = 1 ay
    top_n        : kac hisse tutulacak
    mutlak_filtre: True -> momentumu negatif olan hisse alinmaz (gerekirse nakit kalir)
    Donus: (strateji_gunluk_getiri, ilk_rebalans_tarihi) ya da (None, None)
    """
    daily_ret = panel.pct_change(fill_method=None)
    # t anindaki momentum: (skip gun once) / (lookback gun once) - 1  -> sadece GECMIS veri
    mom = panel.shift(skip) / panel.shift(lookback) - 1

    # Aylik yeniden dengeleme tarihleri (her ayin son islem gunu)
    donemler = panel.index.to_period("M")
    rebal_tarihleri = [grp.index[-1] for _, grp in panel.groupby(donemler)]
    rebal_tarihleri = [d for d in rebal_tarihleri if mom.loc[d].notna().any()]
    if not rebal_tarihleri:
        return None, None

    # Agirlik matrisi: rebalans gunlerinde sec, aralarda ayni kalsin (ffill)
    agirlik = pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    for d in rebal_tarihleri:
        m = mom.loc[d].dropna()
        if mutlak_filtre:
            m = m[m > 0]
        secilen = m.nlargest(top_n).index
        agirlik.loc[d] = 0.0
        if len(secilen) > 0:
            agirlik.loc[d, secilen] = 1.0 / len(secilen)
    agirlik = agirlik.ffill().fillna(0.0)

    # Strateji getirisi: dunku agirlik * bugunku getiri (lookahead yok)
    strat = (agirlik.shift(1) * daily_ret.fillna(0)).sum(axis=1)
    # Islem maliyeti: agirlik degisimi (turnover) kadar
    turnover = (agirlik - agirlik.shift(1)).abs().sum(axis=1).fillna(0)
    strat -= turnover * backtest.ISLEM_MALIYETI

    ilk = rebal_tarihleri[0]
    return strat.loc[ilk:], ilk


def ozet(getiri: pd.Series) -> dict:
    return {
        "getiri": ((1 + getiri).prod() - 1) * 100,
        "sharpe": backtest.sharpe_orani(getiri),
        "max_dd": backtest.maksimum_dusus(getiri),
    }


def main():
    # Evren secimi: "python momentum.py abd"  (varsayilan bist)
    evren_adi = sys.argv[1].lower() if len(sys.argv) > 1 else "bist"
    evren = config.EVRENLER.get(evren_adi)
    if evren is None:
        print(f"Bilinmeyen evren: {evren_adi}. Secenekler: {list(config.EVRENLER)}")
        return
    print(f"Momentum backtest... ({config.BACKTEST_PERIYODU}, {evren_adi.upper()} evreni, {len(evren)} aday)")
    print("Veriler indiriliyor...\n")
    panel = fiyat_paneli(evren)
    if panel is None:
        print("Veri alinamadi.")
        return
    print(f"{panel.shape[1]} hisse verisi hazir, {panel.shape[0]} gun.\n")

    # Denenecek varyantlar: (lookback, skip, top_n, mutlak_filtre, etiket)
    # Evren genis (100) oldugu icin daha buyuk top_n'ler de mantikli.
    varyantlar = [
        (120, 20, 10, False, "Top10 6ay momentum"),
        (120, 20, 15, False, "Top15 6ay momentum"),
        (120, 20, 20, False, "Top20 6ay momentum"),
        (60,  20, 10, False, "Top10 3ay momentum"),
        (120, 20, 10, True,  "Top10 6ay + mutlak filtre"),
    ]

    print(f"{'Strateji':<30}{'Getiri':>9}{'Sharpe':>8}{'MaxDD':>9}")
    print("-" * 56)

    ilk_tarih = None
    for lb, sk, n, mf, etiket in varyantlar:
        getiri, ilk = momentum_backtest(panel, lb, sk, n, mf)
        if getiri is None:
            continue
        ilk_tarih = ilk
        m = ozet(getiri)
        print(f"{etiket:<30}{m['getiri']:>8.1f}%{m['sharpe']:>8.2f}{m['max_dd']:>8.1f}%")

    # Esit agirlikli AL & TUT referansi (ayni donemde, adil karsilastirma)
    if ilk_tarih is not None:
        bh = panel.pct_change(fill_method=None).mean(axis=1).loc[ilk_tarih:]  # esit agirlik endeks
        m = ozet(bh)
        print("-" * 56)
        print(f"{'AL & TUT (esit agirlik)':<30}{m['getiri']:>8.1f}%"
              f"{m['sharpe']:>8.2f}{m['max_dd']:>8.1f}%")

    print(f"\n  Not: Karsilastirma ilk rebalans tarihinden ({ilk_tarih.date() if ilk_tarih is not None else '?'}) "
          f"itibaren, ayni donemde yapildi.")
    print(f"  Sharpe ve MaxDD'ye dikkat: yuksek getiri tek basina yetmez.")


if __name__ == "__main__":
    main()
