Checkpoint: PR #86 CI runtime diagnosis for exact head 9c37107.
Finding: all profiles expose background_test, finished_tasks, and malloc_stats; three tests wrongly expect E_INVARG.
Finding: 32-bit additionally invalidates parse_json(maxint) and two ctime maxint expectations.
Current state: structure/quality passed; runtime totals are 6 failures on 32-bit and 3 on each 64-bit profile.
Next action: report the exact cause; no branch or PR changes are authorized by the read-only check request.
