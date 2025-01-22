FM CI Docker Images
===================

## WARNING

Be extremely careful when overwriting existing tags in the gitlab container
registry, as this can obviously break things. You should typically always
push new tags, unless you know exactly what you are doing.

## Logging Into our Container Registry

To log into our GitLab container registry, you can run:
```
make login
```
If it is the first time you log in, you will be prompted for your GitLab user
name, as well as an API token (that you can generate from the GitLab web UI).
Using scopes `api, read_api, read_registry, write_registry` is sufficient.

You can run `make logout` to log out, and `make clean-all` to delete your user
name and token from the file system (this is useful if you made a mistake, or
if your token expired).

## Configuration Change for New Versions of the CI Images

To generate a new set of CI image, you need to:
1. Updating the `BR_FMDEPS_VERSION` variable in the `Makefile`.
2. Reset the `BR_IMAGE_VERSION` variable to `1` in the `Makefile`.
3. Optionally change other `Makefile` variables (LLVM version, ...)

**Note:** if you only want to update an existing image, you need to bump the
`BR_IMAGE_VERSION` variable. Note that this only makes sense for minor changes
since the image tags will be overwritten when updating the images.

The following variables control what combinations of LLVM and SWI-Prolog are
used in the produced CI images:
- `LLVM_VERSIONS` lists LLVM versions for which an image is generated.
- `LLVM_MAIN_VERSION` selects the main LLVM version (among the above).
- `SWIPL_VERSIONS` lists SWI-Prolog versions for which an image is generated.
- `SWIPL_MAIN_VERSION` selects the main SWI-Prolog version (among the above).

**Note:** we do not generate images for the whole matrix of combinations. We
instead generate images for one line and one row of the matrix:
- One for each supported LLVM version, using the main SWI-Prolog version.
- One for each supported SWI-Prolog version, using the main LLVM version.

## Build and Running

To rebuild all images, simply run:
```
make build
```
If you only want to rebuild a specific image, you can use
```
make list-targets
```
to get a list of available `Makefile` targets. The list also includes targets
for running (prefixed with `run-`) and pushing (prefixed with `push-`) images.

## Pushing Tags

To push all tags (this implies building), run:
```
make push
```
Note that by default the commands are not run. See the output to know how to
actually push.

**Note:** when you are setting up a new image version, with a distinct value
for `BR_FMDEPS_VERSION`, pushing is perfectly safe. In case of mistake in the
images configuration, you can push again without worry (provided you bump the
`BR_IMAGE_VERSION` variable in the case NOVA CI ran).

You can also push a single image if you want, using the corresponding target
from the output of
```
make list-targets
```

## Process for Setting-Up New CI Images

To set up new CI images, e.g., with new FM dependencies, you need to:
 1. Update the `Makefile` configuration as instructed above.
 2. Update the OCaml dependencies in `fm-ci/fm-deps/dune-project`.
 3. Update the Python dependencies in `fm-ci/docker/files/python_deps.txt`.
 4. Run `make build` to confirm that images build fine.
 5. Try running some of the images, to check that they work as expected.
 6. Run `make push`, confirm the commands look fine, and follow instructions.
 7. Run `make tag-default` to prepare the `fm-default` image (**DO NOT PUSH**).
 8. Run `make run-default` to check that the `fm-default` image is as expected.
 9. Modify the `versions` section of `fm-ci/config.toml` to:
    - Update the `image` field to contain the new image version,
    - Update the `main_llvm` field according to the `Makefile`.
    - Update the `main_swipl` field according to the `Makefile`.
10. Make an `fm-ci` MR, and use the `CI::same-branch` tag if needed.
    - Set the `CI::same-branch` tag in all non-NOVA MRs.
    - If a NOVA MR is used, set the `CI-skip-proof` tag.
11. When MRs are ready and approved, take an atomic lock, and then:
    - Run `make push-default` and follow instructions like for `make push`.
    - Merge all your non-`fm-ci` MRs.
    - Merge your `fm-ci` MR and confirm that CI passes.
    - Release the atomic lock.

## Public Release Image

The public release image setup is also covered by the `Makefile`. The relevant
targets are: `make build-release`, `make run-release` and `make push-release`.
The latter should in principle not be used directly, since we have a scheduled
job that builds and publishes the image daily. It is however useful to build
and run the release image locally when working on improvements and debugging.

## Packaging the Image as a Tarball

To package the image as `fm-release.tar.gz`:
```sh
make pack-release
```
This will display a progress bar if `pv` is installed.

To load the image, run either `make unpack-release` or
```sh
docker load -i fm-release.tar.gz
```
