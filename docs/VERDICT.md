# VERDICT.md — the protection/SDK verdict system

## 1. The verdict

An obfuscation/protection SDK verdict lives in static fields:
`r818ck0epp.tgl40htn` (string +0x0) and `r818ck0epp.irxbayllqp1275pp` (uint +0x18).
On this emulator they hold code **83** + `"Error_0xA38B:"`, set once by the
`.cctor` of `qi4t0ty88k` (0xBFDC3C) via shared struct helper **0x1B7EE64**
(212 callers — the helper itself is not worth reversing; treat the verdict as
"environment failed integrity", almost certainly emulator detection).

The boot gate `b1df84um1p6bw5d` formats it as `"1-{0}-{1}"` → `1-83-Error_0xA38B:`
and reports via telemetry `Create(0x1F, msg)`; on success path it checks 8
SDK singletons and sets `*out=1` + static `uq4syc8r10xtscy6.n0yumwktt1tb28k`.
Upstream, `0xB58AE4 call b1df` + `0xB58AEC cbz→0xB58D40` short-circuits
`ApplicationStart` (proxy never sees the main API). P1 removes this gate.

## 2. Enforcers (all in class `efor15x.tav3uy2i1u3mrbeb5`)

Each reads a statics chain ending in an int tested as `(v|4)==4` (clean iff 0)
else throws `Error_0xA38B:`. All are side-effect-free EXCEPT group (c):

- (a) `ef34bnq8q2jd` (0x9F4264) — per-frame from `AppManager.Update`. PATCHED (P6).
- (b) `CheckErrors.MoveNext` (0xCD7D38) — coroutine; entry forced to
  `mov w0,#0; ret` (P7). NOTE: plain `ret` is wrong here (must return bool).
- (c) 8 LONG methods (0x9F4364–0x9F4AD4) — **write a caller verdict flag**
  (`strb [x19],0/1`). DO NOT ret-patch: boot hangs at 0% pre-ping (bisected).
  If one throws post-login, NOP only its throw branch.
- (d) 20 SHORT methods (0x9F4BE4–0x9F5EE4, incl. `rowaqw0cz8dj` 0x9F57E4 and
  `n0b5384pb2ap` 0x9F58E4) — pure checks, all ret-patched (P8/P9). They fire
  one-by-one as new app states are entered (`AppManager.ChangeStateAsync`
  calls them), so batch-patching after classifying via capstone (no stores
  except prologue + class-init flags) beats whack-a-mole.

How to classify a new suspect: disassemble; safe iff body = prologue +
class-inits + static-chain reads + conditional throw, with no `str` outside
spills/flags. The throw sites all funnel to `bl 0x97B4D0`-family helpers.

## 3. Why data-fixes can't satisfy it

The verdict is computed client-side by the SDK (not by our mock), and the
statics stay polluted for the process lifetime. Zeroing them at the `.cctor`
was considered but the per-frame readers may re-derive; killing the readers
(P6–P9) is robust and sufficient. No server traffic depends on the verdict
(telemetry carries only our stub events).

## 4. Related singletons

The success tail of the boot gate checks 8 protection-SDK singletons
(0xE2A114–0xE2A140, skipped by P1). `GetLoginToken` (0xDF64AC, backend header
builder input) also routes through the obfuscated struct helpers (0xF335E8 /
0x1B7EE64 / 0xF33674) — P4 sidesteps it by returning the device session token
directly. If future endpoints need real attestation-shaped tokens, revisit.
