"""
DERIN OGRENME MODELI (cross-sectional forward-return tahmini)
Her ay sonunda, her hisse icin GECMIS ozelliklerden (momentum, volatilite, MA
oranlari, 52h uzaklik...) GELECEK 1 aylik GORELI getiriyi tahmin eden kucuk bir
MLP (PyTorch). Tahmin skoruna gore top-N tutulur ve momentum + esit-agirlik
al&tut ile AYNI cetvelde (kagit-trade) karsilastirilir.

DURUSTLUK ILKELERI:
- WALK-FORWARD: her test ayinda yalnizca o aydan ONCE hedefi gerceklesmis
  verilerle egitilir (lookahead yok, embargo uygulanir).
- Cross-sectional z-score: ozellikler ve hedef her tarihte hisseler arasi
  normalize edilir -> model MUTLAK degil GORELI gucu ogrenir, rejimden bagimsiz.
- Kucuk ag + dropout: overfit'i sinirlamak icin (DL burada COK kolay overfit eder).

UYARI: DL, piyasada verdigimiz emegi otomatik alfaya cevirmez. Bu, momentum ve
LLM ile karsilastirmak icin DURUST bir taban cizgisidir; sonuc buyuk olasilikla
esit-agirlik al&tut'u net yenmez (onceki bulgularimizla tutarli olur).

Calistirma:
    python dl_model.py            # BIST100, 8y
    python dl_model.py abd        # ABD evreni
"""
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

import config
import backtest       # sharpe_orani, maksimum_dusus, ISLEM_MALIYETI
import momentum       # fiyat_paneli

TOHUM = 42
PERIYOT = "8y"
HORIZON = 21          # tahmin ufku (isgunu ~1 ay)
TOP_N = 15
MIN_EGITIM_AY = 24    # tahmine baslamadan once en az bu kadar ay egitim verisi
torch.manual_seed(TOHUM)
np.random.seed(TOHUM)
CIHAZ = "cuda" if torch.cuda.is_available() else "cpu"


# --- Ozellikler (hepsi GECMIS fiyattan; cross-sectional z-score sonra) ------
def ozellik_panelleri(panel: pd.DataFrame) -> dict:
    ret = panel.pct_change(fill_method=None)
    ma50 = panel.rolling(50).mean()
    ma200 = panel.rolling(200).mean()
    return {
        "mom_1a":   panel / panel.shift(21) - 1,
        "mom_3a":   panel / panel.shift(63) - 1,
        "mom_6a":   panel / panel.shift(126) - 1,
        "mom_12a":  panel / panel.shift(252) - 1,
        "mom_12_1": panel.shift(21) / panel.shift(252) - 1,
        "vol_3a":   ret.rolling(63).std(),
        "vol_6a":   ret.rolling(126).std(),
        "ma50_or":  panel / ma50 - 1,
        "ma200_or": panel / ma200 - 1,
        "ma_kesim": ma50 / ma200 - 1,
        "yuksek52": panel / panel.rolling(252).max() - 1,
        "dusuk52":  panel / panel.rolling(252).min() - 1,
    }


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0.0


def veri_hazirla(panel: pd.DataFrame):
    """Her rebalans tarihi icin (X: hisse x ozellik z-score, y: gelecek getiri
    z-score) uretir. Donus: ozellik adlari + tarih basina (X_df, y_series)."""
    ozp = ozellik_panelleri(panel)
    ozellikler = list(ozp)
    donemler = panel.index.to_period("M")
    rebal = [grp.index[-1] for _, grp in panel.groupby(donemler)]

    veri = []  # (tarih, X_df, y_series)
    for i in range(len(rebal) - 1):  # son ayin hedefi yok
        t, t_next = rebal[i], rebal[i + 1]
        # Ozellikler t aninda
        X = pd.DataFrame({ad: ozp[ad].loc[t] for ad in ozellikler})
        X = X.dropna()
        if len(X) < 10:
            continue
        # Hedef: t -> t_next goreli getiri
        fwd = (panel.loc[t_next] / panel.loc[t] - 1).reindex(X.index)
        gecerli = fwd.dropna().index
        X = X.loc[gecerli]
        y = fwd.loc[gecerli]
        # Cross-sectional z-score
        X = X.apply(_zscore, axis=0)
        y = _zscore(y)
        veri.append((t, X, y))
    return ozellikler, veri, rebal


# --- Model -----------------------------------------------------------------
class MLP(nn.Module):
    def __init__(self, giris):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(giris, 32), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(32, 16), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def egit(X: np.ndarray, y: np.ndarray, giris: int, epok=80):
    model = MLP(giris).to(CIHAZ)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    kayip = nn.MSELoss()
    Xt = torch.tensor(X, dtype=torch.float32, device=CIHAZ)
    yt = torch.tensor(y, dtype=torch.float32, device=CIHAZ)
    model.train()
    for _ in range(epok):
        opt.zero_grad()
        cikti = model(Xt)
        kayip(cikti, yt).backward()
        opt.step()
    model.eval()
    return model


def walk_forward_dl(ozellikler, veri):
    """Her test ayinda, hedefi gerceklesmis gecmis verilerle egitip o ayin
    hisselerini skorlar. Donus: {tarih: pd.Series(skor)}."""
    skorlar = {}
    for i in range(len(veri)):
        t = veri[i][0]
        # Egitim: hedefi t'den ONCE gerceklesmis aylar (embargo: j <= i-2,
        # cunku j'nin hedefi j+1 ayinda gerceklesir; j+1 <= i-1 < t garanti)
        egitim = veri[: max(0, i - 1)]
        if len(egitim) < MIN_EGITIM_AY:
            continue
        X_tr = np.vstack([e[1].values for e in egitim])
        y_tr = np.concatenate([e[2].values for e in egitim])
        model = egit(X_tr, y_tr, len(ozellikler))
        with torch.no_grad():
            X_te = torch.tensor(veri[i][1].values, dtype=torch.float32, device=CIHAZ)
            tahmin = model(X_te).cpu().numpy()
        skorlar[t] = pd.Series(tahmin, index=veri[i][1].index)
    return skorlar


# --- Kagit-trade (momentum ile ayni matematik) -----------------------------
def kagit_trade(panel, skor_dict, top_n):
    daily = panel.pct_change(fill_method=None)
    agirlik = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    tarihler = sorted(skor_dict)
    for gun in panel.index:
        gecerli = [t for t in tarihler if t <= gun]
        if not gecerli:
            continue
        skor = skor_dict[gecerli[-1]].dropna()
        secilen = list(skor.sort_values(ascending=False).head(top_n).index)
        secilen = [s for s in secilen if s in agirlik.columns]
        if secilen:
            agirlik.loc[gun, secilen] = 1.0 / len(secilen)
    strat = (agirlik.shift(1) * daily.fillna(0)).sum(axis=1)
    turnover = (agirlik - agirlik.shift(1)).abs().sum(axis=1).fillna(0)
    strat -= turnover * backtest.ISLEM_MALIYETI
    ilk = tarihler[0]
    return strat.loc[ilk:]


def ozet(g):
    return ((1 + g).prod() - 1) * 100, backtest.sharpe_orani(g), backtest.maksimum_dusus(g)


def main():
    evren_adi = sys.argv[1].lower() if len(sys.argv) > 1 and sys.argv[1].lower() in config.EVRENLER else "bist"
    print(f"DL modeli - {evren_adi.upper()} ({PERIYOT}), cihaz={CIHAZ}")
    print("Veriler indiriliyor...")
    panel = momentum.fiyat_paneli(config.EVRENLER[evren_adi], period=PERIYOT)
    if panel is None:
        print("Veri alinamadi.")
        return
    print(f"{panel.shape[1]} hisse, {panel.shape[0]} gun. Ozellik+egitim...")

    ozellikler, veri, rebal = veri_hazirla(panel)
    skor_dl = walk_forward_dl(ozellikler, veri)
    if not skor_dl:
        print("Yeterli egitim verisi yok.")
        return
    ilk_test = min(skor_dl)

    # Karsilastirma: DL vs momentum(6ay) vs esit-agirlik al&tut (AYNI donemde)
    skor_mom = {t: (panel.loc[t] / panel.shift(126).loc[t] - 1) for t in skor_dl}
    strat_dl = kagit_trade(panel, skor_dl, TOP_N)
    strat_mom = kagit_trade(panel, skor_mom, TOP_N)
    baseline = panel.pct_change(fill_method=None).mean(axis=1).loc[ilk_test:]

    print(f"\nTest donemi: {ilk_test} -> {max(skor_dl)}  ({len(skor_dl)} ay)")
    print(f"{'Model':<22}{'Getiri':>9}{'Sharpe':>8}{'MaxDD':>9}")
    print("-" * 48)
    for ad, g in (("DL top-%d" % TOP_N, strat_dl),
                  ("Momentum top-%d" % TOP_N, strat_mom),
                  ("Al & Tut (esit)", baseline)):
        get, shp, dd = ozet(g)
        print(f"{ad:<22}{get:>8.1f}%{shp:>8.2f}{dd:>8.1f}%")
    print("-" * 48)
    print("\n  Not: DL burada momentum ve al&tut ile AYNI kagit-trade motorunda.")
    print("  Walk-forward + cross-sectional -> durust; yine de survivorship ve")
    print("  kisa temiz-veri kisitlari gecerli. Sonucu abartma.")


if __name__ == "__main__":
    main()
