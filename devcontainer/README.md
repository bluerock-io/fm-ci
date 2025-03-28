# FM CI Dev Container

This directory is set up to use the FM CI containers using the dev-container
feature of VS Code (does not work with Codium).

## How to Use

To use, copy **this directory** to the directory that you want to work in as
`.devcontainer`. From a BHV root, you can run the following:

```sh
cp -r fmdeps/fm-ci/devcontainer .devcontainer
```

To make this work, you need to either have two environment variables set or to
make replacements in the `devcontainer.json` file.

- `${env:DUNE_CACHE_DOCKER}` should be the path to the dune cache for the docker
  images. This should probably be different than the `dune` cache for your
  system.
- `${env:LLVM_VERSION}` should be the version of LLVM to use, e.g. `19`.
- `${env:BR_FMDEPS_VERSION}` release of BlueRock FM dependencies (currently 2025-02-26).
- `${env:SWIPL_VERSION}` SwiPL version to use (9.2.7).


If you want to avoid these manual replacements, you can use environment
variables which are very easy to set up using a tool such as
[direnv](https://direnv.net/) and associated VsCode extensions like
https://marketplace.visualstudio.com/items?itemName=mkhl.direnv.

Note: at least on MacOS, you will need to start VsCode from inside a shell for
this to work.

### Using direnv

If you have `direnv` configured, you simply need the following `.envrc`:

```sh
export DUNE_CACHE_DOCKER=$PWD/dune-cache
# choose your LLVM version
export LLVM_VERSION=19
export BR_FMDEPS_VERSION=2025-02-26
export SWIPL_VERSION=9.2.7
```

This must be placed in your `bhv` checkout/worktree, or in a containing folder;
the dune cache will be placed in that folder.
This works because `direnv` searches for `.envrc` files recursively upward, so
you can have a single file in the root of your BlueRock worktree and be all set.

You will also need to trust the `.envrc` file!

If you want per-worktree configuration, you can override variables using
`source_up`. For example, to use LLVM 20 in just one worktree:
```sh
source_up
export LLVM_VERSION=20
```

