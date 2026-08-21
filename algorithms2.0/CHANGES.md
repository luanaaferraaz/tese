# algorithms2.0 — Changes from `algorithms copy/`

All ten algorithms are included. Six are byte-identical copies; four were modified.
Every modification is justified by a published reference. Cosmetic suggestions with
no scientific backing (e.g., normalizing section verbosity across files) were NOT applied.

## References

- [Bracha87] Bracha, G. (1987). "Asynchronous Byzantine Agreement Protocols".
  Information and Computation 75(2), pp. 130–143.
- [HT94] Hadzilacos, V. and Toueg, S. (1994). "A Modular Approach to Fault-Tolerant
  Broadcasts and Related Problems". TR94-1425, Cornell University.
- [CGR11] Cachin, C., Guerraoui, R. and Rodrigues, L. (2011). Introduction to
  Reliable and Secure Distributed Programming, 2nd ed., Springer.

## Unchanged files

- best-effort-broadcast.txt
- rb-crash-failure.txt
- fault-tolerant-rb-no-failure.txt
- reliable-broadcast-general-omission.txt
- termination-reliable-broadcast.txt
- termination-reliable-broadcast-general-omission.txt

## Modified files

### reliable-broadcast.txt

1. **Added `delivered = delivered ∪ {m}` before self-delivery in `rb_broadcast(m)`.**
   Without it, the broadcaster (which sends DATA to all q ∈ {1,…,n}, including itself)
   re-delivers m on receiving its own DATA — violating No duplication ("every correct
   process delivers m at most once", [HT94] §2; [CGR11] Module 3.2, and their
   "Lazy/Eager Reliable Broadcast" Algorithms 3.2/3.3, which add the message to
   `delivered` before the deliver upcall on every path).
2. **Fixed notation:** `m∈/delivered` → `m ∉ delivered`; `\cup \{m\}` → `∪ {m}`
   (LaTeX leftovers; presentation only, no protocol change).

### echo-broadcast.txt

1. **ECHO quorum `(n+f)/2` → `⌈(n+f+1)/2⌉`** in §6 and Rule 1. Bracha's protocol
   requires echoes from *more than* (n+f)/2 processes ([Bracha87] §3; [CGR11]
   Algorithm 3.16 "Authenticated Double-Echo Broadcast" uses `> (N+f)/2`). The
   non-strict `≥ (n+f)/2` is a weaker condition than the published one; the ceiling
   form makes the strict majority explicit for integer counts.
2. **Delivery rule now guarded by the `delivered` flag** (`… and delivered is false:
   delivered ← true; deliver(m)`). The variable was declared in §6 but never used in
   the pseudocode, so nothing prevented a second deliver(m) upcall on the next READY —
   violating No duplication ([HT94] §2; [CGR11] Alg. 3.16 checks `delivered = FALSE`
   before delivering).
3. **Agreement (§3) restated in the standard form** "if a correct process delivers m,
   then every correct process eventually delivers m" ([HT94] §2 Agreement; [CGR11]
   Module 3.12 Consistency + Totality). The original text stated only the
   consistency half; Bracha's protocol guarantees both, and the property file asks
   about "Agreement" in the [HT94] sense.
4. **Typo:** "Timingyes model" → "Timing model".

### byzantine-rb.txt

1. **`<type0, m>` is now accepted only from the designated broadcaster s**
   (new guard in the type0 handler, new validation rule, constant `s`, invariant I1b,
   updated Integrity argument). Without this check any Byzantine non-broadcaster
   could inject `<type0, m'>`, causing correct processes to echo and eventually
   deliver a message that was never broadcast — violating Integrity "only if m was
   previously broadcast by its sender" ([HT94] §2). Bracha's protocol accepts the
   initial SEND only from the designated sender s ([Bracha87] §3, step 1: "upon
   receiving (initial, v) from the transmitter"; [CGR11] Alg. 3.16: "upon receiving
   a message (SEND, m) from the sender s").
2. **Formatting:** blank line inserted between the two receive handlers
   (presentation only).

### new-byzantine-rb.txt

1. **Same sender-validation fix as byzantine-rb.txt**, same justification
   ([Bracha87] §3; [HT94] §2 Integrity; [CGR11] Alg. 3.16).
2. **Typo:** "LGORITHM TEMPLATE" → "ALGORITHM TEMPLATE".
3. **Formatting:** blank line inserted between the two receive handlers.

## Known remaining caveat (deliberately NOT changed)

`new-byzantine-rb.txt` delivers on f+1 = 2 `<type1, m>` messages instead of Bracha's
2f+1 READY threshold, and forwards on f+1. With the sender-validation fix, Integrity
no longer fails via injected type0 messages, and with the designated broadcaster
either correct (Validity path) or the f+1 intersection argument (Agreement path) the
stated properties hold for f = 1. Replacing the whole threshold structure with
Bracha's (n > 3f, echo + ready phases) would change the algorithm's identity, which
is not warranted for a file whose ground truth is "all properties satisfied" under
its own stated model (n ≥ 4, f = 1).
