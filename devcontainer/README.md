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


If you want to avoid these manual replacements, you can use environment
variables which are very easy to set up using a tool such as
[direnv](https://direnv.net/).

### Using direnv

If you have `direnv` configured, you simply need to add the following:

```sh
# bluerock_root/.envrc
export DUNE_CACHE_DOCKER=$PWD/.dune-cache
# choose your LLVM version
export LLVM_VERSION=19
```

Reminder `direnv` searches for `.envrc` files recursively upward so you can have
a single file in the root of your BlueRock worktree and be all set. If you want
per-worktree configuration, you can override variables using `source_up`. For
example:

```sh
source_up
export LLVM_VERSION=20
```

