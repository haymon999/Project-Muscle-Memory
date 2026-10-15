"""Apply the 10 native patches (P1-P10) to libil2cpp.so.

Usage:
    python apply_patches.py <path-to-libil2cpp.so>

Every patch is same-length (4 or 8 bytes). Original bytes are verified
before writing; any mismatch aborts with no changes written.
RVA == file offset for this exact binary (verified).

See docs/PATCHES.md for what each patch does and why.
"""
import sys

# (offset, original_hex, patched_hex, description)
PATCHES = [
    (0xE29F00, "68020034", "85000014",
     "P1 boot gate: cbz -> b success tail (skip verdict telemetry)"),
    (0xD42F8C, "fd7bbfa9", "c0035fd6",
     "P2 AdManager.OnApplicationStarted -> ret"),
    (0xAEE7C4, "fd7bbfa9", "c0035fd6",
     "P3 PlayerDataManager.OnApplicationStarted -> ret"),
    (0xDEADEC, "f70f1cf8f65701a9", "001040f9c0035fd6",
     "P4 BackendManager.GetSessionToken -> return m_deviceSessionToken"),
    (0xE087E8, "881640b9", "28008052",
     "P5 LoginManager.ProcessLogin: force Guest (mov w8,#1)"),
    (0x9F4264, "f44fbea9", "c0035fd6",
     "P6 verdict poller ef34bnq8q2jd -> ret"),
    (0xCD7D38, "f50f1df8f44f01a9", "00008052c0035fd6",
     "P7 CheckErrors.MoveNext -> mov w0,#0; ret"),
    # P8: 19 short verdict checks (write-free, capstone-verified) -> ret
    *[(a, "f44fbea9", "c0035fd6", f"P8 verdict check {hex(a)} -> ret")
      for a in (0x9F4BE4, 0x9F4CE4, 0x9F4DE4, 0x9F4EE4, 0x9F4FE4,
                0x9F50E4, 0x9F51E4, 0x9F52E4, 0x9F53E4, 0x9F54E4,
                0x9F55E4, 0x9F56E4, 0x9F58E4, 0x9F59E4, 0x9F5AE4,
                0x9F5BE4, 0x9F5CE4, 0x9F5DE4, 0x9F5EE4)],
    (0x9F57E4, "f44fbea9", "c0035fd6",
     "P9 roaqw0cz8dj (from AppManager.ChangeStateAsync) -> ret"),
    (0x1206EF0, "ff8303d1", "c0035fd6",
     "P10 NetworkPeer.Connect -> ret (kill ENet dial attempts)"),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    data = bytearray(open(path, "rb").read())
    for off, orig, new, desc in PATCHES:
        cur = data[off:off + len(bytes.fromhex(orig))].hex()
        if cur == new.lower():
            print(f"SKIP (already applied) {hex(off)} {desc}")
            continue
        if cur != orig.lower():
            print(f"ABORT at {hex(off)}: expected {orig}, found {cur}")
            print(f"  ({desc})")
            print("  Wrong binary revision? Nothing was written.")
            sys.exit(1)
    for off, orig, new, desc in PATCHES:
        data[off:off + len(bytes.fromhex(orig))] = bytes.fromhex(new)
        print(f"OK {hex(off)} {desc}")
    open(path, "wb").write(data)
    print(f"Wrote {len(PATCHES)} patches to {path}")


if __name__ == "__main__":
    main()
