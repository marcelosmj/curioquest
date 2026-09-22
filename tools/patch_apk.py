#!/usr/bin/env python3
"""Build a Curio Quest APK that talks to the offline server instead of 5th Planet's servers.

Rewrites three URLs inside assets/Pets.swf - the content CDN, the PHP endpoint and the
www.google.com internet check - then repackages, zipaligns and signs the APK.

Usage:
  python tools/patch_apk.py --host 10.0.2.2       (Android emulator: 10.0.2.2 is the PC)
  python tools/patch_apk.py --host 192.168.0.10   (phone on the same Wi-Fi: the PC's LAN IP)
"""
import argparse
import os
import shutil
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APK = ROOT / "Curio Quest_1.15.00.apk"
KEYSTORE = ROOT / "tools" / "curioquest-offline.keystore"
KEY_ALIAS = "curioquest"
KEY_PASS = "curioquest"

URL_REWRITES = {
    "https://content.5thplanetgames.com/pets_live/": "http://{host}:{port}/pets_live/",
    "https://curioweb.5thplanetgames.com/game/": "http://{host}:{port}/game/",
    "http://www.google.com": "http://{host}:{port}/",
}

# Analytics services the game calls on its own. They are dead too, and a failed call is one
# more thing that can take the client down, so they also point at the offline server, which
# answers "OK" to anything outside /pets_live/. Missing ones are only a warning.
OPTIONAL_REWRITES = {
    "http://collect4328crqst.deltadna.net/collect/api/": "http://{host}:{port}/collect/",
    "http://engage4328crqst.deltadna.net": "http://{host}:{port}",
    "http://www.deltadna.net/qa/": "http://{host}:{port}/",
}

TAG_END, TAG_DOABC, TAG_DOABC2 = 0, 72, 82


def read_u30(buf, pos):
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return result, pos


def write_u30(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def rewrite_abc_strings(abc, rewrites):
    """Replace whole strings in an ABC constant pool. Returns (new_abc, replaced_count)."""
    pos = 4                                   # minor_version, major_version
    count, pos = read_u30(abc, pos)           # int pool
    for _ in range(max(0, count - 1)):
        _, pos = read_u30(abc, pos)
    count, pos = read_u30(abc, pos)           # uint pool
    for _ in range(max(0, count - 1)):
        _, pos = read_u30(abc, pos)
    count, pos = read_u30(abc, pos)           # double pool
    pos += 8 * max(0, count - 1)
    pool_start = pos
    count, pos = read_u30(abc, pos)           # string pool
    pool = bytearray(write_u30(count))
    replaced = 0
    for _ in range(max(0, count - 1)):
        length, pos = read_u30(abc, pos)
        value = bytes(abc[pos:pos + length])
        pos += length
        if value in rewrites:
            value = rewrites[value]
            replaced += 1
        pool += write_u30(len(value)) + value
    return bytes(abc[:pool_start]) + bytes(pool) + bytes(abc[pos:]), replaced


def patch_swf(swf, rewrites):
    signature, version = swf[:3], swf[3]
    if signature == b"CWS":
        body = zlib.decompress(swf[8:])
    elif signature == b"FWS":
        body = swf[8:]
    else:
        raise SystemExit(f"SWF com compressao nao suportada: {signature!r}")
    rect_bits = body[0] >> 3
    pos = (5 + rect_bits * 4 + 7) // 8 + 4    # frame size RECT, frame rate, frame count
    out = bytearray(body[:pos])
    replaced = 0
    while pos < len(body):
        (code_and_length,) = struct.unpack_from("<H", body, pos)
        code, length, header_len = code_and_length >> 6, code_and_length & 0x3F, 2
        if length == 0x3F:
            (length,) = struct.unpack_from("<I", body, pos + 2)
            header_len = 6
        tag = body[pos + header_len:pos + header_len + length]
        if code in (TAG_DOABC, TAG_DOABC2):
            prefix_len = tag.index(b"\x00", 4) + 1 if code == TAG_DOABC2 else 0   # flags + name
            abc, count = rewrite_abc_strings(tag[prefix_len:], rewrites)
            replaced += count
            tag = tag[:prefix_len] + abc
            out += struct.pack("<HI", (code << 6) | 0x3F, len(tag)) + tag
        else:
            out += body[pos:pos + header_len + length]
        pos += header_len + length
        if code == TAG_END:
            break
    out += body[pos:]
    return b"CWS" + bytes([version]) + struct.pack("<I", 8 + len(out)) + zlib.compress(bytes(out), 9), replaced


def rebuild_apk(source_apk, target_apk, patched_swf):
    with zipfile.ZipFile(source_apk) as zin, zipfile.ZipFile(target_apk, "w") as zout:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC", ".MF")):
                continue  # original signature; apksigner writes a new one
            data = patched_swf if name == "assets/Pets.swf" else zin.read(name)
            entry = zipfile.ZipInfo(name, date_time=info.date_time)
            entry.compress_type = info.compress_type
            entry.external_attr = info.external_attr
            zout.writestr(entry, data)


def android_build_tools():
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
               or Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk")
    exe, script = (".exe", ".bat") if os.name == "nt" else ("", "")
    versions = sorted((sdk / "build-tools").glob("*"), key=lambda p: [int(x) for x in p.name.split(".") if x.isdigit()],
                      reverse=True)
    for version_dir in versions:
        zipalign, apksigner = version_dir / f"zipalign{exe}", version_dir / f"apksigner{script}"
        if zipalign.exists() and apksigner.exists():
            return zipalign, apksigner
    raise SystemExit(f"Android SDK build-tools (zipalign/apksigner) nao encontrado em {sdk}")


def run(cmd):
    cmd = [str(part) for part in cmd]
    if os.name == "nt" and cmd[0].lower().endswith(".bat"):
        cmd = ["cmd", "/c"] + cmd
    subprocess.run(cmd, check=True)


def ensure_keystore():
    if KEYSTORE.exists():
        return
    keytool = shutil.which("keytool")
    if not keytool:
        raise SystemExit("keytool (Java) nao encontrado no PATH")
    run([keytool, "-genkeypair", "-keystore", KEYSTORE, "-storepass", KEY_PASS, "-keypass", KEY_PASS,
         "-alias", KEY_ALIAS, "-keyalg", "RSA", "-keysize", "2048", "-validity", "36500",
         "-dname", "CN=Curio Quest Offline, O=Preservacao"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="IP do PC visto pelo aparelho (emulador: 10.0.2.2)")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rewrites = {old.encode(): new.format(host=args.host, port=args.http_port).encode()
                for old, new in {**URL_REWRITES, **OPTIONAL_REWRITES}.items()}
    with zipfile.ZipFile(args.apk) as apk:
        swf = apk.read("assets/Pets.swf")
    patched, replaced = patch_swf(swf, rewrites)
    if replaced < len(URL_REWRITES):
        raise SystemExit(f"esperava trocar ao menos {len(URL_REWRITES)} URLs no Pets.swf, troquei {replaced}")
    if patch_swf(patched, rewrites)[1] != 0:
        raise SystemExit("verificacao falhou: URLs originais ainda presentes no SWF gerado")
    print(f"[ok] Pets.swf: {replaced} URLs apontadas para http://{args.host}:{args.http_port}/")

    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    out = args.out or build / f"CurioQuest-offline-{args.host}.apk"
    unsigned, aligned = build / "tmp-unsigned.apk", build / "tmp-aligned.apk"
    rebuild_apk(args.apk, unsigned, patched)
    zipalign, apksigner = android_build_tools()
    ensure_keystore()
    run([zipalign, "-f", "-p", "4", unsigned, aligned])
    run([apksigner, "sign", "--ks", KEYSTORE, "--ks-key-alias", KEY_ALIAS, "--ks-pass", f"pass:{KEY_PASS}",
         "--key-pass", f"pass:{KEY_PASS}", "--out", out, aligned])
    unsigned.unlink()
    aligned.unlink()
    print(f"[ok] APK assinado: {out}")


if __name__ == "__main__":
    main()
