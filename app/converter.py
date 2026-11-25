"""UUP dosyalarını ISO'ya dönüştürme (resmi uup-converter-wimlib, yalnızca Windows)."""
from __future__ import annotations

import ctypes
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .config import (
    MIRROR_BASE,
    APP_NAME,
    APP_VERSION,
    CONVERTER_LIST_URL,
    FALLBACK_CONVERTER_SHA256,
    FALLBACK_CONVERTER_URL,
    FALLBACK_SEVENZR_SHA256,
    FALLBACK_SEVENZR_URL,
)
from .downloader import Cancelled

LogFn = Callable[[str], None]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ConverterError(Exception):
    pass


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Uygulamayı yönetici olarak yeniden başlatır (UAC istemi açılır)."""
    if not is_windows():
        return False
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, sys.argv[1:]
    else:
        exe, args = sys.executable, sys.argv
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", exe, subprocess.list2cmdline(args), None, 1
    )
    return result > 32


# --------------------------------------------------------------- indirme araçları
def _download_file(
    url: str,
    dest: Path,
    sha256: str,
    cancel: threading.Event,
    log: LogFn,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    log(f"GET {url}")
    with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as out:
        while True:
            if cancel.is_set():
                raise Cancelled()
            block = resp.read(1 << 20)
            if not block:
                break
            digest.update(block)
            out.write(block)
    if sha256 and digest.hexdigest().lower() != sha256.lower():
        part.unlink(missing_ok=True)
        raise ConverterError(f"SHA-256 mismatch: {dest.name}")
    os.replace(part, dest)


def parse_aria_list(text: str) -> list[dict]:
    """aria2 giriş biçimini (url + girintili out=/checksum= satırları) ayrıştırır."""
    entries: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            current = {"url": line.strip(), "out": "", "sha256": ""}
            entries.append(current)
        elif current is not None:
            item = line.strip()
            if item.startswith("out="):
                current["out"] = item[4:]
            elif item.lower().startswith("checksum=sha-256="):
                current["sha256"] = item.split("=", 2)[2].lower()
    return entries


def fetch_manifest(log: LogFn) -> dict:
    """7zr.exe ve dönüştürücü arşivinin güncel adres/özet bilgisini döndürür."""
    fallback = {
        "7zr": {"url": FALLBACK_SEVENZR_URL, "sha256": FALLBACK_SEVENZR_SHA256},
        "conv": {"url": FALLBACK_CONVERTER_URL, "sha256": FALLBACK_CONVERTER_SHA256},
    }
    try:
        req = urllib.request.Request(
            CONVERTER_LIST_URL, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            entries = parse_aria_list(resp.read().decode("utf-8", "replace"))
        by_out = {e["out"]: e for e in entries if e["out"]}
        sevenzr = by_out.get("7zr.exe")
        conv = by_out.get("uup-converter-wimlib.7z")
        if sevenzr and conv and sevenzr["sha256"] and conv["sha256"]:
            return {"7zr": sevenzr, "conv": conv}
    except Exception as exc:  # ağ hatası: son bilinen değerlere dön
        log(f"converter list unavailable, using built-in values ({exc})")
    return fallback


def _download_any(
    url: str, dest: Path, sha256: str, cancel: threading.Event, log: LogFn
) -> None:
    """Önce listedeki adresi, olmazsa git.uupdump.net deposundaki aynı dosyayı dener.

    SHA-256 her iki kaynakta da aynı özetle doğrulanır."""
    name = Path(urllib.parse.urlparse(url).path).name
    candidates = [url]
    mirror = MIRROR_BASE + name
    if name and mirror != url:
        candidates.append(mirror)
    last: Exception | None = None
    for cand in candidates:
        try:
            _download_file(cand, dest, sha256, cancel, log)
            return
        except Cancelled:
            raise
        except (urllib.error.URLError, OSError, ConverterError) as exc:
            log(f"{cand}: {exc}")
            last = exc
    raise ConverterError(f"{name}: {last}")


def ensure_converter(cache_dir: Path, log: LogFn, cancel: threading.Event) -> Path:
    """Dönüştürücüyü indirir ve açar; hazır klasörün yolunu döndürür."""
    if not is_windows():
        raise ConverterError("ISO conversion is only available on Windows")
    cache_dir.mkdir(parents=True, exist_ok=True)
    live = fetch_manifest(log)
    fallback = {
        "7zr": {"url": FALLBACK_SEVENZR_URL, "sha256": FALLBACK_SEVENZR_SHA256},
        "conv": {"url": FALLBACK_CONVERTER_URL, "sha256": FALLBACK_CONVERTER_SHA256},
    }
    candidates = [live] if live["conv"]["sha256"] == fallback["conv"]["sha256"] else [live, fallback]
    last_error: Exception | None = None
    sevenzr = cache_dir / "7zr.exe"
    for manifest in candidates:
        tag = manifest["conv"]["sha256"][:12]
        target = Path(cache_dir) / f"converter-{tag}"
        if (target / "convert-UUP.cmd").exists():
            return target
        archive = cache_dir / f"uup-converter-wimlib-{tag}.7z"
        try:
            _download_any(manifest["7zr"]["url"], sevenzr, manifest["7zr"]["sha256"], cancel, log)
            _download_any(manifest["conv"]["url"], archive, manifest["conv"]["sha256"], cancel, log)
            break
        except ConverterError as exc:
            last_error = exc
            log(f"converter source failed, trying next ({exc})")
    else:
        raise ConverterError(str(last_error))
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(sevenzr), "x", "-y", f"-o{target}", str(archive)],
        capture_output=True,
        creationflags=NO_WINDOW,
    )
    if proc.returncode != 0 or not (target / "convert-UUP.cmd").exists():
        shutil.rmtree(target, ignore_errors=True)
        raise ConverterError("converter archive could not be extracted")
    return target


# ---------------------------------------------------------------- yapılandırma
def patch_ini(path: Path, values: dict, section: str = "convert-UUP") -> None:
    """ConvertConfig.ini içinde yalnızca verilen anahtarları günceller (yoksa ekler)."""
    text = path.read_text("utf-8", errors="replace") if path.exists() else ""
    remaining = dict(values)
    out: list[str] = []
    in_section = False
    found = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section and remaining:
                out.extend(f"{k} ={int(v)}" for k, v in remaining.items())
                remaining = {}
            in_section = stripped[1:-1].strip().lower() == section.lower()
            found = found or in_section
            out.append(line)
            continue
        if in_section:
            match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=", line)
            if match:
                lookup = {k.lower(): k for k in remaining}
                key = lookup.get(match.group(1).lower())
                if key is not None:
                    out.append(f"{match.group(1)} ={int(remaining.pop(key))}")
                    continue
        out.append(line)
    if remaining:
        if not found:
            out.append(f"[{section}]")
        out.extend(f"{k} ={int(v)}" for k, v in remaining.items())
    path.write_text("\r\n".join(out) + "\r\n", encoding="utf-8")


def _run_quiet(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW, timeout=120)
    except Exception:
        pass


def clean_job_dir(job_dir: Path, log: LogFn) -> Path:
    """Önceki (yarım kalmış) dönüştürmeden kalanları temizler; çalışılacak klasörü döndürür.

    Eski bir konsol penceresi/DISM açıksa install.wim kilitli kalır. Önce ilgili süreçler
    sonlandırılır ve DISM bağlamaları temizlenir; kilit sürerse indirilen UUPs klasörü
    yeni bir klasöre taşınır ve oradan devam edilir (yeniden indirme gerekmez)."""
    if not is_windows():
        return job_dir
    # Süreçleri ada/komut satırına göre bul: wimlib-imagex komut satırında tam yol geçmez.
    needle = str(job_dir).replace("'", "''")
    _run_quiet([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ("
        "$_.Name -in 'wimlib-imagex.exe','DismHost.exe','wimserv.exe' -or "
        "$_.CommandLine -like '*convert-UUP*' -or $_.CommandLine -like '*MountUUP*' -or "
        "$_.CommandLine -like '*" + needle + "*') } | ForEach-Object { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
    ])
    # Takılı kalmış DISM bağlamalarını temizle.
    mount_dir = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "MountUUP")
    # Yarım kalan çalışmadan registry'de yüklü kalan hive'lar C:\MountUUP dosyalarını kilitler
    # ve sonraki DISM bağlamasının "dizin boş değil" (0xc1420114) hatasıyla çökmesine yol açar.
    _run_quiet([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "$k='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\hivelist'; "
        "(Get-Item $k).Property | ForEach-Object { "
        "$v=(Get-ItemProperty $k).$_; if ($v -like '*MountUUP*' -and $_ -like '\\REGISTRY\\MACHINE\\*') { "
        "$n=$_.Substring(18); [gc]::Collect(); reg unload \"HKLM\\$n\" | Out-Null } }",
    ])
    _run_quiet(["dism.exe", "/English", "/Unmount-Image", f"/MountDir:{mount_dir}", "/Discard"])
    _run_quiet(["dism.exe", "/English", "/Cleanup-Wim"])
    _run_quiet(["dism.exe", "/English", "/Cleanup-Mountpoints"])
    time.sleep(1.0)
    if _mount_dir_dirty(mount_dir):
        shutil.rmtree(mount_dir, ignore_errors=True)
        if _mount_dir_dirty(mount_dir):
            raise ConverterError(
                f"{mount_dir} önceki yarım kalan dönüştürmeden kilitli kaldı; güncellemeler "
                "uygulanamaz. Bilgisayarı yeniden başlatıp tekrar deneyin."
            )
    leftovers = []
    for item in job_dir.iterdir():
        if item.name.lower() == "uups":
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError:
            leftovers.append(item.name)
    if not leftovers:
        return job_dir
    # Kilit sürüyor: UUPs'u taşıyıp temiz bir klasörde devam et.
    fresh = job_dir.with_name(f"{job_dir.name}_c{int(time.time())}")
    try:
        fresh.mkdir(parents=True)
        os.replace(job_dir / "UUPs", fresh / "UUPs")
    except OSError as exc:
        raise ConverterError(
            "Önceki dönüştürmeden kalan dosyalar kilitli (" + ", ".join(leftovers) + "). "
            "Açık kalan DISM/konsol pencerelerini kapatın ya da bilgisayarı yeniden başlatıp "
            f"tekrar deneyin. ({exc})"
        ) from exc
    log("Kilitli eski klasör atlandı; temiz klasörde devam ediliyor.")
    shutil.rmtree(job_dir, ignore_errors=True)  # kilit çözüldüyse silinir
    return fresh


def mount_dir_path() -> str:
    return os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "MountUUP")


_AV_PROCS = ("TiWorker.exe", "TrustedInstaller.exe", "DismHost.exe", "dism.exe", "wimserv.exe",
             "wimlib-imagex.exe", "oscdimg.exe", "expand.exe")


def _ps(script: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
        return r.returncode == 0, r.stdout
    except (OSError, subprocess.SubprocessError):
        return False, ""


def defender_exclusion(add: bool, paths: list[str], log: LogFn) -> list[str]:
    """Çalışma klasörlerini ve DISM işlemlerini Defender gerçek zamanlı taramasından geçici dışlar.

    DISM binlerce küçük dosyaya dokunduğundan tarama süreyi ciddi uzatır; klasör dışlaması
    TiWorker'ın Windows altındaki geçici dosyalarını kapsamadığı için işlem dışlaması da eklenir.
    Yalnızca kullanıcı ayarı açıksa ve yönetici haklarıyla çalışılır; iş bitince (hata olsa da)
    yalnızca bizim eklediklerimiz kaldırılır (kullanıcının eski dışlamalarına dokunulmaz).

    add=True: eklenenlerin listesini döndürür ("proc:Ad.exe" önekli işlem girdileri dahil).
    add=False: `paths` bu listedir."""
    if not is_windows() or not paths:
        return []
    q = lambda items: ",".join("'" + i.replace("'", "''") + "'" for i in items)  # noqa: E731
    if not add:
        folders = [p for p in paths if not p.startswith("proc:")]
        procs = [p[5:] for p in paths if p.startswith("proc:")]
        if folders:
            _ps(f"Remove-MpPreference -ExclusionPath {q(folders)} -ErrorAction SilentlyContinue")
        if procs:
            _ps(f"Remove-MpPreference -ExclusionProcess {q(procs)} -ErrorAction SilentlyContinue")
        return []
    ok, _ = _ps(f"Add-MpPreference -ExclusionPath {q(paths)} -ErrorAction Stop")
    added = list(paths) if ok else []
    if ok:
        ok2, out = _ps(
            f"$have=@((Get-MpPreference).ExclusionProcess); $new=@({q(_AV_PROCS)} | "
            "Where-Object { $have -notcontains $_ }); "
            "if ($new.Count) { Add-MpPreference -ExclusionProcess $new -ErrorAction Stop }; $new")
        if ok2:
            added += ["proc:" + n.strip() for n in out.splitlines() if n.strip()]
    log("Windows Defender geçici dışlaması eklendi: klasörler ve DISM işlemleri (iş bitince kaldırılır)." if ok
        else "Defender dışlaması eklenemedi (kapalı ya da başka bir antivirüs); devam ediliyor.")
    return added


def _mount_dir_dirty(path: str) -> bool:
    try:
        return os.path.isdir(path) and any(os.scandir(path))
    except OSError:
        return True


_INI_TEMPLATE = """[convert-UUP]
AutoStart ={AutoStart}
AddUpdates ={AddUpdates}
Cleanup ={Cleanup}
ResetBase ={ResetBase}
NetFx3 ={NetFx3}
StartVirtual =0
wim2esd ={wim2esd}
wim2swm =0
SkipISO =0
SkipWinRE =0
LCUwinre =0
LCUmsuExpand =0
UpdtBootFiles =0
ForceDism =0
RefESD =0
SkipLCUmsu =0
SkipEdge =0
AutoExit =1
DisableUpdatingUpgrade =0
AddDrivers =0
Drv_Source =\\Drivers

[Store_Apps]
SkipApps ={SkipApps}
AppsLevel =0
StubAppsFull =0
CustomList =0

[create_virtual_editions]
vUseDism =1
vAutoStart =1
vDeleteSource =0
vPreserve =0
vwim2esd =0
vwim2swm =0
vSkipISO =0
vAutoEditions =
vSortEditions =
"""


def write_ini(path: Path, options: dict) -> None:
    """ConvertConfig.ini'yi tamamen kendimiz yazarız.

    Dönüştürücünün paketindeki varsayılan ini bazı sürümlerde RefESD/ForceDism/UpdtBootFiles/
    LCUmsuExpand gibi yavaşlatan seçenekleri açık getiriyor (günlükteki 'Configured Options').
    Tüm anahtarlar açıkça yazılınca davranış sürümden bağımsız ve hızlı olur."""
    values = {"AutoStart": 1, "AddUpdates": 1, "Cleanup": 0, "ResetBase": 0, "NetFx3": 0,
              "wim2esd": 0, "SkipApps": 0}
    values.update({k: int(bool(v)) for k, v in options.items() if k in values})
    path.write_text(_INI_TEMPLATE.format(**values).replace("\n", "\r\n"), encoding="utf-8")


def prepare_job_dir(job_dir: Path, converter_dir: Path, options: dict) -> None:
    """Dönüştürücüyü iş klasörüne kopyalar ve ConvertConfig.ini'yi yazar."""
    shutil.copytree(converter_dir, job_dir, dirs_exist_ok=True)
    write_ini(job_dir / "ConvertConfig.ini", options)


def _oem_encoding() -> str:
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return "cp850"


def _kill_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW
    )


_ANSI = re.compile(r"\x1b?\[\d{1,3}(?:;\d{1,3})*m")
_DENIED = re.compile(r"(Erişim engellendi|Access is denied)\.?\s*$", re.IGNORECASE)
_BARFRAG = re.compile(r"^[\[\]=\s\d.,%]*$")  # DISM çubuğunun konsol genişliğinde bölünmüş parçaları
_PCT = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")


_ACTIVE_PROCS = ("TiWorker", "TrustedInstaller", "DismHost", "wimserv", "wimlib-imagex", "expand",
                 "oscdimg", "dism", "cmd", "MsMpEng")
_last_snap: dict[int, tuple[float, int, str]] = {}


def _proc_snapshot() -> dict[int, tuple[float, int, str]] | None:
    """{pid: (cpu_saniye, io_bayt)} -- WMI sayaçları; işlemler gelip gitse de pid bazında karşılaştırılır."""
    names = ",".join(f"'{n}.exe'" for n in _ACTIVE_PROCS)
    ps = (f"Get-CimInstance Win32_Process | Where-Object {{ @({names}) -contains $_.Name }} | "
          "ForEach-Object { '{0};{1};{2};{3}' -f $_.ProcessId, "
          "(([double]$_.UserModeTime + [double]$_.KernelModeTime)/10000000), "
          "([double]$_.ReadTransferCount + [double]$_.WriteTransferCount), $_.Name }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                             capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    snap: dict[int, tuple[float, int, str]] = {}
    for line in out.splitlines():
        parts = line.strip().replace(",", ".").split(";")
        if len(parts) == 4:
            try:
                snap[int(parts[0])] = (float(parts[1]), int(float(parts[2])), parts[3])
            except ValueError:
                pass
    return snap


def _dism_activity(quiet_min: int) -> str:
    """Betik sessizken işlemlerin gerçekten çalışıp çalışmadığını CPU ve disk G/Ç farkından anlar.

    Yalnızca iki ölçümde de var olan işlemler karşılaştırılır (negatif fark olmaz). Güncelleme TiWorker
    içinde işlenirken dism.log saatlerce değişmeyebilir; bu yüzden günlük ölçü değildir."""
    snap = _proc_snapshot()
    if snap is None:
        return f"[{quiet_min} dk sessiz] işlem durumu okunamadı."
    prev = dict(_last_snap)
    _last_snap.clear()
    _last_snap.update(snap)
    if not prev:
        return f"[{quiet_min} dk sessiz] işlem izleniyor…"
    av = sum(max(0.0, snap[p][0] - prev[p][0]) for p in snap if p in prev and snap[p][2] == "MsMpEng.exe")
    cpu = sum(max(0.0, snap[p][0] - prev[p][0]) for p in snap if p in prev and snap[p][2] != "MsMpEng.exe")
    io = sum(max(0, snap[p][1] - prev[p][1]) for p in snap if p in prev)
    mb = io / 1048576
    avtxt = f", Defender {int(av)} sn" if av > 5 else ""
    if cpu > 5 or mb > 50:
        return (f"[{quiet_min} dk sessiz] çalışıyor: son 5 dk'da {int(cpu)} sn işlemci, {mb:.0f} MB disk G/Ç{avtxt} "
                "(normal; bu adım yavaş olabilir).")
    if not snap:
        return f"[{quiet_min} dk sessiz] dönüştürücü işlemi görünmüyor."
    return (f"[{quiet_min} dk sessiz] etkinlik çok düşük ({int(cpu)} sn işlemci, {mb:.0f} MB G/Ç{avtxt}): "
            "imaj yazılıyor/bağlama çözülüyor olabilir; 15 dk'dan uzun sürerse kontrol edin.")


PHASES = ("prep", "wim", "update", "save", "build")
_PHASE_RULES = (
    ("build", re.compile(r"adding lcu for boot|creating boot\.wim|rebuilding boot\.wim|creating iso|iso image|oscdimg|virtual edition|exporting.*esd", re.I)),
    ("save", re.compile(r"^(saving image|unmounting image|committing)|rebuilding install\.wim|(creating|updating) winre|remounting image|adding winre", re.I)),
    ("update", re.compile(r"updating install\.wim|adding (lcu|microsoft edge)|servicing index", re.I)),
    ("wim", re.compile(r"creating setup media|creating install\.wim|archiving file data", re.I)),
)


def detect_phase(text: str, current: str) -> str:
    """Dönüştürücü çıktısındaki satırdan aşamayı bulur; aşama yalnızca ileri gider."""
    for phase, rx in _PHASE_RULES:
        if rx.search(text):
            return phase if PHASES.index(phase) > PHASES.index(current) else current
    return current


def run_conversion(
    job_dir: Path,
    log: LogFn,
    cancel: threading.Event,
    on_progress: Callable[[float, str], None] | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> Path:
    """convert-UUP.cmd'yi gizli konsolda çalıştırır; çıktıyı günlüğe ve ilerlemeye yansıtır.

    Betik yönetici değilse kendini yeni pencerede yükseltip hemen çıkar; bu yüzden uygulamanın
    yönetici olması gerekir. -qedit, betiğin konsolu PowerShell ile yeniden başlatmasını atlar."""
    if not is_windows():
        raise ConverterError("ISO conversion is only available on Windows")
    if not (job_dir / "convert-UUP.cmd").exists():
        raise ConverterError("convert-UUP.cmd not found")
    before = {p.name.lower() for p in job_dir.iterdir() if p.suffix.lower() == ".iso"}
    encoding = _oem_encoding()
    proc = subprocess.Popen(
        ["cmd.exe", "/c", "convert-UUP.cmd", "-qedit"],
        cwd=job_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=NO_WINDOW,
    )

    last_out = [time.time()]  # son çıktı zamanı (okuma döngüsü günceller)

    def watcher() -> None:
        next_report = 300.0
        while proc.poll() is None:
            if cancel.wait(0.5):
                _kill_tree(proc.pid)
                return
            quiet = time.time() - last_out[0]
            if quiet < 60:
                next_report = 300.0
            elif quiet >= next_report:
                next_report += 300.0
                log(_dism_activity(int(quiet // 60)))

    threading.Thread(target=watcher, daemon=True).start()
    assert proc.stdout is not None
    buf = b""
    last_ui = 0.0
    last_ui_pct = -1.0
    last_logged_pct = -100.0
    step = ""
    phase = PHASES[0]
    if on_phase:
        on_phase(phase)
    denied = 0
    errors: list[str] = []
    dism_errors: list[str] = []
    while True:
        chunk = proc.stdout.read1(4096)  # type: ignore[attr-defined]
        if not chunk:
            break
        buf += chunk
        last_out[0] = time.time()
        parts = re.split(rb"[\r\n]+", buf)
        buf = parts.pop()  # yarım kalan satır
        for raw in parts:
            text = _ANSI.sub("", raw.decode(encoding, "replace")).strip()
            if not text or set(text) <= set("=-_ "):
                continue
            new_phase = detect_phase(text, phase)
            if new_phase != phase:
                phase = new_phase
                last_logged_pct = -100.0
                if on_phase:
                    on_phase(phase)
            if _DENIED.search(text):
                denied += 1  # eski bağlama kalıntısı temizliği: tek tek günlüğe yazma
                if denied == 1:
                    log("Eski bağlama klasörü (C:\\MountUUP) temizleniyor…")
                continue
            if denied:
                log(f"{denied} dosya silinemedi (eski kalıntı); betik devam ediyor.")
                denied = 0
            match = _PCT.search(text)
            if not match and _BARFRAG.match(text):
                continue  # "]" veya "=====]" gibi artık parçalar
            if match and _BARFRAG.match(text):
                text = f"{step or 'DISM'}: {match.group(1)}%"  # çubuğu sade metne çevir
            if match:
                pct = min(100.0, float(match.group(1).replace(",", ".")))
                now = time.time()
                if on_progress and (now - last_ui >= 0.25 or pct >= 100 or pct < last_ui_pct):
                    on_progress(pct, step or text)
                    last_ui = now
                    last_ui_pct = pct
                new_cycle = pct < last_logged_pct - 5
                if new_cycle or pct - last_logged_pct >= 10 or (pct >= 100 and last_logged_pct < 100):
                    log(text)
                    last_logged_pct = pct
            else:
                if re.match(r"^\[?ERROR\]?:?\s", text, re.IGNORECASE) or text.lower().startswith("error"):
                    errors.append(text)
                if re.match(r"^Error:\s*0x[0-9a-f]+", text, re.IGNORECASE):
                    dism_errors.append(text)
                if text.startswith("==="):
                    step = text.strip("= ").strip()
                    last_logged_pct = -100.0
                log(text)
    tail = buf.decode(encoding, "replace").strip()
    if tail:
        log(tail)
    code = proc.wait()
    if cancel.is_set():
        raise Cancelled()
    isos = [
        p
        for p in job_dir.iterdir()
        if p.suffix.lower() == ".iso" and p.name.lower() not in before
    ]
    if not isos:
        detail = f" - {errors[0]}" if errors else ""
        raise ConverterError(f"no ISO produced (exit code {code}){detail}")
    if dism_errors:
        raise ConverterError(
            f"DISM hata verdi ({dism_errors[0]}); güncellemeler ISO'ya uygulanamadı. "
            "Genellikle önceki yarım kalan bir dönüştürmeden kalma kilittir: bilgisayarı yeniden "
            "başlatıp tekrar deneyin."
        )
    return max(isos, key=lambda p: p.stat().st_mtime)
