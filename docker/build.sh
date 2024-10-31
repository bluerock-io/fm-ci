#!/bin/sh -e

fmdeps_version=2024-11-01
llvm_versions="16 17 18 19"

echo "READ THE SOURCE TO USE"

grep "$fmdeps_version" Dockerfile-fm-base > /dev/null ||
  (echo "Error: BR_FM_DEPS_VERSION should be $fmdeps_version in Dockerfile-fm-base."; exit 1)

grep "fm-base-$fmdeps_version" Dockerfile-fm-llvm > /dev/null ||
  (echo "Error: FROM image tag should be fm-base-$fmdeps_version in Dockerfile-fm-llvm."; exit 1)

dune build ../fm-deps/br-fm-deps.opam
cp ../fm-deps/br-fm-deps.opam files/br-fm-deps.opam

prefix=registry.gitlab.com/bedrocksystems/docker-image
docker_args=""
# For use on our server
#docker_args="-H unix:///var/run/docker-system.sock"

unset do_pull
unset do_build
unset do_push

usage() {
	cat <<-EOF
		$0 [-h] [--pull] [--build] [--push]

		--push implies --build.
		--pull is separate.
	EOF
	exit 1
}

while :; do
	case "$1" in
		-h)
			usage;;
		--pull)
			do_pull=1
			shift;;
		--build)
			do_build=1
			shift;;
		--push)
			do_push=1
			do_build=1
			shift;;
		--)
			shift; break;;
		*)
			break;;
	esac
done

mydocker() {
	docker $docker_args "$@"
}

# Because I seldom need to re-run the full build.
build() {
	echo "Step:	docker build" "$@"
	[ -z "$do_build" ] && return
	mydocker build "$@"
}
push() {
	echo "Step:	docker push $1"
	[ -z "$do_push" ] && return
	mydocker push "$1"
}

if [ -n "$do_pull" ]; then
	mydocker pull debian:bookworm
fi

build --pull -t ${prefix}:fm-base-${fmdeps_version} -f Dockerfile-fm-base . &&
	push ${prefix}:fm-base-${fmdeps_version} || exit 1

for llvm_ver in ${llvm_versions}; do
	build --build-arg LLVM_MAJ_VER=${llvm_ver} \
		-t ${prefix}:fm-llvm${llvm_ver}-${fmdeps_version} -f Dockerfile-fm-llvm . &&
		push ${prefix}:fm-llvm${llvm_ver}-${fmdeps_version} || exit 1
done
