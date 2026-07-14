# BIST 30 Sinyal Sistemi (Aşama 1)

Basit bir başlangıç: BIST 30 hisselerini izler, hareketli ortalama kesişimi
stratejisiyle ALIŞ/SATIŞ sinyali üretir ve Telegram'a bildirim gönderir.
**Gerçek emir göndermez** — sadece haber verir. Ayrıca geçmiş veride strateji
testi (backtest) yapar.

## Kurulum

1. Python paketlerini yükle:
   ```
   pip install yfinance pandas python-dotenv
   ```

2. Telegram bilgilerini ayarla:
   - `.env.example` dosyasını `.env` olarak kopyala
   - Kendi `TELEGRAM_TOKEN` ve `TELEGRAM_CHAT_ID` değerlerini yaz
   - (Token ve chat ID nasıl alınır, sohbette anlatıldı)

3. `.env` dosyasının okunması için `config.py`'nin başına şunu ekleyebilirsin
   (python-dotenv yüklüyse):
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
   Ya da Telegram bilgilerini terminalden ortam değişkeni olarak verebilirsin.

## Kullanım

**Canlı tarama (günlük sinyal kontrolü):**
```
python izle.py
```
Borsa kapanışından sonra (örn. 18:30) çalıştır. Sinyal varsa Telegram'a düşer.
Telegram ayarlı değilse mesajı ekrana yazar — önce böyle test et.

**Backtest (geçmiş veride strateji testi):**
```
python backtest.py
```
Son 3 yılda strateji kâr eder miydi, "al ve tut"u yener miydi gösterir.

## Dosyalar

- `config.py` — ayarlar: hisse listesi, MA periyotları, Telegram
- `strateji.py` — sinyal hesaplama + Telegram (tek yerde, ortak)
- `izle.py` — canlı tarama + bildirim
- `backtest.py` — geçmiş veri testi

## Önemli notlar

- Strateji bilinçli olarak basit (MA20/MA50 kesişimi). Amaç önce boru hattının
  çalıştığını görmek. Stratejiyi sonra birlikte geliştireceğiz.
- YFinance verisi ~15 dk gecikmeli ve günlük analiz için uygundur.
- Bu sistem yatırım tavsiyesi değildir, eğitim/araştırma amaçlıdır.

## Sıradaki adımlar (sonra)

1. Sinyalleri bir süre canlı izle, isabetlerini gözlemle
2. Backtest sonuçlarına göre stratejiyi iyileştir (RSI, hacim filtresi, stop-loss)
3. Kâğıt üstünde trade (sanal portföy) simülasyonu
4. (En sonunda, istersen) AlgoLab API ile gerçek emir
