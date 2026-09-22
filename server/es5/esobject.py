"""ElectroServer 5 EsObject: an ordered, typed key/value tree, plus its binary codec.

Port of the client's EsObjectCodec, MessageWriter and MessageReader. Every value keeps
its exact wire type: the client reads each key with a typed getter (getInteger,
getNumber, ...) and breaks on a missing key or a value of another type.
"""
import struct

# type indicator characters, from EsObjectCodec.initializeMaps()
INTEGER = "0"
STRING = "1"
DOUBLE = "2"
FLOAT = "3"
BOOLEAN = "4"
BYTE = "5"
CHAR = "6"
LONG = "7"
SHORT = "8"
ESOBJECT = "9"
ESOBJECT_ARRAY = "a"
INTEGER_ARRAY = "b"
STRING_ARRAY = "c"
DOUBLE_ARRAY = "d"
FLOAT_ARRAY = "e"
BOOLEAN_ARRAY = "f"
BYTE_ARRAY = "g"
CHAR_ARRAY = "h"
LONG_ARRAY = "i"
SHORT_ARRAY = "j"
NUMBER = "k"
NUMBER_ARRAY = "l"

TYPE_NAMES = {
    INTEGER: "Integer", STRING: "String", DOUBLE: "Double", FLOAT: "Float", BOOLEAN: "Boolean",
    BYTE: "Byte", CHAR: "Char", LONG: "Long", SHORT: "Short", ESOBJECT: "EsObject",
    ESOBJECT_ARRAY: "EsObjectArray", INTEGER_ARRAY: "IntegerArray", STRING_ARRAY: "StringArray",
    DOUBLE_ARRAY: "DoubleArray", FLOAT_ARRAY: "FloatArray", BOOLEAN_ARRAY: "BooleanArray",
    BYTE_ARRAY: "ByteArray", CHAR_ARRAY: "CharArray", LONG_ARRAY: "LongArray",
    SHORT_ARRAY: "ShortArray", NUMBER: "Number", NUMBER_ARRAY: "NumberArray",
}

_SCALAR_FORMATS = {INTEGER: ">i", DOUBLE: ">d", NUMBER: ">d", FLOAT: ">f", BYTE: ">b", LONG: ">q", SHORT: ">h"}
_ARRAY_FORMATS = {INTEGER_ARRAY: ">i", DOUBLE_ARRAY: ">d", NUMBER_ARRAY: ">d", FLOAT_ARRAY: ">f",
                  LONG_ARRAY: ">q", SHORT_ARRAY: ">h"}


class EsObject:
    __slots__ = ("_entries",)

    def __init__(self):
        self._entries = {}

    def _set(self, name, typ, value):
        self._entries[name] = (typ, value)
        return self

    def set_integer(self, name, value): return self._set(name, INTEGER, int(value))
    def set_string(self, name, value): return self._set(name, STRING, str(value))
    def set_double(self, name, value): return self._set(name, DOUBLE, float(value))
    def set_float(self, name, value): return self._set(name, FLOAT, float(value))
    def set_boolean(self, name, value): return self._set(name, BOOLEAN, bool(value))
    def set_byte(self, name, value): return self._set(name, BYTE, int(value))
    def set_char(self, name, value): return self._set(name, CHAR, str(value)[:1])
    def set_long(self, name, value): return self._set(name, LONG, int(value))
    def set_short(self, name, value): return self._set(name, SHORT, int(value))
    def set_number(self, name, value): return self._set(name, NUMBER, float(value))
    def set_esobject(self, name, value): return self._set(name, ESOBJECT, value)
    def set_esobject_array(self, name, values): return self._set(name, ESOBJECT_ARRAY, list(values))
    def set_integer_array(self, name, values): return self._set(name, INTEGER_ARRAY, [int(v) for v in values])
    def set_string_array(self, name, values): return self._set(name, STRING_ARRAY, [str(v) for v in values])
    def set_double_array(self, name, values): return self._set(name, DOUBLE_ARRAY, [float(v) for v in values])
    def set_float_array(self, name, values): return self._set(name, FLOAT_ARRAY, [float(v) for v in values])
    def set_boolean_array(self, name, values): return self._set(name, BOOLEAN_ARRAY, [bool(v) for v in values])
    def set_byte_array(self, name, value): return self._set(name, BYTE_ARRAY, bytes(value))
    def set_char_array(self, name, values): return self._set(name, CHAR_ARRAY, [str(v)[:1] for v in values])
    def set_long_array(self, name, values): return self._set(name, LONG_ARRAY, [int(v) for v in values])
    def set_short_array(self, name, values): return self._set(name, SHORT_ARRAY, [int(v) for v in values])
    def set_number_array(self, name, values): return self._set(name, NUMBER_ARRAY, [float(v) for v in values])

    def has(self, name):
        return name in self._entries

    def get(self, name, default=None):
        entry = self._entries.get(name)
        return default if entry is None else entry[1]

    def get_type(self, name):
        entry = self._entries.get(name)
        return None if entry is None else entry[0]

    def remove(self, name):
        self._entries.pop(name, None)

    def keys(self):
        return list(self._entries)

    def __contains__(self, name):
        return name in self._entries

    def __len__(self):
        return len(self._entries)

    def to_debug(self, names=None):
        """Nested dict for logs; `names` maps wire keys ('dal0') to client names ('DALC_ID')."""
        out = {}
        for key, (typ, value) in self._entries.items():
            label = f"{names.get(key, key) if names else key}:{TYPE_NAMES[typ]}"
            if typ == ESOBJECT:
                value = value.to_debug(names)
            elif typ == ESOBJECT_ARRAY:
                value = [item.to_debug(names) for item in value]
            elif typ == BYTE_ARRAY:
                value = f"<{len(value)} bytes>"
            out[label] = value
        return out

    def __repr__(self):
        return f"EsObject({self.to_debug()!r})"


# -- encoding ------------------------------------------------------------------------------

def write_length(out, n):
    """MessageWriter.writeLength: 1-4 bytes, top two bits of the first byte = extra bytes."""
    if n < 0 or n & 0x40000000:
        raise ValueError(f"comprimento invalido para EsObject: {n}")
    size = 1 if n <= 63 else 2 if n <= 16383 else 3 if n <= 4194303 else 4
    for i in range(size - 1, -1, -1):
        byte = (n >> (i * 8)) & 0xFF
        if i == size - 1:
            byte |= (size - 1) << 6
        out.append(byte)


def _write_string(out, text):
    raw = text.encode("utf-8")
    write_length(out, len(raw))
    out += raw


def _encode_into(out, eso):
    out.append(0)
    write_length(out, len(eso._entries))
    for name, (typ, value) in eso._entries.items():
        out += typ.encode("ascii")
        _write_string(out, name)
        _write_value(out, typ, value)


def _write_value(out, typ, value):
    fmt = _SCALAR_FORMATS.get(typ)
    if fmt:
        out += struct.pack(fmt, value)
    elif typ == STRING:
        _write_string(out, value)
    elif typ == BOOLEAN:
        out.append(1 if value else 0)
    elif typ == CHAR:
        out.append(0)
        out += value.encode("utf-8")[:1]
    elif typ == ESOBJECT:
        _encode_into(out, value)
    elif typ == ESOBJECT_ARRAY:
        write_length(out, len(value))
        for item in value:
            _encode_into(out, item)
    elif typ in _ARRAY_FORMATS:
        write_length(out, len(value))
        item_fmt = _ARRAY_FORMATS[typ]
        for item in value:
            out += struct.pack(item_fmt, item)
    elif typ == STRING_ARRAY:
        write_length(out, len(value))
        for item in value:
            _write_string(out, item)
    elif typ == BOOLEAN_ARRAY:
        write_length(out, len(value))
        out += bytes(1 if item else 0 for item in value)
    elif typ == BYTE_ARRAY:
        write_length(out, len(value))
        out += value
    elif typ == CHAR_ARRAY:
        write_length(out, len(value))
        for item in value:
            out.append(0)
            out += item.encode("utf-8")[:1]
    else:
        raise ValueError(f"tipo de EsObject desconhecido: {typ!r}")


def encode(eso):
    out = bytearray()
    _encode_into(out, eso)
    return bytes(out)


# -- decoding ------------------------------------------------------------------------------

class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf):
        self.buf = bytes(buf)
        self.pos = 0

    def take(self, n):
        end = self.pos + n
        if end > len(self.buf):
            raise ValueError(f"EsObject truncado na posicao {self.pos}")
        chunk = self.buf[self.pos:end]
        self.pos = end
        return chunk

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))[0]

    def length(self):
        first = self.take(1)[0]
        value = first & 0x3F
        for _ in range((first >> 6) & 3):
            value = (value << 8) | self.take(1)[0]
        return value

    def string(self):
        return self.take(self.length()).decode("utf-8")


def _decode_from(r):
    r.take(1)
    eso = EsObject()
    for _ in range(r.length()):
        typ = r.take(1).decode("ascii")
        name = r.string()
        eso._entries[name] = (typ, _read_value(r, typ))
    return eso


def _read_value(r, typ):
    fmt = _SCALAR_FORMATS.get(typ)
    if fmt:
        return r.unpack(fmt)
    if typ == STRING:
        return r.string()
    if typ == BOOLEAN:
        return r.take(1)[0] != 0
    if typ == CHAR:
        r.take(1)
        return r.take(1).decode("utf-8", "replace")
    if typ == ESOBJECT:
        return _decode_from(r)
    if typ == ESOBJECT_ARRAY:
        return [_decode_from(r) for _ in range(r.length())]
    if typ in _ARRAY_FORMATS:
        item_fmt = _ARRAY_FORMATS[typ]
        return [r.unpack(item_fmt) for _ in range(r.length())]
    if typ == STRING_ARRAY:
        return [r.string() for _ in range(r.length())]
    if typ == BOOLEAN_ARRAY:
        return [b != 0 for b in r.take(r.length())]
    if typ == BYTE_ARRAY:
        return r.take(r.length())
    if typ == CHAR_ARRAY:
        items = []
        for _ in range(r.length()):
            r.take(1)
            items.append(r.take(1).decode("utf-8", "replace"))
        return items
    raise ValueError(f"tipo de EsObject desconhecido: {typ!r}")


def decode(data):
    return _decode_from(_Reader(data))
