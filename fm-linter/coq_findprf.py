#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.

import argparse
from util import *

DESCRIPTION = f"""
For <TARGET_FILEPATH> - a [.hpp] or [.cpp] file - guess where the corresponding proof artifacts reside.
"""

def main():
    parser = argparse.ArgumentParser(
        prog=f'{Path(__file__).name}',
        description=DESCRIPTION,
    )
    parser.add_argument(
        'target_filepath',
        metavar='TARGET_FILEPATH',
        type=Path,
        help='the target [.hpp] or [.cpp] file to locate'
    )

    args = parser.parse_args()
    relative_filepath = args.target_filepath

    if not relative_filepath.match('*.[ch]pp'):
        err_msg = ' '.join([
            format_ansi_msg('Error:', ANSI_RED),
            format_ansi_msg(str(relative_filepath), ANSI_BOLD),
            'does not refer to a [.hpp] or [.cpp] file.'
        ])
        print(err_msg)
        return 1

    try:
        resolved_filepath = relative_filepath.resolve(strict=True)
    except FileNotFoundError:
        err_msg = ' '.join([
            format_ansi_msg('Error:', ANSI_RED),
            format_ansi_msg(str(relative_filepath), ANSI_BOLD),
            'does not exist (or is a symlink).'
        ])
        print(err_msg)
        return 1

    # v-- must match either [.hpp] or [.cpp], due to the previous conditional
    is_hpp = resolved_filepath.match('*.hpp')

    if is_hpp:
        # v-- directory structure is [foo/include/foo/bar.hpp], and we want [foo/]
        relative_dirpath = relative_filepath.parents[2]
        resolved_dirpath = resolved_filepath.parents[2]
    else:
        # v-- directory structure is [foo/src/bar.hpp], and we want [foo/]
        relative_dirpath = relative_filepath.parents[1]
        resolved_dirpath = resolved_filepath.parents[1]

    relative_proof_dirpath = relative_dirpath / 'proof/'
    resolved_proof_dirpath = resolved_dirpath / 'proof/'
    if not resolved_proof_dirpath.is_dir():
        err_msg = ' '.join([
            format_ansi_msg('Error:', ANSI_RED),
            'proof artifacts for',
            format_ansi_msg(str(relative_filepath), ANSI_BOLD),
            'should live in',
            format_ansi_msg(str(relative_proof_dirpath), ANSI_BOLD),
            '(which does not exist).',
        ])
        print (err_msg)
        return 1

    target = resolved_filepath.stem
    patterns = [
        # v-- [.v] files apperaing under a [target/] folder are probably related
        f'proof/**/{target}/**/*',
        f'proof/**/{target}/*',
        f'proof/{target}/**/*',
        f'proof/{target}/*',
        # v-- [.v] files prefixed by [target] are probably related
        f'{target}.v'
        f'{target}_hpp_spec.v',
        f'{target}_cpp_spec.v',
        f'{target}_hpp_proof.v',
        f'{target}_cpp_proof.v',
    ]

    resolved_potentially_related_files = []
    for resolved_proof_filepath in resolved_proof_dirpath.rglob('*.v'):
        for pattern in patterns:
            if resolved_proof_filepath.match(pattern):
                resolved_potentially_related_files.append(resolved_proof_filepath)

    if resolved_potentially_related_files:
        success_msg_prologue = ' '.join([
            format_ansi_msg('Success:', ANSI_BOLD),
            'the following proof artifacts appear related to',
            format_ansi_msg(str(relative_filepath), ANSI_BOLD) + ':',
        ])
        print(success_msg_prologue)

        for resolved_potentially_related_file in resolved_potentially_related_files:
            relative_potentially_related_file = (
                relative_proof_dirpath /
                resolved_potentially_related_file.relative_to(
                    resolved_proof_dirpath
                )
            )
            print(f'- {relative_potentially_related_file}')

        success_msg_epilogue = ' '.join([
            format_ansi_msg('Note:', ANSI_ITALIC),
            'this list is produced heuristically and may miss files or mistakenly list them as related.'
        ])
        print(success_msg_epilogue)

        return 0
    else:
        err_msg = ' '.join([
            format_ansi_msg('Error:', ANSI_RED),
            'no proof artifacts appear related to',
            format_ansi_msg(str(relative_filepath), ANSI_BOLD),
            'within',
            format_ansi_msg(str(relative_proof_dirpath), ANSI_BOLD) + '.',
        ])
        print (err_msg)
        return 1

if __name__ == "__main__":
    exit(main())
