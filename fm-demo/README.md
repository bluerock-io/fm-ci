# Packaging fm-demo Instructions

1. Run a pipeline of "Release of the opam-docker image" from
https://gitlab.com/bedrocksystems/formal-methods/fm-ci/-/pipeline_schedules.
to produce a Docker release image at the appropriate release tag,
`registry.gitlab.com/bedrocksystems/formal-methods/fm-ci:fm-opam-release-latest`.
2. Make a Docker release image available
You can use `make build-release` or `make pull-release`; refer to `../docker/README.md`.
2. Package that release image with `make pack-release`.
3. Run
```
./sync.sh path/to/fm-demo-folders
```

That will create `path/to/fm-demo-folders/release-name/` and tarball it as `path/to/fm-demo-folders/release-name.tgz`.
