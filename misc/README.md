Random Scripts And Utilities
============================

## Normalization of Imports

The script `single_line_from.sh` can be used to attempt to turn multi-line
`From ... Require ...` vernaculars into single-line ones.

In a second step, `remove_from.sh` can be used to normalize all imports to
the form `Require ...`.

## Flamegraph

See file `log_flamegraph.py`, but there is an OCaml version of it that can
be run with `dune exec -- coqc-perf.perf-script`.
