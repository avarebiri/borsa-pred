# Otomasyon — GitHub Actions ile günlük tarama

Sisteme açık bir sunucu gerekmez. Tarama her hafta içi GitHub'ın sunucularında
otomatik çalışır, sonucu Telegram'a gönderir ve `gemini_log.jsonl`'i repoya
işler (böylece veri birikir ve geçmişi de tutulur).

## Bir kerelik kurulum

### 1. Repoyu GitHub'a koy
Terminalde, proje klasöründe:
```bash
git init                      # (zaten yapıldıysa atla)
git add -A
git commit -m "ilk commit"    # (zaten yapıldıysa atla)
```
Sonra GitHub'da **boş** bir repo oluştur (README ekleme) ve bağla:
```bash
git remote add origin https://github.com/<KULLANICI>/<REPO>.git
git branch -M main
git push -u origin main
```

### 2. Gizli anahtarları GitHub'a ekle (koda ASLA yazma)
GitHub repo sayfası → **Settings → Secrets and variables → Actions → New repository secret**.
Şu üç secret'ı ekle:

| Secret adı | Değer |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey adresinden al |
| `TELEGRAM_TOKEN` | BotFather'dan aldığın bot token'ı |
| `TELEGRAM_CHAT_ID` | Senin chat ID'in |

> Bulut için **AI Studio API key** kullanıyoruz — en basiti (tek anahtar, Vertex'in
> service-account/ADC derdi yok). Vertex kredisini kullanmak istersen ayrıca
> service-account anahtarı kurulumu gerekir; söyle, onu da ekleriz.

### 3. Actions'ı etkinleştir
Repo → **Actions** sekmesi → workflow'ları etkinleştir. Hepsi bu.

## Nasıl çalışır
- **Zaman:** Hafta içi 15:45 UTC (~18:45 TR, BIST kapanışından sonra).
  Değiştirmek için `.github/workflows/gunluk_tarama.yml` içindeki `cron` satırı.
- **Elle tetikleme:** Actions sekmesi → "Gunluk Gemini Tarama" → **Run workflow**.
- **Çıktı:** Telegram raporu + repoya commit'lenen güncel `gemini_log.jsonl`.

## Performansı ölçmek
Log biriktikçe (haftalar/aylar), yerelde:
```bash
git pull                      # birikmiş logu çek
python gemini_degerlendir.py  # ileriye dönük kâğıt-trade, al&tut'a karşı
```

## Ücretsiz tier limitleri (önemli)
`gemini-2.5-flash` ücretsiz tier (2026): **250 istek/gün**, **10 istek/dakika**.
- Günlük ~100 BIST hissesi 250/gün sınırına rahat sığar.
- 10/dakika sınırı için tarayıcı çağrılar arası bekler (`config.GEMINI_RPM`, varsayılan
  10 → 6 sn) ve `429` olursa tekrar dener. Tam tarama ~10-15 dk sürer (Actions 45 dk
  limitine sığar).
- 250/gün **proje başına**. BIST tek başına sorunsuz; BIST **+** ABD aynı gün (~206)
  sınıra yaklaşır — ikisini birden istersen ücretli tier'a geç (`GEMINI_RPM`'i de büyüt).
- Ücretli tier'a geçince `.env`/secret'a `GEMINI_RPM=<yeni deger>` ekle, bekleme azalır.

## Notlar
- ABD taraması için cron komutunu `python gemini_tara.py abd` yap (ABD kapanışı
  farklı saat — 21:00 UTC civarı uygun).
- yfinance bazı hisselerde veri vermeyebilir; o hisseler atlanır, sorun değil.
- Ücret: `gemini-2.5-flash` çok ucuz; ücretli tier'da bile günde ~100 hisse kuruşlar.
- Vertex (yerel) faturalandırması dönem dönem kapanabiliyor; **bulut otomasyonu AI
  Studio key kullandığı için bundan etkilenmez** — bu yüzden Actions'ta AI Studio seçtik.
