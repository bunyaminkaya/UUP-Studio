# Üçüncü taraf bileşenler

UUP Studio aşağıdaki projelere dayanır. Lisans metinlerini ve koşullarını dağıtımdan önce
ilgili projelerin güncel sayfalarından doğrulayın.

| Bileşen | Kullanım | Kaynak |
|---|---|---|
| UUP dump | Build, dil, sürüm listesi ve indirme bağlantıları (JSON API) | https://uupdump.net |
| uup-converter-wimlib | UUP dosyalarını ISO'ya dönüştürür (ilk kullanımda indirilir, pakete dahil değildir) | https://git.uupdump.net/uup-dump/converter · yazar: abbodi1406 ve katkıda bulunanlar |
| Qt for Python (PySide6) | Arayüz | https://doc.qt.io/qtforpython-6/ · LGPLv3 |
| PyInstaller | EXE paketleme (derleme aracı) | https://pyinstaller.org |

## Notlar
- PySide6 (Qt) LGPLv3 ile lisanslıdır. EXE "klasör" (one-folder) modunda üretildiği için Qt
  kitaplıkları ayrı DLL olarak bulunur ve kullanıcı tarafından değiştirilebilir. Tek dosya
  (`--onefile`) pakete çevirirseniz LGPL gereklerini yeniden değerlendirin.
- UUP Studio, Microsoft ile bağlantılı değildir. Windows dosyaları Microsoft'un Windows Update
  sunucularından indirilir; oluşturulan ISO'daki Windows'un lisansı ve etkinleştirilmesi
  kullanıcıya aittir.
