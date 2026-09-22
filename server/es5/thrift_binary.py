"""Apache Thrift TBinaryProtocol at struct level, as spoken by ElectroServer 5.

Field ids and types come from thrift_spec.json (generated from the client by
tools/extract_client_specs.py), so what we write is exactly what the client reads.
Structs are plain dicts keyed by field name; LIST<BYTE> fields are Python bytes.
"""
import json
import struct
from pathlib import Path

STOP, BOOL, BYTE, DOUBLE, I16, I32, I64, STRING, STRUCT, MAP, SET, LIST = 0, 2, 3, 4, 6, 8, 10, 11, 12, 13, 14, 15

TYPE_CODES = {
    "BOOL": BOOL, "BYTE": BYTE, "DOUBLE": DOUBLE, "I16": I16, "I32": I32, "I64": I64,
    "STRING": STRING, "STRUCT": STRUCT, "MAP": MAP, "SET": SET, "LIST": LIST,
}
_CONTAINER_TYPES = {"struct": STRUCT, "list": LIST, "set": SET, "map": MAP}


class ThriftError(Exception):
    pass


def _meta_type(meta):
    if meta[0] == "val":
        return TYPE_CODES[meta[1]]
    return _CONTAINER_TYPES[meta[0]]


class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf):
        self.buf = memoryview(buf)
        self.pos = 0

    def take(self, n):
        end = self.pos + n
        if n < 0 or end > len(self.buf):
            raise ThriftError(f"dados truncados: faltam bytes ({n}) na posicao {self.pos}")
        chunk = self.buf[self.pos:end]
        self.pos = end
        return chunk

    def unpack(self, fmt, size):
        return struct.unpack(fmt, self.take(size))[0]


class ThriftCodec:
    def __init__(self, spec_path):
        data = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        self.enums = data["enums"]
        self.structs = {}
        for name, fields in data["structs"].items():
            self.structs[name] = {
                "by_id": {f["id"]: f for f in fields},
                "by_name": {f["name"]: f for f in fields},
                "ordered": sorted(fields, key=lambda f: f["id"]),
            }

    def fields(self, struct_name):
        return set(self.structs[struct_name]["by_name"])

    def decode(self, struct_name, data):
        return self._read_struct(_Reader(data), struct_name)

    def encode(self, struct_name, values):
        out = bytearray()
        self._write_struct(out, struct_name, values)
        return bytes(out)

    # -- reading ---------------------------------------------------------------------------

    def _read_struct(self, r, struct_name):
        spec = self.structs.get(struct_name) if struct_name else None
        result = {}
        while True:
            ftype = r.unpack(">b", 1)
            if ftype == STOP:
                return result
            fid = r.unpack(">h", 2)
            field = spec["by_id"].get(fid) if spec else None
            if field is not None and TYPE_CODES[field["type"]] == ftype:
                result[field["name"]] = self._read_value(r, ftype, field["meta"])
            else:
                self._read_value(r, ftype, None)

    def _read_value(self, r, ftype, meta):
        if ftype == BOOL:
            return r.unpack(">b", 1) == 1
        if ftype == BYTE:
            return r.unpack(">b", 1)
        if ftype == I16:
            return r.unpack(">h", 2)
        if ftype == I32:
            return r.unpack(">i", 4)
        if ftype == I64:
            return r.unpack(">q", 8)
        if ftype == DOUBLE:
            return r.unpack(">d", 8)
        if ftype == STRING:
            raw = bytes(r.take(r.unpack(">i", 4)))
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw
        if ftype == STRUCT:
            return self._read_struct(r, meta[1] if meta else None)
        if ftype in (LIST, SET):
            etype = r.unpack(">b", 1)
            count = r.unpack(">i", 4)
            if etype == BYTE:
                return bytes(r.take(count))
            emeta = meta[1] if meta else None
            return [self._read_value(r, etype, emeta) for _ in range(count)]
        if ftype == MAP:
            ktype = r.unpack(">b", 1)
            vtype = r.unpack(">b", 1)
            count = r.unpack(">i", 4)
            kmeta, vmeta = (meta[1], meta[2]) if meta else (None, None)
            return {self._read_value(r, ktype, kmeta): self._read_value(r, vtype, vmeta) for _ in range(count)}
        raise ThriftError(f"tipo thrift nao suportado: {ftype}")

    # -- writing ---------------------------------------------------------------------------

    def _write_struct(self, out, struct_name, values):
        spec = self.structs[struct_name]
        unknown = set(values) - set(spec["by_name"])
        if unknown:
            raise ThriftError(f"{struct_name} nao tem os campos {sorted(unknown)}")
        for field in spec["ordered"]:
            value = values.get(field["name"])
            if value is None:
                continue
            ftype = TYPE_CODES[field["type"]]
            out += struct.pack(">bh", ftype, field["id"])
            self._write_value(out, ftype, field["meta"], value)
        out.append(STOP)

    def _write_value(self, out, ftype, meta, value):
        if ftype == BOOL:
            out.append(1 if value else 0)
        elif ftype == BYTE:
            out += struct.pack(">b", value)
        elif ftype == I16:
            out += struct.pack(">h", value)
        elif ftype == I32:
            out += struct.pack(">i", value)
        elif ftype == I64:
            out += struct.pack(">q", value)
        elif ftype == DOUBLE:
            out += struct.pack(">d", value)
        elif ftype == STRING:
            raw = bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else str(value).encode("utf-8")
            out += struct.pack(">i", len(raw))
            out += raw
        elif ftype == STRUCT:
            self._write_struct(out, meta[1], value)
        elif ftype in (LIST, SET):
            emeta = meta[1]
            etype = _meta_type(emeta)
            out += struct.pack(">bi", etype, len(value))
            if etype == BYTE and isinstance(value, (bytes, bytearray, memoryview)):
                out += bytes(value)
            else:
                for item in value:
                    self._write_value(out, etype, emeta, item)
        elif ftype == MAP:
            kmeta, vmeta = meta[1], meta[2]
            ktype, vtype = _meta_type(kmeta), _meta_type(vmeta)
            out += struct.pack(">bbi", ktype, vtype, len(value))
            for key, item in value.items():
                self._write_value(out, ktype, kmeta, key)
                self._write_value(out, vtype, vmeta, item)
        else:
            raise ThriftError(f"tipo thrift nao suportado: {ftype}")
