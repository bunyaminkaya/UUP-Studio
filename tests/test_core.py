"""Çekirdek modül testleri (ağ gerektirmez): python -m unittest discover -s tests"""
import hashlib
import http.server
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import RemoteFile  # noqa: E402
from app.converter import parse_aria_list, patch_ini  # noqa: E402
from app.downloader import Cancelled, DownloadError, Downloader, verify_files  # noqa: E402


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Range başlığını destekleyen basit sunucu."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = Path(self.directory) / self.path.lstrip("/")
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        rng = self.headers.get("Range")
        start = 0
        if rng:
            start = int(re.match(r"bytes=(\d+)-", rng).group(1))
            if start >= len(data):
                self.send_error(416)
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data)-1}/{len(data)}")
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp())
        cls.srv_dir = cls.root / "srv"
        cls.srv_dir.mkdir()
        cls.blobs = {}
        for i in range(6):
            data = os.urandom(1_500_000 + i * 1000)
            (cls.srv_dir / f"f{i}.cab").write_bytes(data)
            cls.blobs[f"f{i}.cab"] = data
        handler = lambda *a, **k: RangeHandler(*a, directory=str(cls.srv_dir), **k)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.root, ignore_errors=True)

    def files(self, bad_hash=False):
        out = []
        for name, data in self.blobs.items():
            sha = hashlib.sha1(data).hexdigest()
            if bad_hash and name == "f2.cab":
                sha = "0" * 40
            out.append(RemoteFile(name, f"http://127.0.0.1:{self.port}/{name}", len(data), sha))
        return out

    def test_download_and_verify(self):
        dest = self.root / "d1"
        dl = Downloader(self.files(), dest, workers=3)
        seen = []
        dl.run(on_progress=seen.append)
        self.assertTrue(seen)
        self.assertEqual(seen[-1]["percent"], 100.0)
        for name, data in self.blobs.items():
            self.assertEqual((dest / name).read_bytes(), data)
        verify_files(self.files(), dest)

    def test_resume_partial(self):
        dest = self.root / "d2"
        dest.mkdir()
        data = self.blobs["f0.cab"]
        (dest / "f0.cab.part").write_bytes(data[:700_000])
        Downloader(self.files()[:1], dest, workers=1).run()
        self.assertEqual((dest / "f0.cab").read_bytes(), data)

    def test_bad_hash_detected_and_removed(self):
        dest = self.root / "d3"
        files = self.files(bad_hash=True)
        Downloader(files, dest, workers=2).run()
        with self.assertRaises(DownloadError):
            verify_files(files, dest)
        self.assertFalse((dest / "f2.cab").exists())

    def test_cancel(self):
        dest = self.root / "d4"
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            Downloader(self.files(), dest, workers=2, cancel=cancel).run()

    def test_http_404_is_error(self):
        dest = self.root / "d5"
        bad = [RemoteFile("nope.cab", f"http://127.0.0.1:{self.port}/nope.cab", 10, "")]
        with self.assertRaises(DownloadError):
            Downloader(bad, dest, workers=1).run()

    def test_parse_aria_list(self):
        text = (
            "https://uupdump.net/misc/7zr.exe\n  out=7zr.exe\n  checksum=sha-256=AABB\n\n"
            "https://uupdump.net/misc/conv.7z\n  out=uup-converter-wimlib.7z\n  checksum=sha-256=ccdd\n"
        )
        items = parse_aria_list(text)
        self.assertEqual([i["out"] for i in items], ["7zr.exe", "uup-converter-wimlib.7z"])
        self.assertEqual(items[0]["sha256"], "aabb")

    def test_patch_ini(self):
        ini = self.root / "ConvertConfig.ini"
        ini.write_text(
            "[convert-UUP]\r\nAutoStart =0\r\nAddUpdates =1\r\nCleanup =1\r\n\r\n[Other]\r\nX =1\r\n",
            encoding="utf-8",
        )
        patch_ini(ini, {"AutoStart": 1, "Cleanup": False, "NetFx3": True})
        text = ini.read_text("utf-8")
        self.assertIn("AutoStart =1", text)
        self.assertIn("Cleanup =0", text)
        self.assertIn("AddUpdates =1", text)
        self.assertIn("NetFx3 =1", text)
        self.assertLess(text.index("NetFx3"), text.index("[Other]"))
        self.assertIn("X =1", text)
        new = self.root / "new.ini"
        patch_ini(new, {"AutoStart": 1})
        self.assertIn("[convert-UUP]", new.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()


class PhaseTests(unittest.TestCase):
    def test_phase_detection_is_monotonic(self):
        from app.converter import detect_phase

        ph = "prep"
        seq = [
            ("=== Preparing Reference ESDs . . .", "prep"),
            ("=== Creating install.wim . . .", "wim"),
            ("=== Updating install.wim / 1 image{s} . . .", "update"),
            ("Saving image", "save"),
            ("Servicing Index: 1: 11.0%", "save"),  # geri gitmez
            ("=== Creating boot.wim . . .", "build"),
        ]
        for line, want in seq:
            ph = detect_phase(line, ph)
            self.assertEqual(ph, want, line)
