FM CI Docker Images
===================

## WARNING

Be extremely careful when overwriting existing tags in the gitlab container
registry, as this can obviously break things. You should typically always
push new tags, unless you know exactly what you are doing.

You are strongly advised to look at the source code of `build.sh` to first
understand what it does, before trying to use it.

## Generating New Versions of the CI Images

To generate a new set of CI image, start by updating the `fmdeps_version`
variable in file `build.sh`. Other updates are necessary, but running the
script will tell you what to do.

## Interacting with the GitLab Container Registry

NOTE: In order to actually interact with the gitlab container registry, you'll
need an API token (get this from within the gitlab UI). Then `docker login` as
```
docker login registry.gitlab.com/bedrocksystems -u <your-gitlab-username> --password <your-token>
```

## Build

Run `./build.sh --build` to re-build all images.

## Pushing Tags

Run `./build.sh --push` to push the tags (this implies building).
