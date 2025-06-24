#!/bin/bash -evx

opam option depext=false
opam update -y
opam repo add archive git+https://github.com/ocaml/opam-repository-archive

make ast-prepare -sj${NJOBS}
opam pin add -y -k rsync --recursive -n --with-version dev .

opam install -y $(opam pin | grep -E '/fmdeps/(cpp2v|vscoq|coq-lsp)' |
  awk '{print $1}')
/tmp/files/opam-clean

find $(opam var prefix) \( -path '*bluerock*/*.v' -o -path '*bluerock*/*.ml' \) -print0 |
  xargs -0 truncate --size 0

sudo rm -rf /tmp/files
