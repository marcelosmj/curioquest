#!/usr/bin/env python3
"""Walk the game's startup path against the offline server, the way the client does:
HTTP (Servers.xml, Version.xml, Server.xml), ElectroServer connection, login with the
Books, then CharacterDALC.LOGIN_PLATFORM.

Usage (with the server running):  python tools/es5_test_client.py [--host 127.0.0.1]
"""
import argparse
import re
import socket
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.es5 import esobject, protocol  # noqa: E402
from server.es5.thrift_binary import ThriftCodec  # noqa: E402
from server.game.keys import K, NAMES  # noqa: E402

PLATFORM_ANDROID = 1
CHARACTER_DALC = 2
LOGIN_PLATFORM = 1


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("o servidor fechou a conexao")
        data += chunk
    return bytes(data)


def read_message(sock, codec):
    (length,) = struct.unpack(">i", recv_exact(sock, 4))
    indicator, _number, data = protocol.parse_body(recv_exact(sock, length))
    return protocol.MESSAGE_TYPES[indicator][0], codec.decode(protocol.thrift_struct(indicator), data)


def send_message(sock, codec, name, **fields):
    indicator = protocol.INDICATORS[name]
    sock.sendall(protocol.build_frame(indicator, 0, codec.encode(protocol.thrift_struct(indicator), fields)))


def check_codec_roundtrip():
    eso = esobject.EsObject()
    eso.set_integer("i", -5).set_string("s", "Olá").set_boolean("b", True).set_number("n", 1.5)
    eso.set_long("l", -2 ** 40).set_short("h", -3).set_byte("y", -1).set_float("f", 0.5).set_char("c", "x")
    eso.set_integer_array("ia", [1, 2, 3]).set_string_array("sa", ["a", "b"]).set_boolean_array("ba", [True, False])
    eso.set_byte_array("ga", bytes(range(200))).set_number_array("na", [1.0, 2.0])
    eso.set_esobject("o", esobject.EsObject().set_string("x", "y" * 70))
    eso.set_esobject_array("oa", [esobject.EsObject().set_integer("k", i) for i in range(70)])
    assert esobject.decode(esobject.encode(eso)).to_debug() == eso.to_debug(), "ida e volta do EsObject falhou"
    for n in (0, 63, 64, 16383, 16384, 4194303, 4194304):
        out = bytearray()
        esobject.write_length(out, n)
        assert esobject._Reader(out).length() == n, f"writeLength({n}) falhou"
    print("[ok] codec EsObject (ida e volta, comprimentos de 1 a 4 bytes)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--device-id", default="cliente-de-teste")
    args = parser.parse_args()

    check_codec_roundtrip()
    codec = ThriftCodec(ROOT / "server" / "es5" / "thrift_spec.json")

    base = f"http://{args.host}:{args.http_port}/pets_live/"
    bodies = {}
    for name in ("Servers.xml", "Version.xml", "Server.xml", "LandingScreen.xml"):
        with urllib.request.urlopen(base + name + "?v=1234", timeout=5) as resp:
            bodies[name] = resp.read().decode("utf-8")
        print(f"[ok] HTTP {name}: {' '.join(bodies[name].split())[:100]}")
    es_host, es_port = re.search(r'host="([^"]+)" port="(\d+)"', bodies["Server.xml"]).groups()

    sock = socket.create_connection((es_host, int(es_port)), timeout=10)
    skipped = 0
    while recv_exact(sock, 1) != b"\x00":
        skipped += 1
    name, msg = read_message(sock, codec)
    assert name == "ConnectionResponse" and msg.get("successful"), (name, msg)
    print(f"[ok] conexao ES ({skipped} bytes antes do terminador) -> {name} {msg}")

    platform = esobject.EsObject().set_integer(K.USER_PLATFORM, PLATFORM_ANDROID)
    send_message(sock, codec, "LoginRequest", userName="Login", clientVersion="5.3.3", clientType="AS3",
                 userVariables={K.USER_PLATFORM: {"encodedEntries": esobject.encode(platform)}})
    name, msg = read_message(sock, codec)
    assert name == "LoginResponse" and msg.get("successful"), (name, msg)
    login = esobject.decode(msg["esObject"]["encodedEntries"])
    books = login.get(K.XMLS, [])
    xml_bytes = sum(len(zlib.decompress(book.get(K.XML_DATA))) for book in books)
    print(f"[ok] {name}: usuario={msg.get('userName')!r} hora={login.get(K.SERVER_TIME)!r} "
          f"Books={len(books)} ({xml_bytes} bytes de XML)")

    request = (esobject.EsObject()
               .set_integer(K.ACTION_TYPE, LOGIN_PLATFORM)
               .set_string(K.USER_ID, args.device_id)
               .set_string(K.USER_TOKEN, "")
               .set_integer(K.USER_PLATFORM, PLATFORM_ANDROID)
               .set_string(K.CHARACTER_REFER_ID, "")
               .set_string(K.CHARACTER_REREFER_ID, "")
               .set_integer(K.DALC_ID, CHARACTER_DALC))
    send_message(sock, codec, "PluginRequest", pluginName="ServerPlugin",
                 parameters={"encodedEntries": esobject.encode(request)})
    sock.settimeout(5)
    try:
        name, msg = read_message(sock, codec)
    except socket.timeout:
        print("[--] sem resposta ao CharacterDALC.LOGIN_PLATFORM (ainda nao implementado)")
        return
    reply = esobject.decode(msg["parameters"]["encodedEntries"])
    print(f"[ok] {name} com {len(reply)} campos: {str(reply.to_debug(NAMES))[:700]}")


if __name__ == "__main__":
    main()
