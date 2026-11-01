"""Combine screencast frames and narration into an MP4.

Usage: python assemble.py <work dir> <output.mp4>   (requires the imageio-ffmpeg package)
"""

import json
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg


def main():
    work, out = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads((work / "timeline.json").read_text(encoding="utf-8"))
    frames, timeline, duration = data["frames"], data["timeline"], data["duration"]

    # Video: concat list with each frame's on-screen time.
    first = frames[0]["t"]
    lines = []
    for i, f in enumerate(frames):
        next_t = frames[i + 1]["t"] if i + 1 < len(frames) else first + duration
        lines.append(f"file 'frames/{f['name']}'")
        lines.append(f"duration {max(next_t - f['t'], 0.001):.4f}")
    lines.append(f"file 'frames/{frames[-1]['name']}'")
    (work / "frames.txt").write_text("\n".join(lines), encoding="utf-8")

    # Audio: place each narration clip at the moment its segment actually started.
    rate = 22050
    total = bytearray(int((duration + 1) * rate) * 2)
    for seg in timeline:
        with wave.open(seg["wav"], "rb") as w:
            pcm = w.readframes(w.getnframes())
        start = int(seg["at"] * rate) * 2
        total[start:start + len(pcm)] = pcm
    with wave.open(str(work / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(total))

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", "frames.txt", "-i", "narration.wav",
        "-vf", "fps=20,scale=1440:900:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(out.resolve()),
    ], cwd=work, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {duration:.1f} s)")


if __name__ == "__main__":
    main()
