"""Record the demo video end to end: fresh server, scripted walkthrough, narration, MP4.

Windows only, because it uses Windows speech and Microsoft Edge.
Needs: pip install imageio-ffmpeg, and npm install playwright-core in some folder.
Usage: python scripts/video/make_video.py <short work dir> <playwright-core path> <output.mp4>
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = 5058


def main():
    work, playwright, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
    video_dir = work / "video"
    db = work / "demo.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(db) + suffix).unlink(missing_ok=True)
    server = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "--port", str(PORT), "--db", str(db)], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/meta", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        env = dict(os.environ, PLAYWRIGHT_CORE=playwright)
        subprocess.run(["node", str(ROOT / "scripts" / "video" / "record.cjs"), str(video_dir), f"http://127.0.0.1:{PORT}", str(db), sys.executable],
                       env=env, check=True)
    finally:
        server.terminate()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "video" / "assemble.py"), str(video_dir), str(output)], check=True)


if __name__ == "__main__":
    main()
