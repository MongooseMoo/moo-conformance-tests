# toast-2.8-map-key-order

The rename descriptions below are historical. During integration in #217,
the existing case names were retained as durable inventory identities while
their descriptions and assertions were updated for Toast 2.8.

## Goal

Make the map key-order expectations match stock Toast after upstream
c0966e5 ("Order waifs, anonymous objects and bools in compare()") and
7afd3e9 ("Fix compare() truncating 64-bit integer and object map keys to
32 bits"). Barn's stock oracle moved to Toast 03af4fa, which has both.

## State

Done on branch `toast-2.8-map-key-order`; Toast-green and Barn-green for the
selection below. Not pushed (the orchestrator publishes).

## What changed and why

Toast `compare()` (src/utils.cc) now orders bools false < true, and waifs and
anonymous objects by pointer address; it used to return 1 for any two unequal
values of those types, which made map key order depend on insertion order.

- `language/map_authority.yaml`
  - `reverse_inserted_bool_key_maps_expose_reverse_topology` became
    `bool_map_keys_order_false_before_true_in_any_insertion_order`.
  - `reverse_inserted_{waif,anon}_key_maps_expose_reverse_topology` became
    `{waif,anon}_key_map_order_is_independent_of_insertion_order`. Address
    order is not reproducible (on Toast 03af4fa two `class:new()` waifs came
    out second-first, two anonymous objects first-first, and a restart
    reassigns addresses), so the tests assert the order is the same for both
    insertion orders and do not pin which key comes first.
  - New `full_width_{integer,object}_map_keys_order_numerically`: keys on
    both sides of 2^31 and 2^32 (7afd3e9; the old subtraction truncated to 32
    bits, which collided 1 and 4294967297).
- `language/boolean_authority.yaml`
  `boolean_and_equal_integer_mixed_map_reachability`: `maphaskey(values, true)`
  is now 1.
- `server/map_dump_persistence.yaml`
  `ordering_spelling_bytes_and_non_total_topology_round_trip` became
  `ordering_spelling_bytes_and_identity_key_topology_round_trip`: bool maps are
  false-first before and after restart; waif/anon key order is asserted
  insertion-independent, not pinned.

## Surprises

- `x in list` returns the index, so membership checks are written
  `(x in {...}) > 0`.
- `int_keys_separated_by_2_to_32_collide_and_replace` already describes keys
  that stay distinct; commit 83bd326 restored that name on purpose for stable
  case identity, so it was left alone.

## Evidence

From a Barn worktree, in WSL as root:

    make conformance-toast CONFORMANCE_SUITE=<this worktree> K="bool_map_keys_order or key_map_order_is_independent or boolean_and_equal_integer or identity_key_topology or full_width_ or int_keys_separated"

Toast 03af4fa: 9 passed. Before the rewrite the five listed tests failed on
Toast. Barn with its matching change (`make conformance`, same K): 9 passed.

## Next step

Publish alongside the Barn branch `toast-2.8-map-key-order`.
