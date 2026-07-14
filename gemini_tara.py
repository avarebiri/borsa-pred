"""
GEMINI TOPLU TARAMA (gunluk)
Bir evrendeki (BIST100 / ABD) tum hisseleri Gemini'ye analiz ettirir, sonuclari
'gemini_log.jsonl'e yazar ve gruplu bir rapor basar. GERCEK EMIR YOK.

Neden gunluk? LLM gecmise backtest EDILEMEZ; performansini olcebilmek icin
sinyallerin BUGUNDEN ITIBAREN birikmesi gerekir. Bu script her gun (borsa
kapanisindan sonra) bir kez calistirilmak icindir.

Calistirma:
    python gemini_tara.py            # BIST100 (varsayilan)
    python gemini_tara.py abd        # ABD evreni
    python gemini_tara.py bist 5     # sadece ilk 5 hisse (test/maliyet kontrolu)

Ayni gun ikinci kez calistirilirsa, o gun ZATEN analiz edilmis hisseler atlanir
(bosuna Gemini cagrisi = bosuna kredi harcamamak icin).
"""
import sys
import json
import time
import datetime

import config
import backtest
import strateji
import gemini_analist as ga

# Ucretsiz tier RPM'ini asmamak icin cagrilar arasi bekleme (saniye)
CAGRI_ARASI = 60.0 / max(config.GEMINI_RPM, 1)


def bugun_loglananlar() -> set:
    """Bugun zaten loglanmis (kod) kumesini dondurur - tekrar cagriyi onler."""
    bugun = datetime.date.today().isoformat()
    loglanan = set()
    try:
        with open(ga.LOG_DOSYASI, encoding="utf-8") as f:
            for satir in f:
                try:
                    k = json.loads(satir)
                    if k.get("zaman", "").startswith(bugun):
                        loglanan.add(k.get("kod"))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return loglanan


def main():
    # Argumanlar: [evren] [limit] [yeni]
    #   yeni -> ayni-gun dedup'i atla (zengin veriyle bugunu yeniden tara)
    evren_adi = "bist"
    limit = None
    zorla = False
    for a in sys.argv[1:]:
        al = a.lower()
        if al in config.EVRENLER:
            evren_adi = al
        elif al == "yeni":
            zorla = True
        elif a.isdigit():
            limit = int(a)

    evren = config.EVRENLER[evren_adi]
    if limit:
        evren = evren[:limit]

    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"Gemini toplu tarama - {evren_adi.upper()} ({len(evren)} hisse) "
          f"[{config.GEMINI_MODEL}]  {zaman}\n")

    try:
        client = ga.istemci()
    except Exception as e:
        print(f"Gemini istemcisi olusturulamadi: {e}")
        print("Vertex icin: gcloud auth application-default login")
        return

    onceden = set() if zorla else bugun_loglananlar()
    gruplar = {"AL": [], "SAT": [], "BEKLE": []}
    atlanan = 0

    for kod in evren:
        isim = kod.replace(".IS", "")
        if isim in onceden:
            atlanan += 1
            continue
        try:
            df = backtest.veri_indir(kod, period="1y")
            if df is None:
                print(f"  {isim:<8} veri yok, atlandi")
                continue
            oz = ga.ozellikler(df)
            s = ga.analiz_et(client, kod, df)
            ga.logla(kod, oz, s)
            gruplar[s.sinyal].append((isim, s))
            print(f"  {isim:<8} {s.sinyal:<5} (guven {s.guven}, skor {s.skor:+.2f})")
            time.sleep(CAGRI_ARASI)  # RPM sinirina saygi (ucretsiz tier)
        except Exception as e:
            print(f"  {isim:<8} HATA -> {e}")

    # --- Ozet rapor (konsol) ---
    print("\n" + "=" * 48)
    for ad in ("AL", "SAT", "BEKLE"):
        liste = sorted(gruplar[ad], key=lambda x: -abs(x[1].skor))
        print(f"{ad}: {len(liste)} hisse")
        for isim, s in liste:
            print(f"   {isim:<8} guven {s.guven:<3} skor {s.skor:+.2f}")
    if atlanan:
        print(f"\n({atlanan} hisse bugun zaten taranmisti, atlandi.)")
    print(f"\nTumu '{ga.LOG_DOSYASI}' dosyasina loglandi (ileriye donuk olcum icin).")

    # --- Telegram raporu ---
    telegram_rapor(evren_adi, zaman, gruplar)


def telegram_rapor(evren_adi: str, zaman: str, gruplar: dict) -> None:
    """AL/SAT sinyallerini Telegram'a gonderir (ayarli degilse ekrana yazar)."""
    al = sorted(gruplar["AL"], key=lambda x: -x[1].skor)
    sat = sorted(gruplar["SAT"], key=lambda x: x[1].skor)
    if not al and not sat:
        return  # bildirilecek sinyal yok

    def kisa(metin, n=140):
        metin = (metin or "").strip()
        return metin if len(metin) <= n else metin[:n - 1] + "…"

    satir = [f"<b>🤖 Gemini Analist — {evren_adi.upper()}</b>", f"<i>{zaman}</i>", ""]
    for baslik, isaret, liste in (("AL", "🟢", al), ("SAT", "🔴", sat)):
        if not liste:
            continue
        satir.append(f"{isaret} <b>{baslik}</b> ({len(liste)})")
        for isim, s in liste[:10]:  # mesaj cok uzamasin diye ilk 10
            satir.append(f"  • <b>{isim}</b> (skor {s.skor:+.2f}, guven {s.guven}) — {kisa(s.gerekce)}")
        if len(liste) > 10:
            satir.append(f"  … +{len(liste) - 10} daha")
        satir.append("")
    satir.append("<i>⚠️ Yatirim tavsiyesi degildir. Gemini teknik analiz; egitim/gozlem amacli.</i>")

    if strateji.telegram_gonder("\n".join(satir)):
        print("✅ Telegram raporu gonderildi.")


if __name__ == "__main__":
    main()
