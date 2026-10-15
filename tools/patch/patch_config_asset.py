import zipfile, os, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APK = os.path.join(ROOT, "critical-ops-1-32-0-f1831.apk")
OUT = os.path.join(ROOT, "patch_out")
os.makedirs(OUT, exist_ok=True)

# 10.0.2.2 = Android emulator loopback-to-host alias (LDPlayer + MuMu).
# Reachable via NAT without LAN/firewall/VPN dependence, unlike a 192.168.x IP.
# Length-preserving: build() pads the freed bytes with extra junk chars.
PREFIX = sys.argv[1].encode() if len(sys.argv) > 1 else b"http://10.0.2.2:8080/"

def build(orig, char, suffix):
    room = len(orig) - len(PREFIX) - len(suffix)
    assert room >= 0, (orig, len(orig), len(PREFIX), len(suffix))
    return PREFIX + char * room + suffix

PAIRS = [
    (b"https://1-32-0.prod.copsapi.criticalforce.fi/api", build(b"https://1-32-0.prod.copsapi.criticalforce.fi/api", b"a", b"/api")),
    (b"https://api-cops.criticalforce.fi/api",            build(b"https://api-cops.criticalforce.fi/api", b"b", b"/api")),
    (b"https://api-prod.prod.an.cf.fi/v1_4_8",            build(b"https://api-prod.prod.an.cf.fi/v1_4_8", b"c", b"/v148")),
    (b"https://99-99-9.test-dev-1.dev.copsapi.criticalforce.fi/api", build(b"https://99-99-9.test-dev-1.dev.copsapi.criticalforce.fi/api", b"a", b"/api")),
    (b"https://1-21-0.stage.copsapi.criticalforce.fi/api", build(b"https://1-21-0.stage.copsapi.criticalforce.fi/api", b"a", b"/api")),
    (b"https://1-15-0.prod.copsapi.criticalforce.fi/api", build(b"https://1-15-0.prod.copsapi.criticalforce.fi/api", b"a", b"/api")),
    (b"https://api-analytics.criticalforce.fi/api",       build(b"https://api-analytics.criticalforce.fi/api", b"c", b"/api")),
]
for o, r in PAIRS:
    assert len(o) == len(r), (o, r, len(o), len(r))
    print("MAP:", o.decode(), "->", r.decode(), f"({len(o)}b)")

z = zipfile.ZipFile(APK)
swaps = {}
total = 0
for info in z.infolist():
    if not info.filename.startswith("assets/bin/Data/"):
        continue
    d = z.read(info.filename)
    if b"criticalforce.fi" not in d:
        continue
    nd = d
    hits = []
    for o, r in PAIRS:
        n = nd.count(o)
        if n:
            hits.append((o.decode(), n))
            nd = nd.replace(o, r)
    if nd != d:
        outp = os.path.join(OUT, os.path.basename(info.filename))
        open(outp, "wb").write(nd)
        swaps[info.filename] = outp
        total += 1
        print(f"PATCHED {info.filename} hits={hits} -> {outp}")

json.dump(swaps, open(os.path.join(OUT, "swap.json"), "w"), indent=1)
print("files patched:", total)
print("SWAP_JSON:", json.dumps(swaps, indent=1))
