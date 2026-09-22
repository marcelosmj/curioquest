#!/usr/bin/env python3
"""Extract protocol specs from the decompiled Curio Quest client (JPEXS AS3 export).

Produces, in <out_dir>:
  thrift_spec.json  - every ElectroServer 5 Thrift struct (field id, name, type,
                      nested metadata) and enum, read straight from Thrift*.as
  es_constants.json - es.EsConstants: symbolic EsObject key -> wire key

Usage: python tools/extract_client_specs.py reverse/client_as3 server/es5
"""
import ast
import json
import re
import sys
from pathlib import Path


def _meta_to_python(expr):
    """Turn an AS3 FieldMetaData constructor chain into nested tuples."""
    s = expr
    s = re.sub(r'new FieldValueMetaData\(\s*TType\.(\w+)\s*\)', r'("val","\1")', s)
    s = re.sub(r'new StructMetaData\(\s*TType\.STRUCT\s*,\s*(\w+)\s*\)', r'("struct","\1")', s)
    s = re.sub(r'new ListMetaData\(\s*TType\.LIST\s*,', '("list",', s)
    s = re.sub(r'new SetMetaData\(\s*TType\.SET\s*,', '("set",', s)
    s = re.sub(r'new MapMetaData\(\s*TType\.MAP\s*,', '("map",', s)
    s = re.sub(r'new FieldMetaData\(', '("field",', s)
    s = re.sub(r'TFieldRequirementType\.(\w+)', r'"\1"', s)
    return ast.literal_eval(s)


def parse_struct(text):
    name = re.search(r'new TStruct\("(\w+)"\)', text).group(1)
    tfields = {
        m.group(1): (int(m.group(3)), m.group(2))
        for m in re.finditer(r'new TField\("(\w+)"\s*,\s*TType\.(\w+)\s*,\s*(-?\d+)\s*\)', text)
    }
    metas = {}
    for m in re.finditer(r'metaDataMap\[\w+\] = (new FieldMetaData\(.*\));', text):
        meta = _meta_to_python(m.group(1))
        metas[meta[1]] = (meta[2], meta[3])
    enum_fields = {m.group(2): m.group(1)
                   for m in re.finditer(r'(\w+)\.VALID_VALUES\.contains\(this\.(\w+)\)', text)}
    binary_fields = set(re.findall(r'this\.(\w+) = param1\.readBinary\(\)', text))

    fields = []
    for fname, (fid, ttype) in sorted(tfields.items(), key=lambda kv: kv[1][0]):
        required, meta = metas.get(fname, (None, None))
        entry = {"id": fid, "name": fname, "type": ttype, "required": required, "meta": meta}
        if fname in enum_fields:
            entry["enum"] = enum_fields[fname]
        if fname in binary_fields:
            entry["binary"] = True
        fields.append(entry)
    missing = set(metas) - set(tfields)
    if missing:
        print(f"  aviso: {name} tem metadata sem TField: {sorted(missing)}")
    return name, fields


def parse_enum(text):
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r'public static const (\w+):int = (-?\d+);', text)}


def parse_constants(text):
    consts = {}
    for name, typ, value in re.findall(r'public static const (\w+):(\w+) = (.+?);', text):
        value = value.strip()
        if typ == "String" and value.startswith('"'):
            value = json.loads(value)
        else:
            try:
                value = int(value)
            except ValueError:
                pass
        consts[name] = value
    return consts


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    spec = {"structs": {}, "enums": {}}
    for f in sorted((src / "com/electrotank/electroserver5/thrift").glob("Thrift*.as")):
        text = f.read_text(encoding="utf-8")
        if "new TStruct(" in text:
            name, fields = parse_struct(text)
            spec["structs"][name] = fields
        elif "VALUES_TO_NAMES" in text:
            spec["enums"][f.stem] = parse_enum(text)
        else:
            print("  ignorado:", f.name)
    (out / "thrift_spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    print(f"thrift_spec.json: {len(spec['structs'])} structs, {len(spec['enums'])} enums")

    consts = parse_constants((src / "es/EsConstants.as").read_text(encoding="utf-8"))
    (out / "es_constants.json").write_text(json.dumps(consts, indent=1), encoding="utf-8")
    print(f"es_constants.json: {len(consts)} constantes")


if __name__ == "__main__":
    main()
