# Contents

This tarball contains a binary release of our automation (as a Docker image snashot) images and some demos.

- Have a working Docker and VsCode installation (tested with VsCode 1.97.2).
- Download and unpack `bluerock-fm-demo-$version.tar.gz` (where `$version` is currently `2025-02-25-1`)
- Download and "load" the `fm-release` image --- see instructions below.

## Loading the Docker image

Load it with
```
bluerock-fm-demo-2025-02-25-1$ docker load -i bluerock-fm-release-2025-02-25-1.tar.gz
```
and you should get a Docker image named
`registry.gitlab.com/bedrocksystems/formal-methods/fm-ci:fm-release`.

```
$ docker images
REPOSITORY                                                                     TAG              IMAGE ID       CREATED          SIZE
registry.gitlab.com/bedrocksystems/formal-methods/fm-ci                        fm-release       01c8428c05ed   5 days ago       6.89GB
```


## Demo use instructions

Open the `fm-release-$version` folder with VsCode, then follow the prompts for VS Code to open the directory using the dev container:

![Folder contains a Dev Container configuration file. Reopen folder to develop in a container](<VsCode Prompt 1.png>)

Press "Reopen in Container". Then VsCode will prepare a Docker container for development in the image, based on our Docker image.
The folders with the demo code are shared with the host computer and should be
persisted reliably, while the rest will disappear easily on upgrades.
**Warning**: Do _not_ do important work inside this demo without backups!

You will need to build the demos before you can step through the demos reliably.
Open the VsCode terminal and run `dune build`:

![Running dune in VsCode Terminal](<VsCode Demo.png>)

Then, start walking through demos, for instance from
`rocq-bluerock-cpp-demo/proof/basic/main_cpp_proof.v`, the proof for
`rocq-bluerock-cpp-demo/proof/basic/main.cpp`.

To step through `fm-docs` examples, you will also need to build `fm-docs` via the following command in the same prompt.
```
cd fm-docs; pip3 install -r python_requirements.txt; ./core-build.sh
```

**Warning**: updating the VsCoq extension is not supported.
