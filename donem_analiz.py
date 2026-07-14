"""
DONEM ANALIZI (momentum saglamlik testi)
Onceki momentum testlerinin HEPSI son ~2.5 yili (bogayi) olcuyordu. Burada
daha uzun gecmiste (varsayilan 8 yil) momentumu YIL YIL ve drawdown bazinda
inceleriz. Amac: momentum sadece bu bogada mi calisti, yoksa stresli/yatay
donemlerde de ayakta mi kaliyor?

Ayrica "mutlak filtre"nin (momentum negatifse nakit kal) degeri ancak dususte
ortaya cikar - onu da yil yil karsilastiririz.

Calistirma:
    python donem_analiz.py

UYARILAR:
- Genis evren (BIST100) bugunun listesidir; geriye gidildikce survivorship
  bias ARTAR ve o yil borsada olmayan/yeni halka arzlar otomatik dislanir.
  Yani eski yillarda evren daralir - sonuclari bu kisitla oku.
- TL nominal getiriler enflasyon nedeniyle cogu takvim yilinda POZITIFTIR;
  stres takvim getirisinde degil DRAWDOWN'da gorunur. Bu yuzden hem getiri
  hem max dususe bakiyoruz.
"""
import sys
import pandas as pd
import config
import backtest
import momentum

# Daha uzun gecmis (2018 lira krizi, 2020 Covid, 2022 satisi gibi donemler dahil)
UZUN_PERIYOT = "8y"
# Sabit bir strateji secimi (BIST100 testinde en dengeli cikan): Top15, 6ay momentum
LOOKBACK, SKIP, TOP_N = 120, 20, 15


def yillik_metrik(getiri: pd.Series) -> dict:
    """Bir getiri serisi icin toplam getiri ve o donemin max dususu."""
    return {
        "getiri": ((1 + getiri).prod() - 1) * 100,
        "max_dd": backtest.maksimum_dusus(getiri),
    }


def main():
    # Evren secimi: "python donem_analiz.py abd"  (varsayilan bist)
    evren_adi = sys.argv[1].lower() if len(sys.argv) > 1 else "bist"
    evren = config.EVRENLER.get(evren_adi)
    if evren is None:
        print(f"Bilinmeyen evren: {evren_adi}. Secenekler: {list(config.EVRENLER)}")
        return
    print(f"Donem analizi... ({evren_adi.upper()}, {UZUN_PERIYOT}, "
          f"Top{TOP_N} {LOOKBACK//20}ay momentum)")
    print("Veriler indiriliyor (uzun gecmis, biraz surebilir)...\n")
    panel = momentum.fiyat_paneli(evren, period=UZUN_PERIYOT)
    if panel is None:
        print("Veri alinamadi.")
        return
    print(f"{panel.shape[1]} hisse, {panel.shape[0]} gun "
          f"({panel.index[0].date()} -> {panel.index[-1].date()}).\n")

    # Iki strateji: filtresiz ve mutlak filtreli (dususte nakit)
    strat, ilk = momentum.momentum_backtest(panel, LOOKBACK, SKIP, TOP_N, False)
    strat_f, _ = momentum.momentum_backtest(panel, LOOKBACK, SKIP, TOP_N, True)
    bh = panel.pct_change(fill_method=None).mean(axis=1).loc[ilk:]  # esit agirlik al&tut

    # Her takvim yili icin getiri + drawdown
    print(f"{'Yil':<6}{'Strateji':>10}{'(DD)':>9}{'Filtreli':>11}{'(DD)':>9}"
          f"{'Al&Tut':>10}{'(DD)':>9}{'Aktif':>7}")
    print("-" * 71)

    for yil in sorted(set(strat.index.year)):
        s_y = strat[strat.index.year == yil]
        f_y = strat_f[strat_f.index.year == yil]
        b_y = bh[bh.index.year == yil]
        if len(s_y) < 20:  # cok kisa (ilk kismi) yili atla
            continue
        ms, mf, mb = yillik_metrik(s_y), yillik_metrik(f_y), yillik_metrik(b_y)
        # O yil verisi olan ortalama hisse sayisi (evren genisligi)
        aktif = int(panel.loc[panel.index.year == yil].notna().any().sum())
        print(f"{yil:<6}{ms['getiri']:>9.1f}%{ms['max_dd']:>8.1f}%"
              f"{mf['getiri']:>10.1f}%{mf['max_dd']:>8.1f}%"
              f"{mb['getiri']:>9.1f}%{mb['max_dd']:>8.1f}%{aktif:>7}")

    # Tum donem ozeti
    print("-" * 71)
    ms, mf, mb = yillik_metrik(strat), yillik_metrik(strat_f), yillik_metrik(bh)
    print(f"{'TUM':<6}{ms['getiri']:>9.1f}%{ms['max_dd']:>8.1f}%"
          f"{mf['getiri']:>10.1f}%{mf['max_dd']:>8.1f}%"
          f"{mb['getiri']:>9.1f}%{mb['max_dd']:>8.1f}%")
    print(f"\n  Sharpe (tum donem):  Strateji {backtest.sharpe_orani(strat):.2f} | "
          f"Filtreli {backtest.sharpe_orani(strat_f):.2f} | "
          f"Al&Tut {backtest.sharpe_orani(bh):.2f}")
    print(f"\n  Oku: Strateji getiriyi yiliyor mu HER yil, yoksa birkac iyi yila mi")
    print(f"  bagli? 'Filtreli' kotu yillarda dususu (DD) azaltiyor mu? 'Aktif' o")
    print(f"  yil veri olan hisse sayisi - dustukce eski yil sonuclari az guvenilir.")


if __name__ == "__main__":
    main()
