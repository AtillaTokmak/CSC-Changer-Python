
#!/usr/bin/env python3
"""
Samsung CSC aracı — AT + ADB

Kullanım:
  python change_csc.py --list
  python change_csc.py --csc THL
  python change_csc.py --csc THL --verify
  python change_csc.py --port /dev/ttyACM0 --csc THL --verify
  python change_csc.py --csc THL --verify --yes

Gereksinim:
  pip install pyserial

Not:
  AT+PRECONFG komutunun kabul edilmesi, CSC'nin kesin değiştiğini
  kanıtlamaz. Sonuç yeniden başlatma sonrasında kontrol edilir.
"""

import argparse
import shutil
import subprocess
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial eksik. Kur: python -m pip install pyserial")


SAMSUNG_VID = 0x04E8
BAUD_RATE = 115200
CMD_TIMEOUT = 6.0
SETTLE = 0.5


def run_adb(*args, timeout=15):
    """ADB komutunu çalıştır ve sonucunu döndür."""
    return subprocess.run(
        ["adb", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def samsung_ports():
    return [
        port for port in list_ports.comports()
        if port.vid == SAMSUNG_VID
    ]


def list_serial_ports():
    ports = list(list_ports.comports())

    if not ports:
        print("Seri port bulunamadı.")
        return

    for port in ports:
        mark = " <-- Samsung" if port.vid == SAMSUNG_VID else ""
        print(f"{port.device:15} {port.description}{mark}")


def pick_port():
    ports = samsung_ports()

    if not ports:
        sys.exit(
            "Samsung seri portu bulunamadı. "
            "--list ile portları kontrol et."
        )

    if len(ports) > 1:
        print("Birden fazla Samsung portu bulundu:")
        for port in ports:
            print(f"  {port.device}: {port.description}")
        sys.exit("--port ile kullanmak istediğin portu seç.")

    print(f"Port otomatik seçildi: {ports[0].device}")
    return ports[0].device


def check_adb_connection():
    try:
        result = run_adb("devices")
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ADB çalıştırılamadı: {exc}")
        return False

    if result.returncode != 0:
        print(result.stderr.strip() or "ADB bağlantı kontrolü başarısız.")
        return False

    devices = [
        line.split()
        for line in result.stdout.splitlines()[1:]
        if line.strip()
    ]

    if any(len(parts) == 2 and parts[1] == "device"
           for parts in devices):
        print("ADB cihazı bağlı ve yetkilendirilmiş.")
        return True

    if any(len(parts) >= 2 and parts[1] == "unauthorized"
           for parts in devices):
        print("ADB yetkisiz. Telefonda USB hata ayıklama iznini onayla.")
    else:
        print("ADB üzerinden hazır cihaz bulunamadı.")

    return False


def send(ser, cmd, timeout=CMD_TIMEOUT, expected=None):
    """
    AT komutunu gönder.

    expected:
      OK/ERROR beklemek yerine, komuta özgü başarı mesajlarını
      da kabul etmek için kullanılan isteğe bağlı metinler.

    Dönüş: (status, response)
      status = ok | error | timeout
    """
    ser.reset_input_buffer()

    print(f">> {cmd}")
    ser.write((cmd + "\r\n").encode("ascii"))
    ser.flush()

    response = ""
    status = "timeout"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)

        if not chunk:
            continue

        response += chunk.decode("ascii", errors="replace")
        lines = [
            line.strip()
            for line in response.replace("\r", "\n").split("\n")
            if line.strip()
        ]

        if any(line == "ERROR" or line.endswith(": ERROR")
               for line in lines):
            status = "error"
            break

        if any(line == "OK" or line.endswith(": OK")
               for line in lines):
            status = "ok"
            break

        if expected and any(token in response for token in expected):
            status = "ok"
            break

    # Yanıtın kalanını toplamak için kısa süre bekle.
    time.sleep(SETTLE)

    if ser.in_waiting:
        response += ser.read(ser.in_waiting).decode(
            "ascii", errors="replace"
        )

    lines = [
        line.strip()
        for line in response.replace("\r", "\n").split("\n")
        if line.strip()
    ]

    for line in lines:
        print(f"<< {line}")

    print(f"   [{status.upper()}]")
    return status, response


def change_csc(port, csc, baud):
    """
    CSC komutlarını gönder.
    Başarılıysa True döndürür.
    """
    try:
        ser = serial.Serial(
            port,
            baudrate=baud,
            timeout=0.3,
            write_timeout=5,
        )
    except (serial.SerialException, OSError) as exc:
        print(f"Seri port açılamadı: {exc}")
        return False

    try:
        with ser:
            steps = [
                (
                    "AT+SWATD=0",
                    ("CHANGE TO DDEXE",),
                ),
                (
                    "AT+ACTIVATE=0,0,0",
                    ("+ACTIVATE:0,OK",),
                ),
                (
                    "AT+SWATD=1",
                    ("CHANGE TO ATD",),
                ),
                (
                    f"AT+PRECONFG=2,{csc}",
                    (f"+PRECONFG:2,OK",),
                ),
            ]

            for cmd, expected in steps:
                status, response = send(
                    ser,
                    cmd,
                    expected=expected,
                )

                # SWATD komutları bazı cihazlarda OK yerine
                # mod değişikliği mesajları döndürebilir.
                if status != "ok":
                    print(f"Komut doğrulanamadı: {cmd}")
                    print("İşlem durduruldu; yeniden başlatılmayacak.")
                    return False

                if cmd.startswith("AT+PRECONFG"):
                    if "+PRECONFG:2,OK" not in response:
                        print("PRECONFG başarı yanıtı bulunamadı.")
                        return False

                    print("PRECONFG komutu kabul edildi.")

    except (serial.SerialException, OSError) as exc:
        print(f"Seri bağlantı hatası: {exc}")
        return False

    # with bloğu bitti: seri port kapandı.
    return True


def reboot_device():
    """ADB ile yeniden başlatmayı iste."""
    print("ADB üzerinden yeniden başlatma isteniyor...")

    try:
        result = run_adb("reboot", timeout=15)
    except subprocess.TimeoutExpired:
        print("ADB reboot zaman aşımına uğradı.")
        print("Cihazın durumunu kontrol et.")
        return False
    except OSError as exc:
        print(f"ADB reboot çalıştırılamadı: {exc}")
        return False

    if result.returncode != 0:
        print("ADB reboot başarısız:")
        print(result.stderr.strip() or result.stdout.strip())
        return False

    print("ADB yeniden başlatma komutunu kabul etti.")
    return True


def wait_for_boot(timeout=180):
    """
    Yeniden başlatmanın gözlenmesini, ADB bağlantısını ve
    Android açılışının tamamlanmasını bekle.
    """
    deadline = time.monotonic() + timeout

    # Önce cihazın ADB'den ayrılmasını gözlemlemeye çalış.
    # Ayrılma gözlenemezse yine de boot_completed kontrolü yapılır.
    disconnect_deadline = min(
        deadline,
        time.monotonic() + 30,
    )
    disconnected = False

    while time.monotonic() < disconnect_deadline:
        try:
            state = run_adb("get-state", timeout=5)
            if state.returncode != 0 or state.stdout.strip() != "device":
                disconnected = True
                break
        except (OSError, subprocess.TimeoutExpired):
            disconnected = True
            break

        time.sleep(1)

    if disconnected:
        print("ADB bağlantısının kesilmesi gözlendi; cihaz bekleniyor.")
    else:
        print("ADB bağlantısının kesilmesi gözlenemedi; açılış kontrol edilecek.")

    while time.monotonic() < deadline:
        try:
            state = run_adb("get-state", timeout=5)

            if state.returncode == 0 and state.stdout.strip() == "device":
                result = run_adb(
                    "shell", "getprop", "sys.boot_completed",
                    timeout=8,
                )

                if (
                    result.returncode == 0
                    and result.stdout.strip() == "1"
                ):
                    return True

        except (OSError, subprocess.TimeoutExpired):
            pass

        time.sleep(2)

    print("Zaman aşımı: Android'in açılışı doğrulanamadı.")
    return False


def verify(csc):
    """Açılış sonrasında CSC property'sini oku."""
    print("\nCSC doğrulaması başlıyor.")

    if not wait_for_boot():
        print("CSC sonucu doğrulanamadı.")
        return False

    try:
        result = run_adb(
            "shell", "getprop", "ro.csc.sales_code",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"CSC okunamadı: {exc}")
        return False

    if result.returncode != 0:
        print("ADB property okuma hatası:")
        print(result.stderr.strip())
        return False

    actual = result.stdout.strip()
    expected = csc.upper()

    print(f"Beklenen CSC: {expected}")
    print(f"Okunan CSC:   {actual or '(boş)'}")

    if actual.upper() == expected:
        print("CSC property doğrulaması başarılı.")
        return True

    print("CSC eşleşmiyor.")
    print(
        "PRECONFG komutu kabul edilmiş olsa da "
        "bu property beklenen değeri göstermiyor."
    )

    # Ek salt okunur tanılama: farklı property kaynaklarını göster.
    for prop in (
        "ro.boot.sales_code",
        "ril.sales_code",
    ):
        try:
            diagnostic = run_adb(
                "shell", "getprop", prop,
                timeout=10,
            )
            value = diagnostic.stdout.strip()
            print(f"{prop} = {value or '(boş)'}")
        except (OSError, subprocess.TimeoutExpired):
            print(f"{prop} okunamadı.")

    return False


def main():
    parser = argparse.ArgumentParser(
        description="Samsung CSC aracı (AT + ADB)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Seri portları listele",
    )
    parser.add_argument(
        "--port",
        help="Seri port; belirtilmezse otomatik seçilir",
    )
    parser.add_argument(
        "--csc",
        help="Üç karakterli CSC kodu, ör. THL veya TUR",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=BAUD_RATE,
        help=f"Seri port hızı (varsayılan: {BAUD_RATE})",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Yeniden başlatma sonrasında CSC'yi doğrula",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Onay sorma",
    )

    args = parser.parse_args()

    if args.list:
        list_serial_ports()
        return

    if not args.csc:
        parser.error("--csc gerekli; portları listelemek için --list kullan.")

    csc = args.csc.strip().upper()

    if len(csc) != 3 or not csc.isalnum():
        parser.error("CSC üç alfasayısal karakterden oluşmalı.")

    if args.baud <= 0:
        parser.error("--baud pozitif bir sayı olmalı.")

    if not shutil.which("adb"):
        sys.exit("ADB bulunamadı. Android platform-tools kurulu olmalı.")

    if not check_adb_connection():
        sys.exit(
            "Önce ADB bağlantısını ve USB hata ayıklama iznini kontrol et."
        )

    port = args.port or pick_port()

    if not args.yes:
        answer = input(
            f"{port} üzerindeki cihazın CSC'si {csc} yapılacak. "
            "Devam? [e/H] "
        )
        if answer.strip().lower() not in ("e", "evet", "y", "yes"):
            sys.exit("İptal edildi.")

    if not change_csc(port, csc, args.baud):
        sys.exit("AT işlemi doğrulanamadı; yeniden başlatma yapılmadı.")

    print("\nAT komut aşaması tamamlandı.")

    if not reboot_device():
        sys.exit(
            "Yeniden başlatma doğrulanamadı. "
            "Cihazın durumunu kontrol et; otomatik doğrulama yapılmadı."
        )

    if args.verify:
        verify(csc)
    else:
        print("Yeniden başlatma istendi.")
        print("Açılıştan sonra kontrol et:")
        print("adb shell getprop ro.csc.sales_code")


if __name__ == "__main__":
    main()
