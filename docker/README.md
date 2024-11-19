FM CI Docker Images
===================

## WARNING

Be extremely careful when overwriting existing tags in the gitlab container
registry, as this can obviously break things. You should typically always
push new tags, unless you know exactly what you are doing.

## Generating New Versions of the CI Images

To generate a new set of CI image, start by updating the `FMDEPS_VERSION`
variable in the `Makefile`.

Other variables control what combinations of LLVM and SWI-Prolog are used in
the produced CI images.

## Interacting with the GitLab Container Registry

NOTE: In order to actually interact with the gitlab container registry, you'll
need an API token (get this from within the gitlab UI). For docker to log into
our registry, you can use
```
make login
```
which may prompt you for a user name and token.

## Build

To rebuild all images, run:
```
make build
```

## Pushing Tags

To push all tags (this implies building), run:
```
make push
```
Note that by default the commands are not run. See the output to know how to
actually push.

## Building / Pushing Individual Images

You can run the following to list available `make` targets for building or
pushing particular versions.
```
make list-targets
```

## Supported Combinations of LLVM and SWI-Prolog Versions

The `Makefile` defines the following variables to contral what docker images
are built and pushed by `make build` and `make push` respectively:
relies on four variables:
- `LLVM_VERSIONS` listing all supported LLVM versions,
- `LLVM_MAIN_VERSION` giving the main LLVM version,
- `SWIPL_VERSIONS` listing all supported SWI-Prolog versions, and
- `SWIPL_MAIN_VERSION` giving the main SWI-Prolog version.

Note that we do not generate images for the whole matrix of combinations. We
instead generate images for:
- all supported versions of LLVM, using the main SWI-Prolog version,
- all supported versions of SWI-Prolog, using the main LLVM version.
