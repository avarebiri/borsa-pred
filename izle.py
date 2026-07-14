"""
CANLI IZLEME
BIST 30 hisselerini cekip, son gunde ALIS/SATIS sinyali olan varsa
Telegram'a bildirim gonderir. GERCEK EMIR GONDERMEZ - sadece haber verir.

Calistirma:
    python izle.py

Her gun borsa kapanisindan sonra (ornegin 18:30) bir kez calistirilmasi
yeterli. Otomatiklestirmeyi sonra ekleriz (cron / GitHub Actions).

Tekrar-gonderim korumasi: Hangi hisse icin hangi BAR tarihinde sinyal
gonderdigimizi 'gonderilen_sinyaller.json' dosyasinda tutariz. Boylece
ayni gun script'i iki kez calistirsan ya da hafta sonu yeni veri gelmemisken
calistirsan ayni sinyal TEKRAR bildirilmez.
"""
import datetime
import json
import os
import yfinance as yf
import config
import strateji

# Gonderilen sinyallerin kaydi (hisse -> {"tarih": ..., "sinyal": ...})
DURUM_DOSYASI = os.path.join(os.path.dirname(__file__), "gonderilen_sinyaller.json")


def durum_yukle() -> dict:
    """Daha once gonderilen sinyallerin kaydini okur."""
    if os.path.exists(DURUM_DOSYASI):
        try:
            with open(DURUM_DOSYASI, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def durum_kaydet(durum: dict) -> None:
    """Gonderilen sinyal kaydini diske yazar."""
    try:
        with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(durum, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Durum kaydedilemedi: {e}")


def main():
    bugun = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"BIST 30 taraniyor... ({bugun})\n")

    durum = durum_yukle()
    alis_listesi = []
    satis_listesi = []
    hatalar = []

    for kod in config.BIST30:
        try:
            df = yf.download(
                kod,
                period=config.VERI_PERIYODU,
                interval=config.VERI_ARALIGI,
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < config.UZUN_MA:
                hatalar.append(kod)
                continue

            # yfinance bazen cok seviyeli sutun dondurur, duzlestir
            if df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)

            df = strateji.sinyalleri_hesapla(df)
            sinyal = strateji.son_sinyal(df)

            fiyat = float(df["Close"].iloc[-1])
            isim = kod.replace(".IS", "")
            # Sinyalin ait oldugu BAR'in tarihi (calistirma tarihi degil!)
            bar_tarihi = str(df.index[-1].date())

            if sinyal in ("ALIS", "SATIS"):
                onceki = durum.get(isim)
                zaten_gonderildi = (
                    onceki is not None
                    and onceki.get("tarih") == bar_tarihi
                    and onceki.get("sinyal") == sinyal
                )
                isaret = "🟢 ALIS " if sinyal == "ALIS" else "🔴 SATIS"
                if zaten_gonderildi:
                    print(f"  {isaret}: {isim}  ({fiyat:.2f} TL)  [zaten bildirildi]")
                else:
                    if sinyal == "ALIS":
                        alis_listesi.append((isim, fiyat))
                    else:
                        satis_listesi.append((isim, fiyat))
                    durum[isim] = {"tarih": bar_tarihi, "sinyal": sinyal}
                    print(f"  {isaret}: {isim}  ({fiyat:.2f} TL)")
            else:
                print(f"  ⚪ ---   : {isim}")

        except Exception as e:
            hatalar.append(kod)
            print(f"  ! Hata: {kod} ({e})")

    # ---- Telegram mesajini olustur ----
    if not alis_listesi and not satis_listesi:
        print("\nYeni sinyal yok. Telegram'a mesaj gonderilmiyor.")
        durum_kaydet(durum)  # [zaten bildirildi] kayitlari sabit kalir
        return

    satirlar = [f"<b>📊 BIST 30 Sinyal Raporu</b>", f"<i>{bugun}</i>", ""]

    if alis_listesi:
        satirlar.append("🟢 <b>ALIS Sinyalleri</b>")
        for isim, fiyat in alis_listesi:
            satirlar.append(f"  • {isim}: {fiyat:.2f} TL")
        satirlar.append("")

    if satis_listesi:
        satirlar.append("🔴 <b>SATIS Sinyalleri</b>")
        for isim, fiyat in satis_listesi:
            satirlar.append(f"  • {isim}: {fiyat:.2f} TL")
        satirlar.append("")

    satirlar.append("<i>⚠️ Bu yatirim tavsiyesi degildir. Sadece teknik sinyal bildirimidir.</i>")

    mesaj = "\n".join(satirlar)
    basarili = strateji.telegram_gonder(mesaj)
    if basarili:
        print("\n✅ Telegram bildirimi gonderildi.")

    # Yeni sinyaller diske yazilir -> bir daha tekrar gonderilmez.
    durum_kaydet(durum)


if __name__ == "__main__":
    main()
