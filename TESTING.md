# Yayın öncesi test listesi

Her satırı gerçek bir Windows makinesinde deneyip işaretleyin.

## Dönüştürme
- [ ] Windows 11 tam sürüm (ör. 25H2), tek sürüm (Pro), tr-tr → ISO oluşur, "Aşama süreleri" tablosu görünür
- [ ] Birden fazla sürüm (Home + Pro) → tek ISO, iki sürüm içerir
- [ ] Başka bir dil (en-us) ve arayüz dili English
- [ ] Windows 10 build'i
- [ ] ARM64 build'i (yalnızca ISO oluşumu; ARM cihaz gerekmez)
- [ ] Güncelleme paketi ("Preview Update…") seçince uyarı çıkıyor

## İş kontrolü
- [ ] İndirme sırasında Duraklat → Devam et (dosyalar baştan inmiyor)
- [ ] Dönüştürme sırasında İptal et → çalışma klasörü siliniyor, C:\MountUUP boş
- [ ] İptal sonrası yeni dönüştürme başarıyla çalışıyor
- [ ] İş bitince `AppData\Local\UUPStudio\work` altında klasör kalmıyor

## Ortam
- [ ] Yönetici olmayan hesap: açılışta UAC istiyor, reddedince anlaşılır uyarı
- [ ] Defender kapalı veya başka antivirüs: "dışlama eklenemedi" notu çıkıyor, dönüştürme sürüyor
- [ ] Gelişmiş'ten Defender dışlaması kapatılınca eklenmiyor
- [ ] Python kurulu olmayan temiz Windows'ta EXE açılıyor
- [ ] Açık / koyu / sistem teması; %125, %150, %200 ölçekleme
- [ ] İnternet kesilince / API 429 verince liste ve indirme toparlanıyor

## Yeni özellikler
- [ ] İlk açılışta bilgilendirme bir kez çıkıyor, ikinci açılışta çıkmıyor
- [ ] Günlük → Kaydet bir .txt dosyası yazıyor
- [ ] Hakkında → Günlük klasörünü aç klasörü açıyor
