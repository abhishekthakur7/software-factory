# soft-factory

The trusted control plane of the software factory: the `factory` command,
its stage drivers, and the run record. Design documents live under
`docs/`; the working rules for code and tests are in [AGENTS.md](AGENTS.md).

## Start

One command, from any directory:

```bash
bin/start
```

It frees every port the factory uses, stops any stale `factory` process,
syncs the Python environment with `uv`, and runs the `factory` command.
Arguments pass straight through, so these all work:

```bash
bin/start show 1
```

```bash
bin/start advance 1
```

```bash
bin/start run 1 S1
```

With no arguments it prints the command's help. The ports it frees are the
`PORTS` list at the top of the script; only the mockup preview server on
8765 exists today, and a server added later joins that list.

## Prerequisites

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) on the PATH

Nothing else. `uv sync` installs the one runtime dependency and pytest.

## The `factory` command

| Verb | What it does |
|---|---|
| `factory advance <ticket>` | Runs the stage due in the ticket's state, else evaluates the state's gate, else reports that the ticket waits on a human |
| `factory run <ticket> <stage>` | Runs one stage (`S0` to `S6`); a stage its state does not precede is refused and recorded |
| `factory show <ticket>` | Prints the ticket's state and its stage runs |

`--db <path>` picks the record; it defaults to `runs/factory.sqlite`, and
the run tree (per-ticket artefacts) lives in the same directory.

## Checks

The adoption gate runs the whole test suite:

```bash
uv run python -m runner.gate
```

## Layout

| Path | Holds |
|---|---|
| `runner/` | The control plane: record, schema, state table, stages, command |
| `runner/tests/` | The pytest suite the gate runs |
| `factory/` | Versioned, read-only at run time: manifest, agents, skills, rubrics, evals, config |
| `runs/` | Unversioned run state: the record and per-ticket artefacts |
| `docs/` | Charter, PRD, design, build tickets and per-ticket build notes |
| `tools/` | Document checkers |
