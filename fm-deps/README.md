Opam Package for FM dependencies
================================

This package gives the list of OCaml dependencies for the FM toolchain.

To add dependencies, edit the `dune-project` file, and do not forget to run
`dune build` to update the `br-fm-deps.opam` file.

To update your dependencies, you can simply run:
```
opam update
opam install br-fm-deps.opam
```
Note that this may mess up your current switch, so be careful.
