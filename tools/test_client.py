"""Runs the real game on the connected Android device/emulator and reports what happened.

Launches the app, taps PLAY, waits, then says whether the client is still alive, saves a
screenshot and prints the native crash line if it died. Use it together with the server's
log (run the server with --packet-log) to see how far the client got.

    python tools/test_client.py                     # full run, screenshot in build/
    python tools/test_client.py --wait 40 --shot menu.png
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "air.com.A5thplanetgames.pets"
PLAY_BUTTON = (1077, 655)          # landing screen PLAY, in device coordinates


def adb_path():
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    return str(local) if local.exists() else "adb"


class Adb:
    def __init__(self, serial=None):
        self.base = [adb_path()] + (["-s", serial] if serial else ["-e"])

    def run(self, *args, binary=False):
        result = subprocess.run(self.base + list(args), capture_output=True)
        return result.stdout if binary else result.stdout.decode("utf-8", "replace").strip()

    def shell(self, command):
        return self.run("shell", command)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serial", help="dispositivo adb (padrao: o emulador)")
    parser.add_argument("--boot", type=float, default=32, help="segundos ate a tela inicial")
    parser.add_argument("--wait", type=float, default=32, help="segundos depois de tocar em PLAY")
    parser.add_argument("--no-tap", action="store_true", help="nao toca em PLAY")
    parser.add_argument("--no-launch", action="store_true", help="usa o jogo que ja esta aberto")
    parser.add_argument("--tap", action="append", default=[], metavar="X,Y[,ESPERA]",
                        help="toca nessa posicao e espera (pode repetir para uma sequencia)")
    parser.add_argument("--shot", default="build/client.png", help="onde salvar a captura de tela")
    args = parser.parse_args()

    adb = Adb(args.serial)
    if not args.no_launch:
        adb.run("logcat", "-c")
        adb.shell(f"am force-stop {PACKAGE}")
        time.sleep(3)
        adb.shell(f"monkey -p {PACKAGE} -c android.intent.category.LAUNCHER 1")
        print(f"[..] abrindo o jogo, esperando {args.boot:.0f}s")
        time.sleep(args.boot)
        if not args.no_tap:
            adb.shell(f"input tap {PLAY_BUTTON[0]} {PLAY_BUTTON[1]}")
            print(f"[..] toquei em PLAY, esperando {args.wait:.0f}s")
            time.sleep(args.wait)
    for step in args.tap:
        parts = step.split(",")
        x, y = int(parts[0]), int(parts[1])
        espera = float(parts[2]) if len(parts) > 2 else 6
        adb.shell(f"input tap {x} {y}")
        print(f"[..] toquei em ({x}, {y}), esperando {espera:.0f}s")
        time.sleep(espera)

    shot = ROOT / args.shot
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(adb.run("exec-out", "screencap", "-p", binary=True))
    alive = adb.shell(f"pidof {PACKAGE}")
    crash = [line for line in adb.run("logcat", "-d").splitlines() if "F DEBUG" in line and "signal" in line]
    print(f"[{'ok' if alive else '!!'}] jogo {'rodando (pid ' + alive + ')' if alive else 'MORREU'}")
    for line in crash[:2]:
        print("     ", line.strip()[:150])
    print(f"[ok] captura: {shot}")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
