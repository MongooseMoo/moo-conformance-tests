# Expression codes, catch defaults, splice assignment

## Goal
Pin grammar ToastStunt accepts that Barn rejected: 14 live mongoose.db verbs
failed to compile on Barn (found compiling PR 567's local verb corpus).
Q chose "Fix Toast-first" 2026-11-02.

## State
`language/expression_codes_and_defaults.yaml`, 7 cases. Stock WSL Toast
oracle (`make conformance-toast K=expression_codes_and_defaults` from Barn):
8 passed including admission. Barn master: all 7 fail.

## Decisions and why
- Grammar source: parser.y `codes: tANY | ne_arglist` (line 667) and
  `default: tARROW expr` (line 674).
- `x = true = {}` is wrapped in eval() because I did not know Toast's answer;
  Toast returns {1, {}}: `true` is an ordinary variable name there.

## Next step
Merge only after the Barn parser fix merges; Barn CI runs this repo's main.
