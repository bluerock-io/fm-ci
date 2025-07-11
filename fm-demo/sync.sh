#!/bin/sh -vxe

# "Configuration"
BHV=$(realpath $PWD/../../../)
docker_path=$PWD/../docker

usage() {
  echo ""
}
if [ $# -lt 1 ]; then
  usage
  exit 1
fi

cd $(dirname "$0")
target_parent="$1"
shift

{
  cd ${docker_path};
  release_ver=$(make ver-release);
  cd - > /dev/null;
}

docker_name=bluerock-fm-release-${release_ver}.tar.gz
docker_target_name=bluerock-fm-release.tar.gz
target_dir_name=bluerock-fm-demo-${release_ver}
target=${target_parent}/${target_dir_name}
target_tarball=${target}.tar.gz
echo ">>> Assembling release ${release_ver} in path ${target} and tarball ${target_tarball}"

mkdir -p ${target}

# Sync our skeleton, and preserve demos
# Getting ${exclusions} correct is optional but reduces noise/extra work when rerunning the script
exclusions="--exclude rocq-bluerock-cpp-demo --exclude rocq-bluerock-cpp-stdlib --exclude flags --exclude fm-docs --exclude docker --exclude ${docker_target_name} --exclude _build"
rsync -avc --delete ${exclusions} $PWD/skeleton/ ${target}/ "$@"


cd ${target}
rsync -av ${docker_path}/${docker_name} ${target}/${docker_target_name} "$@"

# Regenerate dune.inc files
make -C ${BHV}/fmdeps/cpp2v clean -sj
make -C ${BHV}/fmdeps/cpp2v ast-prepare -sj

# Package our demos
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/rocq-bluerock-cpp-demo . "$@"
#rsync -avc --delete --delete-excluded --exclude theories ${BHV}/fmdeps/cpp2v/rocq-bluerock-cpp-stdlib . "$@"
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/rocq-bluerock-cpp-stdlib . "$@"
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/flags/ flags/ "$@"
rsync -avc --delete --delete-excluded --exclude .git ${BHV}/fmdeps/fm-docs/ fm-docs/ "$@"
ln -sf ../../cpp2v-dune-gen.sh rocq-bluerock-cpp-demo/proof/
ln -sf ../../cpp2v-dune-gen.sh rocq-bluerock-cpp-stdlib/theories/
ln -sf ../../cpp2v-dune-gen.sh rocq-bluerock-cpp-stdlib/tests/

cat ${BHV}/fmdeps/fm-ci/fm-demo/_CoqProject.flags > _CoqProject
echo >> _CoqProject
${BHV}/support/gather-coq-paths.py `find . -name dune` >> _CoqProject

# Tag for docker image
img_name=registry.gitlab.com/bedrocksystems/formal-methods/fm-ci:fm-release
# Path inside container -- chosen to match VsCode one
demo_mount_point=/workspaces/${target_dir_name}
docker run -v ${target}:${demo_mount_point} --rm -it ${img_name} bash -l -c \
       "cd ${demo_mount_point}; dune build; cd fm-docs; ./core-build.sh"
# Copy fm-docs output back to source, so we won't erase it at next pass.
rsync -avc fm-docs/ ${BHV}/fmdeps/fm-docs/ "$@"

cd ${target_parent}
time tar czf ${target_tarball} ${target_dir_name}
