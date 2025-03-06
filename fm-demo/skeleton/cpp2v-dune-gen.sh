#!/bin/bash
#
# Copyright (C) BlueRock Security Inc. 2020-2025
#
# This software is distributed under the terms of the BedRock Open-Source License.
# See the LICENSE-BedRock file in the repository root for details.
#

usage() {
	cat >&2 <<-EOF
		usage: $(basename "$0") [ -t ] <filename>.<ext> <cpp2v-options> -- [ <clang-options> ]

		This will output (to stdout) dune rules for building <filename>.<ext>,
		passing <options> to cpp2v. Redirect output to dune.inc and
		load via dune's include.

		The output is filesystem-independent and <filename>.<ext> need not exist.
		Placing the output in <base>/dune.inc will transform
		<base>/<filename>.<ext> into <base>/<filename>_<ext>.v and
		<base>/<filename>_<ext>_names.v and (with \`-t\`)
		<base>/<filename>_<ext>_templates.v.
	EOF
	exit 1
}

getSystemPaths() {
	local args=()
	while [[ $# -gt 0 ]]; do
		if [[ "$1" =~ ^(-isystem)$ ]]; then
			args+=("${BASH_REMATCH[1]}")
			shift
			args+=("$1")
		elif [[ "$1" =~ ^(-internal.*system.*)$ ]]; then
			args+=("-Xclang")
			args+=("${BASH_REMATCH[1]}")
			shift
			args+=("-Xclang")
			args+=("$1")
		fi
		shift
	done
	echo "${args[@]}"
}

outRule() {
	local indent fullName name ext
	indent="$1"
	fullName="$2"
	shift 2

	# The extension starts at the last dot:
	name="${fullName%.*}"
	if [ "$name" = "$fullName" ]; then
		echo -e "Error: filename '$fullName' has no extension\n" >&2
		usage
	fi
	ext="${fullName##*.}"

	local module="${name}_${ext}.v"
	local names="${name}_${ext}_names.v"
	local targ="${module} ${names}"
	local clang_options=""
	if [ "$system" = 1 ]; then
		clang_options=$(clang++ -### $fullName 2>&1 | grep -Fv '(in-process)' | sed '5q;d')
		clang_options=$(eval getSystemPaths "$clang_options")
	fi
	local cpp2v="cpp2v -v %{input}"
	local core="-o ${module} -names ${names}"

	if [ "$templates" = 1 ]; then
		local templates="${name}_${ext}_templates.v"
		local cmd1="${cpp2v} ${core} --templates=${templates} ${1+ $@} ${clang_options} "
		action="(progn (run ${cmd1}))"
		targ="$targ ${templates}"
	else
		local cmd="${cpp2v} ${core} ${1+ $@} ${clang_options}"
		action="(run ${cmd})"
	fi
	sed "s/^/${indent}/" <<-EOF
		(rule
		 (targets ${targ})
		 (alias test_ast)
		 (deps (:input ${name}.${ext}) (glob_files_rec ../*.hpp))
		 (action
		  ${action}))
		(alias (name srcs) (deps ${name}.${ext}))
	EOF
	# TODO: maybe drop @srcs alias, seems leftover from !2613
}

traverse() {
	local indent path firstDir rest
	indent="$1"
	path="$2"
	shift 2
	firstDir="${path%%/*}"
	rest="${path#*/}"
	if [ "$firstDir" = "$path" ]; then
		outRule "$indent" "$path" "$@"
	elif [ "$firstDir" = "." ]; then
		traverse "$indent" "$rest" "$@"
	else
		#echo DIR $firstDir
		#echo REST $rest
		echo "${indent}(subdir ${firstDir}"
		(cd "${firstDir}"; traverse " $indent" "$rest" "$@")
		echo "${indent})"
	fi
}

templates=0
system=0
while :
do
	case "$1" in
	-t)
		templates=1
		shift
		;;
	-s)
		system=1
		shift
		;;
	--)
		shift
		break
		;;
	-*)
		usage
		;;
	*)
		break
		;;
	esac
done
[ $# -ge 1 ] || usage

path="$1"
shift

traverse "" "$path" "$@"

# vim:set noet sw=8:
