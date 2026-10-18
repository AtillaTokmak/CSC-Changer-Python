# Samsung CSC Değiştirme Aracı (AT + ADB)

Bu Python aracı, Samsung cihazların **CSC (Country Specific Code / Ülkeye Özgü Kod)** ayarını seri port üzerinden gönderilen **AT komutları** ve **ADB (Android Debug Bridge)** yardımıyla değiştirmek, cihazı yeniden başlatmak ve işlem sonucunu doğrulamak için geliştirilmiş bir komut satırı uygulamasıdır.

---

## ✨ Özellikler

- **Otomatik Port Tespiti:** Bilgisayara bağlı Samsung modem/seri portlarını (`VID: 0x04E8`) otomatik olarak bulur ve seçer.
- **ADB Entegrasyonu:** İşlem öncesi cihazın ADB bağlantısını ve yetkilendirme durumunu kontrol eder, işlem sonrasında cihazı güvenli şekilde yeniden başlatır.
- **Güvenli İletişim:** AT komutlarının (`AT+SWATD`, `AT+ACTIVATE`, `AT+PRECONFG`) yanıtlarını adım adım dinler; hata durumunda işlemi durdurarak cihazın gereksiz yere yeniden başlatılmasını önler.
- **Otomatik Doğrulama (`--verify`):** Cihaz yeniden başladıktan sonra Android sisteminin tamamen açılmasını (`sys.boot_completed`) bekler ve yeni CSC kodunun uygulanıp uygulanmadığını `getprop` ile kontrol eder.

---

## 🛠️ Gereksinimler

### 1. Yazılım ve Kütüphaneler
- **Python 3.6+**
- **pyserial** kütüphanesi
- **ADB (Android Platform Tools):** Sisteminizde kurulu ve `PATH` (ortam değişkenleri) içerisine eklenmiş olmalıdır.
- **Samsung USB Sürücüleri:** Cihazın seri port (modem) olarak tanınması için gereklidir (Özellikle Windows kullanıcıları için).

### 2. Cihaz Hazırlığı
1. Telefonunuzda **Geliştirici Seçenekleri**'ni açın ve **USB Hata Ayıklama (USB Debugging)** özelliğini etkinleştirin.
2. Cihazınızı USB kablosu ile bilgisayara bağlayın ve telefon ekranına gelen **"USB hata ayıklamasına izin ver"** uyarısını onaylayın.
3. *(Cihaza/Yazılıma göre değişebilir)* Telefonunuzun arama ekranından `*#0808#` veya `*#9090#` tuşlayarak USB ayarlarının `MTP + ADB` (veya `DM + MODEM + ADB`) modunda olduğundan emin olun.

---

## 🚀 Kurulum

Projeyi indirdikten sonra gerekli olan tek Python kütüphanesi `pyserial`'ı aşağıdaki komutla kurabilirsiniz:

```bash
python -m pip install pyserial
```

ADB'nin sisteminizde çalışıp çalışmadığını doğrulamak için:
```bash
adb --version
```

---

## 💻 Kullanım

### Seri Portları Listeleme
Bilgisayara bağlı tüm seri portları görmek ve hangisinin Samsung cihazınıza ait olduğunu tespit etmek için:
```bash
python change_csc.py --list
```
*Çıktıda Samsung cihazların yanında `<-- Samsung` işareti yer alır.*

### CSC Değiştirme (Standart)
Samsung portunu otomatik seçerek CSC'yi değiştirmek (örneğin `THL` veya `TUR` yapmak) için:
```bash
python change_csc.py --csc THL
```

### CSC Değiştirme ve Otomatik Doğrulama (Önerilen)
CSC komutları gönderildikten sonra cihazın yeniden başlamasını beklemek ve yeni CSC kodunu otomatik olarak kontrol etmek için `--verify` parametresini ekleyin:
```bash
python change_csc.py --csc THL --verify
```

### Belirli Bir Port Seçerek ve Onay Sormadan Çalıştırma
Birden fazla Samsung portu varsa veya betiği otomasyon içinde kullanıyorsanız:
```bash
# Linux / macOS örneği:
python change_csc.py --port /dev/ttyACM0 --csc TUR --verify --yes

# Windows örneği:
python change_csc.py --port COM4 --csc TUR --verify --yes
```

---

## ⚙️ Komut Satırı Parametreleri

| Parametre | Açıklama |
| :--- | :--- |
| `--list` | Bilgisayardaki mevcut seri portları listeler ve Samsung portlarını işaretler. |
| `--csc <KOD>` | **(Zorunlu)** Uygulanacak 3 karakterli alfasayısal CSC kodu (Örn: `TUR`, `THL`, `EUX`). |
| `--port <PORT>` | Kullanılacak seri port adı (Örn: `COM3` veya `/dev/ttyACM0`). Belirtilmezse otomatik seçilir. |
| `--baud <HIZ>` | Seri port iletişim hızı (Varsayılan: `115200`). |
| `--verify` | Yeniden başlatma sonrasında cihazın açılmasını bekler ve CSC değişimini doğrular. |
| `-y`, `--yes` | İşlem öncesinde kullanıcıdan `[e/H]` onayı istemeden doğrudan işleme başlar. |

---

## 🔍 Çalışma Mantığı

Betik çalıştırıldığında sırasıyla şu adımları izler:

1. **Ön Kontroller:** `adb` komutunun varlığını ve cihazın yetkilendirilmiş (`device`) durumda olduğunu doğrular.
2. **Seri Port Bağlantısı:** Seçilen port üzerinden cihazla seri iletişim başlatır ve sırasıyla şu AT komutlarını gönderir:
   - `AT+SWATD=0` *(Beklenen: `CHANGE TO DDEXE` veya `OK`)*
   - `AT+ACTIVATE=0,0,0` *(Beklenen: `+ACTIVATE:0,OK` veya `OK`)*
   - `AT+SWATD=1` *(Beklenen: `CHANGE TO ATD` veya `OK`)*
   - `AT+PRECONFG=2,<CSC>` *(Beklenen: `+PRECONFG:2,OK`)*
3. **Yeniden Başlatma:** Komutlar başarıyla kabul edilirse `adb reboot` ile cihaz yeniden başlatılır.
4. **Doğrulama (`--verify` aktifse):**
   - Cihazın kapanıp tekrar açılması ve `sys.boot_completed` değerinin `1` olması beklenir (Maksimum 180 saniye).
   - `ro.csc.sales_code` özelliği okunarak hedeflenen CSC ile karşılaştırılır. Eşleşme olmazsa tanı amaçlı `ro.boot.sales_code` ve `ril.sales_code` değerleri ekrana yazdırılır.

---

## ⚠️ Önemli Notlar ve Sorumluluk Reddi

- **Uyumluluk:** `AT+PRECONFG` komutunun cihaz tarafından kabul edilmesi (`+PRECONFG:2,OK`), CSC'nin her zaman kesin olarak değişeceği anlamına gelmez. Cihazınızda yüklü olan mevcut yazılımın (Multi-CSC seperti `OXM`) hedeflediğiniz CSC kodunu desteklemesi gerekir. Ayrıca yeni güvenlik yamaları bu yöntemi kısıtlamış olabilir.
- **İzinler (Linux):** Linux kullanıyorsanız `/dev/ttyACM*` portlarına erişim için kullanıcınızın `dialout` veya `uucp` grubunda olması ya da betiği uygun izinlerle çalıştırmanız gerekebilir.
- **Sorumluluk:** Bu araç yalnızca eğitim ve geliştirme amaçlıdır. Cihaz üzerinde yapılacak işlemlerin sorumluluğu tamamen kullanıcıya aittir.

## Krediler

Bu araç, **[Alephgsm](https://github.com/Alephgsm)** tarafından yayınlanan
**[Change-CSC-AT-Command](https://github.com/Alephgsm/Change-CSC-AT-Command)** deposundaki yöntemin
Python'a uyarlanmış halidir. Komut dizisi ve yöntem orijinal depoya aittir, bu proje sadece onu otomatikleştirir.
