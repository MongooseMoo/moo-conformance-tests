# ANSI, match, conversion, and embedded JSON conformance

**Goal** Cover eleven Barn behavior discrepancies found through public MOO builtins.

**State** The managed selection ran the eleven new cases and capability admission. Stock ToastStunt reported `12 passed`. Baseline Barn reported `11 failed, 1 passed`, with capability admission passing.

**Decisions and why** Compare random ANSI output to the reachable foreground palette without requiring any particular draw. The matching cases use positive and negative inputs and preserve empty match results in failure output. The newline case requires wizard permissions for `chr(10)`. The embedded boolean case checks both the type and value.

**Surprises** Baseline Barn returned an empty list for the positive backreference and newline-anchor inputs. Its misplaced-caret result was also an empty list, where the expected outcome is E_INVARG.

**Next step** Verify with the corresponding Barn fix before merging these cases.
