"""Bundle the FastAPI sidecar and native ffmpeg for the current platform."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import imageio_ffmpeg  # noqa: E402  (installed through requirements-desktop.txt)

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "desktop" / "build"
EXECUTABLE = "frame-get-api.exe" if os.name == "nt" else "frame-get-api"


def main():
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onedir", "--name", "frame-get-api",
            "--distpath", str(BUILD), "--workpath", str(BUILD / "work"),
            "--specpath", str(BUILD),
            "--paths", str(ROOT),
            "--collect-all", "yt_dlp", "--collect-all", "yt_dlp_ejs",
            "--collect-submodules", "uvicorn",
            str(ROOT / "server" / "desktop.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    binary = BUILD / "frame-get-api" / EXECUTABLE
    if not binary.is_file():
        raise RuntimeError(f"Backend binary was not created: {binary}")
    ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
    destination = BUILD / "ffmpeg" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ffmpeg, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    print(f"Backend: {binary}")
    print(f"FFmpeg: {destination}")


if __name__ == "__main__":
    main()
