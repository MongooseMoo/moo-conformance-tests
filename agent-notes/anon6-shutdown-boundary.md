# Anon6 shutdown completion boundary

## Goal
Observe the canned Anon6 database's natural shutdown before asserting its log and checkpoint, using the runner's existing lifecycle support.

## State
Replaced the fixed 750 ms sleep with wait_for_server_exit requiring exit code zero within 5000 ms. Both existing log and checkpoint-content assertions remain unchanged. No local tests or CI steps were run; parent owns publication, review and PR CI.

## Decisions and why
Anon6.db logs shazam before run_gc(), a second suspend(0), shutdown() and kill_task(task_id()). The log message therefore does not establish checkpoint completion. Existing runner.wait_for_server_exit observes natural process exit, asserts its status and retains launch file/log freshness boundaries. The existing deferred-WAIF-shutdown fixture uses the same lifecycle assertion and deadline. This correction requires successful natural exit before checking the same output; it does not extend the file assertion timeout or alter its contents.

## Surprises
The failing Banteng CI artifact records the missing checkpoint after 0.758 seconds but contains no process status or server log. The same run's Java Anon6 test passed after waiting for actual shutdown. Whether the failed process later wrote its checkpoint remains unverified; this change corrects the fixture's missing completion boundary without claiming a production defect.

## Next step
Parent checks the two-file diff, publishes the PR, obtains review, follows CI and merges. Implementation worker does not push or publish.

## Draft PR description
Anon6 logs shazam before garbage collection, suspension and shutdown, so its fixed sleep can reach the checkpoint assertion without observing completion. Replace that sleep with the existing natural-exit assertion, requiring exit code zero, then retain both log and checkpoint-content assertions unchanged.

Validation: source comparison with the existing deferred-WAIF shutdown fixture and runner/server/schema lifecycle implementation. Tests remain for PR CI; no local reruns.
