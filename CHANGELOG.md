# Değişiklik notları

## 0.3.0 (beta)
- Dönüştürme 5 alt aşamaya bölündü (Hazırlık, install.wim, Güncelleme, Kayıt + WinRE, Boot + ISO); toplam 9 adım.
- Her aşamanın başlangıç saati günlüğe yazılır, iş bitince "Aşama süreleri" özeti eklenir.
- Her iş için günlük dosyası otomatik kaydedilir (son 20); Günlük kartında "Kaydet" düğmesi, Hakkında'da "Günlük klasörünü aç".
- İlk açılışta kaynak, lisans ve Defender dışlaması hakkında bilgilendirme.
- Hakkında: üçüncü taraf atıfları, Microsoft ile bağlantı yok ve lisans/etkinleştirme uyarısı.
- Defender dışlaması artık DISM/TiWorker/oscdimg işlemlerini de kapsar; yalnızca uygulamanın eklediği dışlamalar kaldırılır.
- Boşta bekleme uyarısı CPU + disk G/Ç + Defender ölçümüne dayanır; yanlış alarmlar giderildi.
- Derleme: sürüm bilgili EXE, isteğe bağlı kod imzalama, sürüm numaralı zip ve Inno Setup kurulum betiği.

## 0.2.0
- Tek sürüm varsayılanı, güncelleme-only build'lerin filtrelenmesi, yavaş build uyarısı.
- Eski bağlama (C:\MountUUP) kalıntı temizliği, DISM hata tespiti.
- Build listesi önbelleği, 429/ağ hatalarında yeniden deneme.

## 0.1.0
- İlk taslak: build bul, indir, doğrula, ISO'ya dönüştür.
