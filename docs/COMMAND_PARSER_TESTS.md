# Command Parser Test Design

This document describes the YAML schema extension for testing MOO command parsing and verb dispatch.

## Background

MOO command parsing transforms player input like `put ball in box` into:
- `verb` = "put"
- `argstr` = "ball in box"
- `dobjstr` = "ball", `dobj` = #123 (resolved object)
- `prepstr` = "in"
- `iobjstr` = "box", `iobj` = #456 (resolved object)

The verb dispatch algorithm finds a matching verb based on:
1. Verb name match
2. Arg specs match: `{dobj_spec, prep_spec, iobj_spec}`
3. Search order: player → dobj → iobj → location → ...

## Design Goals

1. **Declarative** - Tests describe expectations, not implementation
2. **Minimal schema changes** - Extend existing step/expect structure
3. **Debuggable** - Clear what's being tested and why it fails
4. **Flexible** - Support various command parsing scenarios

## Schema Extension

### New Step Field: `command`

Alternative to `run` for sending raw commands (not wrapped with `;`).

```yaml
steps:
  - command: "put ball in box"
    expect:
      output: "..."
```

### New Expectation Field: `output`

Captures notify() output from raw commands.

```yaml
expect:
  output: "exact string match"
  # OR
  output:
    match: "regex pattern"
  # OR
  output:
    contains: "substring"
  # OR
  output:
    - "line 1"
    - "line 2"
```

### Verb Reporter Pattern

For testing parsed variables, create verbs that notify() their context:

```yaml
steps:
  - run: |
      obj = create($nothing);
      obj.name = "box";
      move(obj, player);
      add_verb(obj, {player, "xd", "put"}, {"any", "in", "this"});
      set_verb_code(obj, "put", {
        "notify(player, toliteral([\"verb\" -> verb, \"argstr\" -> argstr, \"dobjstr\" -> dobjstr, \"prepstr\" -> prepstr, \"iobjstr\" -> iobjstr]));"
      });
      return obj;
    capture: box
```

## Example Tests

### Basic Verb Dispatch

```yaml
name: command_parser
tests:
  - name: put_dispatches_to_iobj_verb
    description: "put X in Y" dispatches to Y's put verb with correct parsed values
    steps:
      # Create box with put verb
      - run: |
          obj = create($nothing);
          obj.name = "box";
          move(obj, player);
          add_verb(obj, {player, "xd", "put"}, {"any", "in", "this"});
          set_verb_code(obj, "put", {
            "notify(player, \"VERB:\" + verb);",
            "notify(player, \"ARGSTR:\" + argstr);",
            "notify(player, \"DOBJSTR:\" + dobjstr);",
            "notify(player, \"PREPSTR:\" + prepstr);",
            "notify(player, \"IOBJSTR:\" + iobjstr);"
          });
          return obj;
        capture: box
      # Create ball
      - run: |
          obj = create($nothing);
          obj.name = "ball";
          move(obj, player);
          return obj;
        capture: ball
      # Send command
      - command: "put ball in box"
        expect:
          output:
            - "VERB:put"
            - "ARGSTR:ball in box"
            - "DOBJSTR:ball"
            - "PREPSTR:in"
            - "IOBJSTR:box"
    cleanup:
      - run: "recycle({box})"
      - run: "recycle({ball})"
```

### Failed Object Match

```yaml
  - name: failed_dobj_match_uses_minus_3
    description: Non-existent dobj resolves to #-3 (FAILED_MATCH)
    steps:
      - run: |
          obj = create($nothing);
          obj.name = "box";
          move(obj, player);
          add_verb(obj, {player, "xd", "put"}, {"any", "in", "this"});
          set_verb_code(obj, "put", {
            "notify(player, \"DOBJ:\" + toliteral(dobj));"
          });
          return obj;
        capture: box
      - command: "put rock in box"
        expect:
          output: "DOBJ:#-3"
    cleanup:
      - run: "recycle({box})"
```

### Preposition Mismatch

```yaml
  - name: wrong_preposition_no_match
    description: Verb with "in" spec doesn't match "on" command
    steps:
      - run: |
          obj = create($nothing);
          obj.name = "box";
          move(obj, player);
          add_verb(obj, {player, "xd", "put"}, {"any", "in", "this"});
          set_verb_code(obj, "put", {"notify(player, \"CALLED\");"});
          return obj;
        capture: box
      - command: "put ball on box"
        expect:
          output:
            contains: "couldn't understand"
    cleanup:
      - run: "recycle({box})"
```

### Player Verb Dispatch

```yaml
  - name: player_verb_dispatch
    description: Verbs on player are checked for command dispatch
    steps:
      - run: |
          add_verb(player, {player, "xd", "wave"}, {"none", "none", "none"});
          set_verb_code(player, "wave", {
            "notify(player, \"WAVED\");"
          });
        as: wizard
      - command: "wave"
        expect:
          output: "WAVED"
    cleanup:
      - run: 'delete_verb(player, "wave")'
        as: wizard
```

### Verb Alias Matching

```yaml
  - name: verb_alias_matching
    description: Verb can have multiple names (aliases)
    steps:
      - run: |
          obj = create($nothing);
          obj.name = "box";
          move(obj, player);
          add_verb(obj, {player, "xd", "look examine"}, {"this", "none", "none"});
          set_verb_code(obj, "look", {
            "notify(player, \"LOOKED:\" + verb);"
          });
          return obj;
        capture: box
      - command: "look box"
        expect:
          output: "LOOKED:look"
      - command: "examine box"
        expect:
          output: "LOOKED:examine"
    cleanup:
      - run: "recycle({box})"
```

### This/Any/None Arg Specs

```yaml
  - name: argspec_this_requires_this_object
    description: "this" argspec requires command target to be this object
    steps:
      - run: |
          box = create($nothing);
          box.name = "box";
          move(box, player);
          add_verb(box, {player, "xd", "open"}, {"this", "none", "none"});
          set_verb_code(box, "open", {"notify(player, \"OPENED:\" + toliteral(this));"});
          return box;
        capture: box
      - run: |
          ball = create($nothing);
          ball.name = "ball";
          move(ball, player);
          return ball;
        capture: ball
      # "open box" should match (dobj is this)
      - command: "open box"
        expect:
          output:
            match: "OPENED:#\\d+"
      # "open ball" should NOT match (dobj is not this)
      - command: "open ball"
        expect:
          output:
            contains: "couldn't understand"
    cleanup:
      - run: "recycle({box})"
      - run: "recycle({ball})"
```

## Test Categories

### 1. Basic Parsing
- Verb name extraction
- Argument string (argstr)
- Direct/indirect object string parsing
- Preposition identification

### 2. Object Resolution
- Object by name
- Object by alias
- Ambiguous match (#-2)
- Failed match (#-3)
- Objects in different locations

### 3. Verb Arg Specs
- `this` vs `any` vs `none` for dobj/iobj
- Preposition matching (in, on, with, etc.)
- Preposition aliases (in/inside/into)

### 4. Dispatch Order
- Player verbs
- dobj verbs
- iobj verbs
- Location verbs
- First match wins

### 5. Special Commands
- Say shortcut: `"hello` → `say hello`
- Emote shortcut: `:waves` → `emote waves`
- Eval shortcut: `;1+1` → eval

### 6. Huh Handling
- No verb match → huh verb
- player_huh server option

## Implementation Notes

### Transport Changes

Add `send_command(text: str)` method to `SocketTransport`:
- Sends text without `;` prefix
- Captures all output between PREFIX/SUFFIX markers
- Returns list of output lines

### Schema Changes

In `schema.py`:
1. Add `command: str | None` to `TestStep`
2. Add `output` to expectation options
3. Validate: step has exactly one of `run` or `command`

### Runner Changes

In `runner.py`:
1. Check if step has `command` field
2. Call `transport.send_command(step.command)` instead of `execute()`
3. Match output against expectations

### Output Expectations

```python
@dataclass
class OutputExpect:
    exact: str | list[str] | None = None  # Exact match
    match: str | None = None               # Regex match
    contains: str | None = None            # Substring match
```

## Migration Path

1. Add transport support (non-breaking)
2. Add schema support (non-breaking)
3. Add runner support (non-breaking)
4. Write initial command parser tests
5. Iterate on schema based on test needs
