# Softcode callback inventory and test expansion

## Goal

Q: "Inventory toast, then build out all the missing tests with proper semantics."
Q: "make sure we assert they are called with the proper caller/player/whatever else too."

Cover implicit server-to-softcode entry points, their distinct triggers, invocation context, outcome handling, and observable ordering. A callback-name match is not evidence that its contract is tested.

## State

2026-10-26: Q approved with "Make it so!" and requested PR publication and babysitting through CI. Implementation active in C:/Users/Q/code/mct-softcode-callbacks on test/softcode-callback-context. No merge authorization.

- Conformance checkout: main. Tracked working tree initially clean; many pre-existing untracked files and other worktrees must be preserved.
- Toast: C:/Users/Q/src/toaststunt, pinned oracle source, no tracked modifications reported. This matches .github/workflows/toast-conformance-core.yml:259 and :517.
- Source inventory covers all references to run_server_task, run_server_task_setting_id, do_server_verb_task, call_verb, call_verb2, do_input_task, and run_server_program_task in src/*.cc. The named implicit dispatches form 27 callbacks/families below.
- The inventory records source and prior coverage. Active-file exploratory Toast runs now cover the added cases. They do not establish CI-pinned acceptance. Existing create.yaml uses suite-level initialize setup and unindented tests; both were included in the inventory.
- This living inventory travels with the implementation commit. A separate root checkpoint file in the original checkout is required by the developer checkpoint instruction and stays uncommitted.

## Decisions and why

### Smallest implementation

Extend existing suites where the event already has a real trigger; add focused suites for startup scripts, lag handlers, callback outcomes, and context gaps. Reuse YAML tables for actual semantic alternatives, existing connection actions, dump/restart, signal actions, and exec-fixture installation. No server changes, generated Cartesian coverage, new review gates, or new coverage framework.

Expected size: approximately 50-80 new or strengthened semantic cases, 2,000-3,500 YAML lines including fixtures and cleanup; about 100-200 controller/helper lines plus focused controller tests. These are planning estimates, not a quota or a promised passing count. Reuse current fixture code and strengthen an existing assertion instead of duplicating its trigger wherever practical.

### Invocation assertions required in every added callback case

Record values inside the callback before invoking any helper: this, caller, player, verb, args, argstr, dobj, dobjstr, prepstr, iobj, iobjstr, task_perms(), caller_perms(), and callers(). For inherited dispatch, inspect the callback's frame using a small MOO observer verb and check the defining object as well as the receiver. Do not infer the callback frame from a later observer's own variables.

Use different player, verb owner, receiver, defining object, and driver identities where applicable. Use a nonempty parsed command context for inherited-context tests, so mistakenly clearing the fields cannot pass. Include wizard-reassigned player and nonwizard-reassigned player cases for callbacks through call_verb2. Verify callback return/error/suspension effect and event ordering, not just a marker.

Source contracts:

- execute.cc:3280-3337: server callback this is the supplied receiver; permissions come from verb owner; player is supplied by dispatch; caller and caller_perms() are #-1; callers() is empty; dobj/iobj are #-1; object strings/prepstr are empty; argstr is supplied by dispatch; verb is the supplied name.
- execute.cc:734-780: nested/builtin callbacks use callback owner permissions, caller = calling activation's this, and inherited parsed fields. Wizard callers can supply an OBJ-valued reassigned player; other callers use the activation's player. WAIF names lose the leading colon in the MOO verb variable on this path.
- execute.cc:3341-3372: command and huh dispatch have caller = connected player, player = connected player, parsed command fields, and verb = the typed command rather than the fallback name huh.
- execute.cc:452-517, :3711-3744: frame entries contain this, invoked verb, programmer, definer, player; optional line numbers; synthetic builtin frames have their own representation. caller_perms is the previous activation's programmer or #-1 at root.
- tasks.cc:1846-1869: absent/noncallable server hooks simulate an empty verb returning 0. db_verbs.cc:484-537 and :235-236 require executable callable verbs and search parents. Test inherited/non-executable handling through each distinct dispatcher, without multiplying every event by all name-lookup permutations.
- Preserve identities/types and exact deterministic values. Normalize only variable object numbers, elapsed duration, task IDs, and line locations where appropriate; do not replace meaningful context checks with type-only assertions.

## Inventory: source, existing evidence, and additions

Paths in the existing-test column are relative to src/moo_conformance/_tests/. Source paths are relative to Toast src/.

| Callback/family | Dispatch and contract | Existing evidence | Work to add/strengthen |
|---|---|---|---|
| checkpoint_started | server.cc:829-842; #0, player #-1, args {}; before flush; outcome ignored | audit/checkpoint_lifecycle_toast_oracle.yaml:10; server/signals_checkpoint.yaml:6 | Full root context; true/false return, abort, suspend/resume must not become a checkpoint veto; before/after state and exact event count. |
| checkpoint_finished | server.cc:404-411, :836-847, :453-454; #0, player #-1, args {0 or 1} | Same lifecycle test asserts success and persistence; server/signals_timers.yaml:6 and signals_children.yaml:26 cover timer/child success | Actual failed open/write/publication -> {0}; success -> {1}; full context on both; recovery checkpoint after removing fault; no direct softcode invocation masquerading as a server test. |
| server_started | server.cc:783-795; checkpointed disconnections precede #0 callback, args {}, player #-1 | audit/connection_lifecycle_toast_oracle.yaml:1097 checks order, this and disconnection player/arg | Strengthen full root context, inherited definition, once per boot; callback false/error/suspension does not suppress normal server operation. |
| do_start_script | server.cc:1273-1334, :2019-2032, :2318-2328; #0, player #-1; argument list is cleaned script lines; both CLI forms follow option order; outcome logged | No references in test YAML | Single --start-line, multiline --start-script including empty line, both orders, absent handler, return/error/suspend result; full root context and ordering before server_started. |
| handle_signal | server.cc:384-400; #0, player #-1; SIGUSR1/SIGUSR2 name; false completed -> default; true/abort/block -> suppress default | server/signals_user_hooks.yaml:6; signals_checkpoint/log_rotation/default_usr1/ignored/shutdown | Existing truth/outcome matrix is substantial: strengthen caller/caller_perms/callers/parsed fields and owner distinction; inherited/noncallable dispatch. Keep negative INT/TERM and ignored-signal assertions. |
| handle_lagging_task | execute.cc:3108-3147; elapsed wall time around run(), threshold >= 0.1; completed payload differs from aborted/blocked stack payload; callback #0, player from root activation | None | Disabled threshold (<0.1), absent handler, completed/aborted/blocked triggering slices, full callback context; completed six-field partial frame uses full verb names/definer, noncompleted uses structured stack; elapsed float >= configured threshold. Disable lag in handler to avoid recursively measuring the test handler. |
| handle_uncaught_error | execute.cc:535-565, :3162-3186; args code/message/value/stack/traceback; #0; originating player; after unwind | language/error_traceback.yaml:403, :430, :477; vm/tick_accounting.yaml:924 | Full root context on foreground, forked and resumed failures; caught error must not invoke hook; cleanup/finally ordering; true/block suppress printed fallback, false/absent/aborted handler prints original traceback; handler errors do not recursively invoke traceback handler. Verify frame payload and custom values. |
| handle_task_timeout | execute.cc:580-601, :3162-3186; args resource/stack/traceback; ticks and seconds; kill has no timeout hook | audit/task_scheduling_toast_oracle.yaml:533; server/signals_timers.yaml:36; vm/tick_accounting.yaml | Full root context and originating player; tick/seconds payloads; same handled/fallback outcome branches; kill_task negative control; foreground/background/resumed task distinctions where current coverage lacks context. |
| user_connected | server.cc:1706, :1723-1724, :921; listener receives {player}, player set to affected user | audit/connection_lifecycle_toast_oracle.yaml:344, :451, :572, :695, :971 | Strengthen owner/caller_perms/stack/default fields; switch_player to unused player, prelogin switch and silent flag; prove callback selection/order. |
| user_created | server.cc:1723-1724; do_login_task compares new player ID with pre-login max (tasks.cc:882, :958) | audit/connection_hook_frames_toast_oracle.yaml:50; connection_lifecycle:2174 | Full frame, inherited listener hook; returning existing player must not call created; inspect reuse of a recycled ID against source's max-ID predicate rather than English "new". |
| user_reconnected | server.cc:1699-1700 (same listener login), :921 (switch to connected player) | connection_hook_frames:108; cross-listener case verifies different selection | Full frame; switch-to-connected branch, silent true/false, listener selection and event exclusions. |
| user_disconnected | server.cc:788 (checkpointed), :881 (login timeout), :905 (boot/disconnect flag), :919 (switch away from old user) | connection_lifecycle:1097 and :1244 | Add boot_player and switch_player callback assertions, prelogin boot, set_player_flag removal where same path is reached; context, listener and ordering. Existing boot message tests do not assert this hook. |
| user_client_disconnected | server.cc:1557 (client close), :1703 (cross-listener redirection) | connection_lifecycle:855, :971; connection_hook_frames:108 has negative assertion | Strengthen complete context and old-listener/new-listener ordering; prelogin client close with negative connection ID, not just logged-in close. |
| do_login_command | tasks.cc:878-965; listener; negative connection player; parsed words and original or cleared PROXY line; returned user accepted only before suspension and while connection remains unlogged | connection_hook_frames:8; connection_lifecycle:34, :254, :1941; divergence_input_lifecycle_decompile:121; proxy_delayed_prelude | Full frame with separate owner/receiver; return nonuser/nonobject, aborted/absent/noncallable, switch_player inside handler; preserve existing suspended-result rejection test and add context before/after resume. |
| do_blank_command | tasks.cc:891-901; only trusted-proxy empty input; false prevents login fallthrough, true permits it | connection_lifecycle:174 asserts this/args/argstr for false | Assert both fallthrough outcomes, absent/noncallable, untrusted/nonempty negative controls, complete frame. Do not invent semantics for reading an uninitialized result after an aborted hook; source currently ignores outcome here. |
| do_command | tasks.cc:825-856; listener gets words/full input; true, abort or block stop fallback; completed false permits native dispatch | server/lifecycle:12, :37; command/parser:591, :657; command_parser_toast_oracle:219, :354; move_hooks_suspend:122 | Full frame and separate owner; aborted and blocked/resumed-false no native second dispatch; intrinsic-command bypass, inherited/noncallable fallback. |
| do_out_of_band_command | tasks.cc:970-973; listener, connection player, word list/raw OOB command; return ignored | server/lifecycle:64; audit/divergence_command_connection_lifecycle:25; gap_followups telnet/GMCP cases; input_task_completion | Complete frame pre/post login; error/suspend must not redirect into ordinary parsing; retain protocol-specific input assertions. |
| huh | tasks.cc:844-856; location or player selected by player_huh; do_input_task uses parsed command frame | command/parser and server/command_parsing; command_parser_toast_oracle:254 | Full native command frame, typed verb, parsed object fields, owner and inherited definer; absent chosen fallback must not search the other huh target. |
| initialize | objects.cc:430-457 create permanent/anonymous with optional init list; :520 recreate with {} | builtins/create.yaml suite setup plus argument cases and :431; builtins/recreate.yaml:57 | Complete nested context for permanent/anonymous/recreate; supplied initializer arguments; inherited definer; hook return ignored in favor of created object; absent/nonexec, raise, suspend/resume and post-initialize identity. |
| accept | objects.cc:125-168; destination gets {moved object}; before mutation; false rejects nonwizard, wizard overrides; same location/#-1 skip | builtins/move_hooks_toast_oracle:8, :55; audit/divergence_move_recycle_lifecycle | Existing frame is good but identities coincide: distinct owners/player and inherited nonempty parser fields; error/suspend and post-callback mutation validity branches. Preserve existing absence/false/relocation cases. |
| exitfunc | objects.cc:175 and :769; old location gets {object}, after location mutation; move and recycle paths | move_hooks_toast_oracle, move_hooks_suspend; divergence_move_recycle_lifecycle:194, :465, :499 | Full nested frame for ordinary move AND recycle of object/contents; inherited fields and owner; resumed context; missing/noncallable; reentrant changes and errors must assert the state at that stage. |
| enterfunc | objects.cc:187-204; destination gets {object} only while destination and object remain valid and location still matches | move_hooks_toast_oracle:8, :83; move_hooks_suspend | Distinct context, inherited fields; return ignored, abort/suspend state and ordering; suppression if earlier callback recycles destination/object or relocates object. |
| recycle | objects.cc:805-859 explicit permanent/anonymous; server.cc:630-654 deferred anonymous cleanup | audit/divergence_move_recycle_lifecycle:414-544; builtins/gc.yaml; language/anonymous.yaml | Separate explicit nested-call frame from deferred server-root frame (player/caller #-1); exact {} args and counts; no double callback after explicit anonymous recycle; inherited callback; callback context across suspension where object lifetime permits. |
| :recycle (WAIF) | server.cc:661-677; deferred class lookup with this = WAIF, player #-1, args {}; marks processed to avoid repeated callback | language/waif.yaml:445; divergence_waif_statement_semantics:171; startup_pending_waif_recycle_shutdown | Full root context including literal verb = :recycle on this dispatch path; owner distinct from class owner/waif owner, definer and identity; once on final release, retained refs delay; suspended hook/retained this does not repeat. |
| :_index (WAIF) | execute.cc:1594-1621 normal read, :1695-1720 indexed compound update; wizard-owned class; {key}; missing -> E_TYPE | language/waif_authority.yaml:159, :199, :214, :231 | Full nested context with MOO verb = _index; direct read vs indexed assignment's read stage; missing/invalid/nonwizard paths for both opcodes; return, raise, suspend, inherited lookup. |
| :_set_index (WAIF) | execute.cc:1184-1213; {key,value}; same class restrictions; returned value becomes VM result | waif_authority:159 | Full context with verb = _set_index; direct/nested assignment, setter return semantics, errors, suspension, missing/nonexec/nonwizard/invalid class; assert original WAIF identity separately from resulting expression/assignment value. |
| #0:bf_<builtin> family | functions.cc:219-237 before native arity/type checks; caller this != #0 and builtin protected; wrapper failures/missing have wizard/nonwizard and E_MAXREC behavior | builtins/protected_builtin_redirect.yaml; audit/time_server_builtins_toast_oracle:116 | Full nested context, complete raw args including invalid native call shapes, wrapper owner distinct; #0 bypass; inherited/nonexec; callback error/suspension and maxrec; protect one builtin with representative contracts rather than every builtin name. |

## Planned implementation and validation

1. Data-only additions using today's controller: extend existing context assertions and implement missing login/switch/boot, handler outcomes, initialization/recycling, WAIF and protected-builtin cases. Separate files by their current owners, not a new abstraction. Use bounded observation of callback records; restore hooks/options and clean up connections/objects. Persist only the intended startup fixtures.
2. Minimal controller support: an optional argument list on restart_server, forwarded as argv tokens into ManagedServer.start for that launch only, so real --start-line/--start-script triggers can be tested. Existing schema.py:404-411 has no launch arguments; server.py:266-282 builds a single fixed command. Do not reinterpret tokens with a shell, persist overrides into unrelated suites, or change the normal command.
3. Add one exec fixture for checkpoint faults using the existing _install_exec_fixtures path (server.py:526-552). It operates only on explicitly selected Test.db.new or its first temporary output inside the disposable test server directory; reject other locations. Controlled nonempty directories produce open/publication failures; on Linux a temporary symlink to /dev/full can exercise write failure. The fixture must remove only its own obstruction and cleanup must precede restart/reset. It does not edit the input database or touch a production process. Existing helper installation classifies as controller work.
4. Dependent data adds actual startup invocations and checkpoint failure/recovery. For lag callbacks use ftime(1) bounded CPU loop with sufficient test-local budgets to deliberately exceed 0.1 seconds, then complete/raise/suspend; restore options. Do not use suspend duration as proof of elapsed interpreter time. Payload assertion uses duration lower bound, never a precise timing value. If timing cannot be made reliable under the existing oracle, report that case as unverified rather than weakening it.
5. Keep controller and data changes separate: change_boundary.py:12-14, :62-83, :110-119 rejects mixed candidates and requires the controller on main before dependent data can be admitted. Independent data can proceed while that dependency is held. Do not merge without the applicable permission. Keep notes on task branches.
6. Run only files actively being authored locally against the actual Toast oracle if needed. Push/open PRs and use PR CI for the normal checks; do not reproduce CI locally as a push gate. Record exact oracle and candidate revisions, admitted cases, skips and failures. Passing another implementation is not proof of Toast semantics.

## Boundaries and unresolved verification

- Direct obj:verb(), pass(), eval(), scheduled fork/resume, and emergency console code also execute softcode but do not name implicit lifecycle callbacks. They were checked as dispatch entry points: execute.cc:2116-2188, :3341-3390, :3682; server.cc:1117-1121; tasks.cc:1875-1889. Keep their existing conformance suites; don't turn this callback campaign into an entire VM rewrite/test expansion.
- Fork failure (db_file.cc:1152-1154), unforked build behavior, and platform-specific waitpid variants remain explicit environment coverage questions. Shared checkpoint_finished(0) output is testable without exhausting host processes; do not claim that this exercises fork() failure itself or every compile-time profile. No resource-exhaustion or kernel fault-injection infrastructure is proposed.
- Startup arguments and the confined checkpoint-fault fixture are implemented in controller PR #161. Startup and write/publication data passed exploratory authoring runs but need the controller on main for trusted admission. The chmod open-failure case requires an unprivileged POSIX runner and was not executed by the root WSL session.
- User-defined signal tests already cover true/false/abort/suspend heavily. Reuse them; don't inflate coverage by repeating equivalent constants.
- GC and WAIF lifetime tests must not keep the target alive accidentally in the observation record. Record booleans/metadata before final release, except where retention is the explicit behavior under test.
- Inventory itself was read-only. Implementation and active-file testing followed Q's explicit approval. No runtime server changes or production actions are included.

## Surprises

- Initial progress incorrectly called server_started missing; corrected after reading connection_lifecycle_toast_oracle.yaml:1097-1213. It has coverage, but not all frame fields.
- total_cputime is a misleading variable name: execute.cc:3111-3115 measures high_resolution_clock elapsed wall time around run().
- WAIF :recycle is a server task and retains the colon in verb. WAIF indexing uses call_verb2, which strips it. A universal context expectation would be wrong.
- do_blank_command ignores the task outcome and inspects its result; do not infer supported error/suspension behavior from the better-defined do_command branch.

## Next step

Publish the independent data PR and monitor its CI. Publish startup/fault data separately; trusted acceptance requires controller PR #161 to be merged first. Q has not authorized merges. Continue fixing branch-related CI failures within the approved scope.


## Implementation update

- Current main provides confined chmod and unprivileged_posix for real failed-open checkpoints. The separate controller fixture covers checked writes and publication; it is not needed by this independent data branch.
- WSL /root/src/toaststunt differs from the CI-pinned source. Local authoring runs are exploratory; PR CI is the acceptance evidence.
- Publication and CI monitoring authorized. Data and controller stay in separate PRs; dependent data cannot receive trusted-controller CI until the controller is merged.


## Implemented coverage map

Paths below are relative to src/moo_conformance/_tests/. The source inventory
above remains the rationale; these are concrete additions, not a claim that every
OS failure or combination of generic verb-lookup rules has been executed.

- server/checkpoint_callback_context.yaml: start false/true/error/suspend and
  finished error/suspend, exact start/finish order and full root contexts.
- server/checkpoint_failure_callback_context.yaml: failed open, status zero, full
  context and subsequent successful recovery (unprivileged POSIX).
- server/server_started_callback_context.yaml: return/error/suspend and once per
  restart; audit/connection_lifecycle_toast_oracle.yaml strengthens all frame
  fields for checkpointed disconnections and login timeout.
- server/connection_callback_context.yaml: existing/new/recreated-ID login,
  same/cross-listener reconnection, client close, boot, prelogin close/boot/switch,
  and silent/non-silent switches to unused or connected players.
- server/input_callback_context.yaml: login return shapes/error/suspended result;
  command false/true/error/block fallback; OOB prelogin/logged-in outcomes;
  trusted blank false/true; player/location huh with parsed objects and inherited
  definer, plus absent selected huh must not search the other receiver.
- server/error_callback_context.yaml and error_handler_outcomes.yaml: foreground,
  forked and resumed uncaught errors, payload frames/finally order, caught and
  killed-task negatives, tick/seconds timeouts, handler truth/abort/block/absence/
  nonexecutability and original traceback fallback.
- server/lag_callback_context.yaml: completed/aborted/blocked slices with distinct
  payload formats and full context; disabled threshold negative.
- server/signals_user_hooks.yaml: existing signal/outcome matrix now also checks
  caller, caller permissions/stack and default parsed fields.
- builtins/builtin_callback_context.yaml: permanent/anonymous/recreated initialize
  return/suspend/error and absent/nonexecutable lookup; explicit permanent/anonymous
  recycle context and no second deferred callback after references are released.
- builtins/move_callback_context.yaml and recycle_exit_callback_context.yaml:
  distinct callback/driver owners, wizard vs nonwizard player reassignment,
  inherited parsed fields/definer, suspension, mutation state, and both recycle
  exitfunc paths.
- server/deferred_callback_context.yaml: retained reference delays recycling;
  anonymous/WAIF immediate and suspended root frames, inherited definer and once
  only. Anonymous marker is captured before suspension because destruction follows
  the first callback slice.
- builtins/waif_index_callback_context.yaml and waif_index_dispatch.yaml: read,
  compound read and setter frames, arguments, resumed continuations, setter return
  replacing the container versus assignment expression retaining RHS; missing,
  nonexecutable, nonwizard and invalid-class write/compound dispatch.
- builtins/protected_callback_context.yaml: raw ordinary/empty/extra/wrong-type
  args before native validation, full nested context, returned value, suspension
  and error propagation. The redirect is a tail call without a builtin stack frame.
- Separate dependent data: server/startup_script_callback_context.yaml covers both
  CLI forms/orders, blank script lines, return/error/suspend, absent/nonexecutable
  hooks, full context and ordering before server_started.
  server/checkpoint_io_failure_callback_context.yaml covers real checked-write and
  publication failures, exact diagnostic, full status-zero context and recovery.

## Validation limits and remaining delivery

Only actively authored files/cases were run locally. The WSL oracle differs from
the CI pin. CI must validate the published data against all repository profiles.
No fork-exhaustion injection, unforked build or alternate waitpid implementation
is claimed; those environment branches remain outside the available matrix.

PR #161 supplies the controller prerequisite. Independent data uses only current
main's controller. Startup/fault data requires that PR merged before its trusted
CI can execute the new field/fixture. No merge is authorized yet.

Surprises from authoring: the minimal DB fits in stdio buffers; /dev/full requires
padding to reach checked writes because Toast ignores the final fflush result.
Handler abort prints its own traceback before the original but does not recursively
invoke the DB handler. Test.db creates a fresh wizard at login, so restored-hook
ownership is compared with the saved installing owner, not the new connection.
