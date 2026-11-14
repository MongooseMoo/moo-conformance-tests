# strings across source lines

## Goal
Assert eval rejection and valid neighboring syntax using bundled Test.db.

## State
Independent data branch from origin/main. Toast-green, Barn-master-red, and
fixed-Barn-green loop complete. No harness changes. Do not merge; Barn fix
must merge first. PR/CI pending.

## Decisions and why
Use full eval results to preserve the oracle diagnostics. Toast authority:
/root/src/toaststunt/src/parser.y:1032-1045,1314-1318.

## Surprises
Both rejected source-line cases returned [1, 'a\nb'] on unchanged Barn.

## Next step
Open data PR and watch CI. Merge remains forbidden. Required merge order:
https://github.com/MongooseMoo/barn/pull/622 first, then this data PR.

## Raw result summaries
All runs use managed WSL Debian servers, bundled Test.db and canonical
capability_admission. Selected YAML filename matches this branch's task.
Test.db SHA-256: 1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e.
Toast binary: /root/src/toaststunt/build-release/moo.
Executable SHA-256: 72fb1cf96cb303647a8ee72808e7c1ff62a491ecf44f547e6757e71ba2402bde.

```text
Toast: 4 passed in 11.07s
Barn master: 2 failed, 2 passed in 17.71s
Fixed Barn: 4 passed in 7.83s
```
