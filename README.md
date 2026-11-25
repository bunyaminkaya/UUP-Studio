# UUP Studio

Windows Update sunucularındaki build'leri bulur, indirir, doğrular ve ISO'ya dönüştürür.
Arayüz Türkçe / English; açık, koyu ve sistem teması.

Geliştirici: Bünyamin KAYA — https://bunyaminkaya.com

## Çalıştırma
    pip install -r requirements.txt
    python main.py

## Dönüştürme aşamaları
Dosya listesi → İndirme → Doğrulama → Hazırlık → install.wim → Güncelleme → Kayıt + WinRE → Boot + ISO → Tamamlama.
Her aşamanın başlangıç saati günlüğe yazılır; iş bitince "Aşama süreleri" özeti eklenir.

## Hızlandırma
- Dönüştürme sırasında klasörler ve DISM işlemleri Defender taramasından geçici dışlanır (Gelişmiş'ten kapatılabilir; iş bitince kaldırılır).
- Tam sürümler ("Windows 11, version 25H2") güncelleme paketlerinden ("Preview Update…") çok daha hızlıdır.
- Çalışma klasörü hızlı bir SSD üzerinde olmalıdır.

## Notlar
- ISO dönüştürme yalnızca Windows'ta çalışır (resmî uup-converter-wimlib), yönetici olarak çalıştırmanız önerilir.
- Build listesi UUP dump API'sinden gelir. Dönüştürücü ilk kullanımda indirilir.
- Testler: `python -m unittest discover tests` ve `python tools/check_i18n.py`
- EXE, zip ve (Inno Setup varsa) kurulum paketi için: `build.bat` → `dist\`
- Kod imzalama: `SIGN_PFX` ve `SIGN_PASS` ortam değişkenlerini tanımlayın (signtool gerekir).
- Günlükler: `%LOCALAPPDATA%\UUPStudio\logs` (son 20 iş). Sorun bildirirken Günlük kartındaki "Kaydet" ile dosyayı gönderin.
- Yayın öncesi: `TESTING.md` listesi; üçüncü taraf atıflar: `THIRD_PARTY.md`; sürüm geçmişi: `CHANGELOG.md`
