# crypt one-character salt test: remove the 1-in-4096 flake

## Goal
`audit/divergence_builtin_edges.yaml::crypt_one_char_salt_randomizes_salt`
failed in Barn's merge queue (barn PR #826, CI run 43570030130): "expected
value 0, but got 1". Make the test stop failing by chance without weakening
what it pins.

## State
- Cause: the test compared two `crypt("foo", "x")` calls. Toast picks each of
  the two salt characters uniformly from 64 (`src/crypto.cc` bf_crypt, lines
  325-326: `saltstuff[RANDOM() % strlen(saltstuff)]`), so two calls agree once
  in 4096 on Toast as well as on Barn (`builtins/crypto.go` cryptDES).
- Change: eight calls; the test passes when they are not all equal. All eight
  agree with probability 4096^-7. The property pinned is unchanged: a salt
  shorter than two characters is replaced by a fresh random one.
- Managed stock WSL Toast oracle, `K=crypt_one_char_salt_randomizes_salt`:
  2 passed (admission and this test).

## Next step
Merge; Barn's queue then runs the new form.
