# Complete the Toast 2.8 oracle cutover

## Goal

Finish the approved non-WASM merge plan by restoring one immutable Toast 2.8
oracle for every admitted workflow mode after the expectation data lands.

## State

The transition repair #220 and expectation data #217 have merged. Prepared
the cleanup on ci/universal-toast-2.8: both Toast jobs use the same constant
pin; the temporary data-marker selector, output and its transition-only test
fixtures are removed. Existing workflow tests now assert the universal pin.
The cleanup is ready to publish for current-base CI; it has not run CI yet.

Barn's implementation group has merged through #870. Conformance #219 and
#85 have merged. The #85 ledger executed all 13,944 packaged cases across
three Toast profiles with zero failures or errors, including its five
ToastCore cases. This branch includes both data merges.

## Decisions and why

Publish from main after #219 and #85, so one final current-base CI proves
the complete suite and the final controller together.
The existing three-profile Toast execution and zero-omission ledger are the
required validation, alongside controller unit, type and lint checks.

## Surprises

A wrapper syntax error prevented the initial cleanup edit call from running.
The corrected wrapper applied the reviewed deletion. No partial edits were
assumed from the rejected wrapper.

## Next step

Publish the controller-only cleanup PR, fix CI findings and merge it. Then
verify both default branches on the complete final suite and preserve the
raw evidence.
