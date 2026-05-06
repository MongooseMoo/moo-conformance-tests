# Barn/ToastStunt Deviation Conformance Checklist

Workflow: for each item, first add or run an oracle test against ToastStunt and keep only behavior Toast confirms. Barn failures are useful only after the Toast oracle passes.

Order rule: command parser tests come first because many later tests depend on reliable raw-command setup. Builtin permission tests precede lifecycle tests when lifecycle setup depends on safe object/verb manipulation. Restart/persistence tests come last because they need harness support.

## Command Parser And Object Matching

- [x] CMD-001 tokenizer_backslash_escapes: command word parsing consumes backslash escapes like Toast.
- [x] CMD-002 tokenizer_midword_quotes: quotes toggle inside a word, not only at word start.
- [x] CMD-003 shortcut_say_reparsed: leading quote rewrites to `say` and still receives Toast-style parsed command variables.
- [x] CMD-004 shortcut_emote_reparsed: leading colon rewrites to `emote` and still receives Toast-style parsed command variables.
- [x] CMD-005 shortcut_eval_reparsed: leading semicolon rewrites to `eval` and still goes through normal command setup.
- [x] CMD-006 argstr_preserves_original_spacing: `argstr` preserves the original post-verb substring spacing.
- [x] CMD-007 prep_scan_leftmost_position: Toast chooses the earliest preposition position, not the globally highest-priority prep phrase.
- [x] CMD-008 negative_object_literal_failed_match: `#-1`, `#-2`, and `#-3` in command object slots resolve to FAILED_MATCH when parsed as object literals.
- [x] CMD-009 name_alias_exact_ambiguity: an object name and another object alias with the same exact text are ambiguous.
- [x] CMD-010 name_alias_partial_ambiguity: partial matches across names and aliases are pooled for ambiguity.
- [x] CMD-011 player_name_in_room_contents_matches: the current player can be matched by name through room contents.
- [x] CMD-012 do_command_runs_for_semicolon_eval: `do_command` runs before a semicolon eval command.
- [x] CMD-013 huh_runs_after_argspec_mismatch: a matching verb name with mismatching argspec falls through to `huh`.
- [x] CMD-014 quoted_backslash_wordlist_for_do_command: `do_command` receives Toast's escaped/quoted word list.
- [x] CMD-015 dot_program_intrinsic: `.program object:verb` command mode works for programmers.

## Verb Lookup, Frames, And Permissions

- [x] VRB-001 alias_collision_definition_order: callable verb alias collisions resolve in Toast definition order.
- [x] VRB-002 trailing_star_wildcard_matches_any_suffix: a verb alias ending in `*` matches longer command/call names.
- [x] VRB-003 max_stack_depth_raises_toast_limit: recursive verb calls hit Toast's max activation limit.
- [x] VRB-004 verb_info_no_inheritance: `verb_info(obj, name)` does not find inherited verbs.
- [x] VRB-005 verb_args_no_inheritance: `verb_args(obj, name)` does not find inherited verbs.
- [x] VRB-006 verb_code_no_inheritance: `verb_code(obj, name)` does not find inherited verbs.
- [x] VRB-007 verb_info_requires_read: non-readable verbs deny `verb_info`.
- [x] VRB-008 verb_args_requires_read: non-readable verbs deny `verb_args`.
- [x] VRB-009 verb_code_requires_read: non-readable verbs deny `verb_code`.
- [x] VRB-010 set_verb_info_requires_write_and_owner: `set_verb_info` requires Toast write/ownership permissions.
- [x] VRB-011 set_verb_args_requires_write: `set_verb_args` requires Toast write permissions.
- [x] VRB-012 set_verb_code_requires_write: `set_verb_code` requires Toast write permissions.
- [x] VRB-013 pass_preserves_command_vars: `pass()` copies `argstr`, `dobj`, `dobjstr`, `prepstr`, `iobj`, and `iobjstr`.
- [x] VRB-014 callers_includes_toast_server_frames: `callers()` frame visibility matches Toast for server-initiated calls.
- [x] VRB-015 callers_builtin_frame_shape: builtin pseudo-frame visibility matches Toast where observable.
- [x] VRB-016 set_task_perms_checks_current_programmer: `set_task_perms` compares target against current programmer, not player.
- [x] VRB-017 caller_perms_top_level_is_nothing: top-level `caller_perms()` returns `#-1`.
- [x] VRB-018 diamond_inheritance_resolution: multi-parent verb lookup matches Toast order.
- [x] VRB-019 pass_parent_search_order: `pass()` parent search order matches Toast.
- [x] VRB-020 command_context_nested_call: nested verb calls from command verbs inherit command variables.

## Task Scheduling, Limits, Read, And Persistence

- [x] TSK-001 default_fg_ticks: foreground default tick limit matches Toast.
- [x] TSK-002 default_bg_ticks: background default tick limit matches Toast.
- [x] TSK-003 server_options_fg_ticks_runtime: `$server_options.fg_ticks` is honored for new tasks.
- [x] TSK-004 server_options_bg_ticks_runtime: `$server_options.bg_ticks` is honored for forked tasks.
- [x] TSK-005 server_options_fg_seconds_runtime: `$server_options.fg_seconds` is honored.
- [x] TSK-006 server_options_bg_seconds_runtime: `$server_options.bg_seconds` is honored.
- [x] TSK-007 server_options_max_stack_depth_runtime: `$server_options.max_stack_depth` is honored.
- [x] TSK-008 suspend_zero_yields_to_ready_task: `suspend(0)` gives another ready task a turn.
- [x] TSK-009 tick_exhaustion_not_catchable: tick exhaustion cannot be swallowed by MOO `try`.
- [x] TSK-010 handle_task_timeout_invoked: Toast invokes `$server:handle_task_timeout` on timeout.
- [x] TSK-011 suspended_task_survives_restart: suspended tasks persist across checkpoint/restart.
- [x] TSK-012 read_requires_connection_owner_or_wizard: `read()` denies unrelated programmers.
- [x] TSK-013 read_requires_last_input_task: `read()` is only allowed from the last input task context.
- [x] TSK-014 yin_yields_when_needed: `yin()`/`yield_if_needed` has Toast scheduling behavior.
- [x] TSK-015 seconds_deadline_resets_on_resume: resumed suspended tasks get Toast-style execution limit reset.
- [x] TSK-016 fg_to_bg_after_suspend_limits: a suspended foreground task resumes with Toast background limits if Toast does that.
- [x] TSK-017 queued_task_reported_budget: `queued_tasks()` reports task budgets and start times like Toast.
- [x] TSK-018 force_input_read_login_interaction: `force_input` interaction with login/read matches Toast.

## Login, Connection, Listener, And Network Lifecycle

- [ ] CON-001 listener_handler_do_login_command: `listen(handler, port, options)` dispatches login hooks on that handler.
- [ ] CON-002 listener_handler_do_command: post-login command hooks dispatch on the connection's handler.
- [ ] CON-003 listener_handler_do_blank_command: trusted-proxy blank-line hook dispatches on the listener handler.
- [x] CON-004 do_login_command_argstr_original: `do_login_command` sees original command and Toast word parsing.
- [ ] CON-005 proxy_command_clears_login_input: trusted proxy `PROXY` command is parsed and cleared like Toast.
- [ ] CON-006 user_created_hook_on_new_login_object: `user_created` runs when login creates a new player.
- [ ] CON-007 user_client_disconnected_hook: client-initiated disconnect invokes Toast's client-disconnect hook.
- [ ] CON-008 user_reconnected_cross_listener_hooks: reconnect hook behavior matches Toast.
- [ ] CON-009 connect_timeout_server_option: `$server_options.connect_timeout` controls login timeout.
- [ ] CON-010 flush_command_flushes_pending_input: connection `flush-command` flushes queued input.
- [x] CON-011 hold_input_blocks_inband: `hold-input` queues normal commands until released.
- [x] CON-012 hold_input_allows_oob_when_enabled: OOB input bypasses hold-input unless disabled.
- [x] CON-013 disable_oob_blocks_oob: `disable-oob` makes OOB wait like in-band input.
- [x] CON-014 oob_prefix_dispatch: `#$#` dispatches `do_out_of_band_command`.
- [ ] CON-015 listener_print_messages_suppresses_connect_msg: listener `print-messages` controls connect messages.
- [x] CON-016 connection_name_method0_hostname: `connection_name(player)` method 0 returns Toast hostname format.
- [x] CON-017 connection_info_source_fields: `connection_info()` source fields use actual network handle data.
- [ ] CON-018 boot_player_messages: boot/disconnect messages match Toast server options.
- [ ] CON-019 recycle_redirect_timeout_messages: lifecycle message options match Toast.

## Time And Server Builtins

- [x] TIM-001 ctime_includes_timezone: `ctime()` includes Toast's full timezone text.
- [x] TIM-002 ctime_extreme_clamps_or_errors: extreme integer timestamps match Toast clamp/error behavior.
- [x] TIM-003 ftime_arg_clock_selector: `ftime(1)` and `ftime(2)` are clock selectors, not timestamp conversion.
- [x] TIM-004 shutdown_accepts_two_args: `shutdown` accepts Toast's optional second argument.
- [x] TIM-005 queue_info_no_arg_no_wizard_required: `queue_info()` no-arg permission matches Toast.
- [x] TIM-006 queue_info_wizard_map_shape: `queue_info(player)` map keys match Toast.
- [x] TIM-007 set_property_info_requires_perm: `set_property_info` requires Toast permissions.
- [x] TIM-008 set_player_flag_false_boots_player: clearing player flag boots active players.
- [x] TIM-009 builtin_protect_properties: `.protect_<funcname>` server options protect builtins like Toast.
- [x] TIM-010 memory_usage_behavior: `memory_usage()` behavior matches Toast's actual configured result.

## Harder Audit Follow-Ups

- [x] GAP-001 intrinsic_command_table: Toast intrinsic command table is fully compared and covered.
- [ ] GAP-002 transport_telnet_iac_binary: telnet IAC and binary-mode line parsing match Toast.
- [ ] GAP-003 output_order_disconnect: output buffer ordering during disconnect matches Toast.
- [x] GAP-004 move_chparent_trust_check: move/chparent/trust_check permission flow matches Toast.
- [x] GAP-005 property_flag_enforcement: property read/write/change flags match Toast.
- [x] GAP-006 command_dispatch_x_flag: Toast command dispatch executes matching verbs even without the `x` flag.
- [x] GAP-007 waif_anonymous_callers: WAIF/anonymous values in callers/task_stack match Toast.
- [x] GAP-008 task_local_fork_suspend: Toast forked tasks start with empty `task_local()` state.
