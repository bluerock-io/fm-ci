# BlueRock Security Formal Verification Tooling

This tarball contains a binary release of the BlueRock formal verification tools for verifying C++.

## License
The image is provided for **evaluation purposes** only. It may not be re-distributed.
Use of this image for production software is requires a separate license from BlueRock.
Contact [support@bluerock.io](mailto:support@bluerock.io).

## Requirements
- Docker
- VsCode

## Quick Start

After extracting this file, run the following from this directory.

```sh
docker load -i bluerock-fm-release-2025-05-08.tar.gz
code . &
```

The first of these commands may take a few minutes.

Once inside VsCode, follow the prompts to open the directory using the dev container.
This may take a few minutes the first time that you do it.

![Folder contains a Dev Container configuration file. Reopen folder to develop in a container](<VsCode Prompt 1.png>)

Press "Reopen in Container". Then VsCode will prepare a Docker container for development in the image, based on our Docker image; this might take a few minutes.

The folders with the demo code are shared with the host computer and should be
persisted reliably, while the rest will disappear easily on upgrades.
**Warning**: Do _not_ do important work inside this demo without backups!

**Warning**: updating the VsCoq extension is not supported.

## The Contents of the Image

The image contains the following:
- `rocq-bluerock-cpp-demo` example files demonstrating various features of the system
- `rocq-bluerock-cpp-stdlib` specifications of the libc++ standard library
- `fm-docs/sphinx/_build/html/` documentation

## First Example

We suggest reading bits of the documentation if you are not familiar with separation
logic. When you're ready to explore the examples, we recommend getting started with
`rocq-bluerock-cpp-demo/proof/basic/main_cpp_proof.v` which contains some proofs of
particularly simple C++ functions.

### Stepping through fm-docs

To step through `fm-docs` examples, you might also need to (re)build `fm-docs` via the following command in the same prompt.
```
cd fm-docs; ./core-build.sh
```

## Experiment on Your Own

The easiest way to experiment with your own code is to create a new directory in
`rocq-bluerock-cpp-demo/proof` and to put your code inside of it. Note that the demo
infrastructure is not set up to pass special command line options to the BlueRock
tools, but you can use the standard library.

After you do this, you need to re-generate the build setup by running:

```sh
rocq-bluerock-cpp-demo/proof$ ./dune-gen.sh
rocq-bluerock-cpp-demo/proof$ dune b
```

This script will create build infrastructure to automatically build any .cpp or .hpp files
under the proof directory. In general, you need to run `dune-gen.sh` whenever you add or
remove C++ files.

To import the file, we recommend copying one of the existing Rocq files (with a .v extension)
and using it as a template. To get access to your code, you will need to modify the
`Require Import bluerock.cpp.demo.xxx.yyy` line so that `xxx.yyy` corresponds to the C++ file
that you want to work on. For example, if you create the file `proof/testing/test.cpp`, then you
would use `Require Import bluerock.cpp.demo.testing.test_cpp.`.

## Reporting Bugs

If you run into issues or questions, please reach out!
