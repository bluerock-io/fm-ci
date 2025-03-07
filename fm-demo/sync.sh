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
target_dir_name=bluerock-fm-demo-${release_ver}
target=${target_parent}/${target_dir_name}
target_tarball=${target}.tar.gz
echo ">>> Assembling release ${release_ver} in path ${target} and tarball ${target_tarball}"

mkdir -p ${target}

# Sync our skeleton, and preserve demos
# Getting ${exclusions} correct is optional but reduces noise/extra work when rerunning the script
exclusions="--exclude rocq-bluerock-cpp-demo --exclude rocq-bluerock-cpp-stdlib --exclude flags --exclude fm-docs --exclude docker --exclude ${docker_name}"
rsync -avc --delete ${exclusions} $PWD/skeleton/ ${target}/ "$@"

rsync -av ${docker_path}/${docker_name} ${target}/ "$@"

cd ${target}

# Regenerate dune.inc files
make -C ${BHV}/fmdeps/cpp2v clean -sj
make -C ${BHV}/fmdeps/cpp2v ast-prepare -sj

# Package our demos
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/rocq-bluerock-cpp-demo . "$@"
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/rocq-bluerock-cpp-stdlib . "$@"
rsync -avc --delete --delete-excluded ${BHV}/fmdeps/cpp2v/flags/ flags/ "$@"
rsync -avc --delete --delete-excluded --exclude .git ${BHV}/fmdeps/fm-docs/ fm-docs/ "$@"
ln -sf ../../cpp2v-dune-gen.sh rocq-bluerock-cpp-demo/proof/
ln -sf ../../cpp2v-dune-gen.sh rocq-bluerock-cpp-stdlib/theories/

cd ${target_parent}
time tar czf ${target_tarball} ${target_dir_name}
