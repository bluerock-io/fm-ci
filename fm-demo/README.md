# Packaging fm-demo Instructions

1. Make a Docker release image available at the appropriate release tag, `registry.gitlab.com/bedrocksystems/formal-methods/fm-ci:fm-release`.
You can use `make build-release` or `make pull-release`; refer to `../docker/README.md`.
2. Package that release image with `make pack-release`.
3. Run
```
./sync.sh path/to/fm-demo-folders
```

That will create `path/to/fm-demo-folders/release-name/` and tarball it as `path/to/fm-demo-folders/release-name.tgz`.
