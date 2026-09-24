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


    # Bypass mobile Advertising.getID() hang on modern Android:
    # Jump directly over the if(AppInfo.isMobile()) block to CharacterDALC.doLoginPlatform()
    ADV_PATTERN = bytes.fromhex("60 ef 06 46 97 53 00 12 34 00 00")
    ADV_REPLACEMENT = bytes.fromhex("10 3b 00 00 02 02 02 02 02 02 02")
    if ADV_PATTERN in body:
        body = body.replace(ADV_PATTERN, ADV_REPLACEMENT, 1)
        print("[ok] Patched Project.doLoginPlatform with direct jump to CharacterDALC.doLoginPlatform()")

    # Bypass crash-prone native telemetry/tracking SDKs (Adjust, Fabric, Supersonic):
    INIT_NATIVE_PATTERN = bytes.fromhex("60 ef 06 46 97 53 00 12 0b 00 00 5d 84 50 4f 84 50 00")
    INIT_NATIVE_REPLACEMENT = bytes.fromhex("60 ef 06 46 97 53 00 12 0b 00 00 02 02 02 02 02 02 02")
    if INIT_NATIVE_PATTERN in body:
        body = body.replace(INIT_NATIVE_PATTERN, INIT_NATIVE_REPLACEMENT, 1)
        print("[ok] Patched CurioQuest.init: bypassed crash-prone native telemetry (Adjust/Fabric/Supersonic)")

    # Bypass audio playback (prevents FP_AudioCallback AudioTrack.write crash in ARM emulation / headless):
    PLAY_MUSIC_PATTERN = bytes.fromhex("5d bd 51 4f bd 51 00")
    PLAY_MUSIC_REPLACEMENT = bytes.fromhex("47 02 02 02 02 02 02")
    if PLAY_MUSIC_PATTERN in body:
        body = body.replace(PLAY_MUSIC_PATTERN, PLAY_MUSIC_REPLACEMENT, 1)
        print("[ok] Patched AudioManager.playMusic: early return to prevent audio thread crashes")

    PLAY_SOUND_PATTERN = bytes.fromhex("65 01 d1 6d 01 65 01 6c 01 11 01 00 00 47")
    PLAY_SOUND_REPLACEMENT = bytes.fromhex("47 02 02 02 02 02 02 02 02 02 02 02 02 02")
    if PLAY_SOUND_PATTERN in body:
        body = body.replace(PLAY_SOUND_PATTERN, PLAY_SOUND_REPLACEMENT, 1)
        print("[ok] Patched AudioManager.playSound: early return to prevent audio thread crashes")

    # Bypass dead third-party native extensions (GoViral / Facebook, GoogleGames / Play Games, StoreKit, AndroidIAB):
    # Replaces callproperty isSupported() (46 ad 52 00) with:
    # pop (0x29) [pops the class object], pushfalse (0x27) [pushes false], nop (0x02), nop (0x02).
    # Result: isSupported() returns false everywhere cleanly without stack imbalance or native JNI calls!
    IS_SUPPORTED_PATTERN = bytes.fromhex("46 ad 52 00")
    IS_SUPPORTED_REPLACEMENT = bytes.fromhex("29 27 02 02")
    count_supp = body.count(IS_SUPPORTED_PATTERN)
    if count_supp > 0:
        body = body.replace(IS_SUPPORTED_PATTERN, IS_SUPPORTED_REPLACEMENT)
        print(f"[ok] Patched isSupported across {count_supp} call sites (GoViral/GoogleGames/Billing -> return false)")


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


def patch_libcore(so_bytes):
    """ATENCAO: desligado por padrao (--patch-libcore para ligar).

    O patch 2 (AVMPI_allocateCodeMemory -> NULL) MATA o app no arranque.  Medido no
    Redmi Note 11S / Android 13 em 24/09/2026:

        Zygote: Process 3144 exited due to signal 11 (Segmentation fault)
        DigestGenerator: ... libCore.so (nanojit::CodeAlloc::addMem()+)

    A intencao era forcar o interpretador AVM2 no lugar do JIT, mas devolver NULL nao
    desliga o JIT: o nanojit::CodeAlloc::addMem() usa o ponteiro devolvido sem testar
    se e nulo, e o processo morre antes de desenhar a primeira tela.  Sem este patch o
    app sobe normalmente (foi assim que a build de 23/09 16:13 rodou).
    """
    so = bytearray(so_bytes)
    RET0_THUMB = bytes.fromhex("00 20 70 47")  # movs r0, #0; bx lr

    # Patch 1: InvokerCompiler::canCompileInvoker -> return false (0)
    # Offset 0x939fca: d0 b5 02 af -> 00 20 70 47
    INVOKER_OFFSET = 0x939fca
    INVOKER_ORIG = bytes.fromhex("d0 b5 02 af")
    if so[INVOKER_OFFSET:INVOKER_OFFSET+4] == INVOKER_ORIG:
        so[INVOKER_OFFSET:INVOKER_OFFSET+4] = RET0_THUMB
        print("[ok] Patched libCore.so: canCompileInvoker -> return false (disables JIT invokers)")

    # Patch 2: AVMPI_allocateCodeMemory -> return NULL (0)
    # Offset 0x98ef3c: f0 b5 03 af -> 00 20 70 47
    ALLOC_OFFSET = 0x98ef3c
    ALLOC_ORIG = bytes.fromhex("f0 b5 03 af")
    if so[ALLOC_OFFSET:ALLOC_OFFSET+4] == ALLOC_ORIG:
        so[ALLOC_OFFSET:ALLOC_OFFSET+4] = RET0_THUMB
        print("[ok] Patched libCore.so: AVMPI_allocateCodeMemory -> return NULL (forces AVM2 interpreter)")

    return bytes(so)


def rebuild_apk(source_apk, target_apk, patched_swf, patched_libcore=None):
    with zipfile.ZipFile(source_apk) as zin, zipfile.ZipFile(target_apk, "w") as zout:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC", ".MF")):
                continue  # original signature; apksigner writes a new one
            if name == "assets/Pets.swf":
                data = patched_swf
            elif patched_libcore and name == "lib/armeabi-v7a/libCore.so":
                data = patched_libcore
            else:
                data = zin.read(name)
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
    parser.add_argument("--patch-libcore", action="store_true",
                        help="aplica os patches binarios no libCore.so (SEGFAULT conhecido: ver patch_libcore)")
    args = parser.parse_args()

    rewrites = {old.encode(): new.format(host=args.host, port=args.http_port).encode()
                for old, new in {**URL_REWRITES, **OPTIONAL_REWRITES}.items()}
    with zipfile.ZipFile(args.apk) as apk:
        swf = apk.read("assets/Pets.swf")
        libcore = apk.read("lib/armeabi-v7a/libCore.so")
    patched, replaced = patch_swf(swf, rewrites)
    patched_libcore = patch_libcore(libcore) if args.patch_libcore else None
    if replaced < len(URL_REWRITES):
        raise SystemExit(f"esperava trocar ao menos {len(URL_REWRITES)} URLs no Pets.swf, troquei {replaced}")
    if patch_swf(patched, rewrites)[1] != 0:
        raise SystemExit("verificacao falhou: URLs originais ainda presentes no SWF gerado")
    print(f"[ok] Pets.swf: {replaced} URLs apontadas para http://{args.host}:{args.http_port}/")

    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    out = args.out or build / f"CurioQuest-offline-{args.host}.apk"
    unsigned, aligned = build / "tmp-unsigned.apk", build / "tmp-aligned.apk"
    rebuild_apk(args.apk, unsigned, patched, patched_libcore)
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

