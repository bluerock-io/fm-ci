#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.

import argparse
from coq_hierarchy_builder import *

DESCRIPTION = f"""
For <TARGET>, prepopulate the supplied [proof/] directory with the following files (matching the {format_hyperlink(SCALABLE_FILE_ORGANIZATION_GUIDE_URI, 'Scalable (vSwitch) File Organization')}).
"""

def main():
    parser = argparse.ArgumentParser(
        prog=f'{Path(__file__).name}',
        description=DESCRIPTION,
    )
    parser.add_argument(
        'dirpath_prf',
        metavar='DIRPATH_PROOF',
        type=Path,
        default='.',
        help='the target proof directory',
    )
    parser.add_argument(
        'target_name',
        metavar='TARGET_NAME',
        type=str,
        help='the target name for Coq file hierarchy generation within DIRPATH_PROOF'
    )
    parser.add_argument(
        '--exclude-hierarchy',
        dest='excluded_hierarchy',
        metavar='EXCLUDED_HIERARCHY',
        type=str,
        default=list(),
        nargs='+',
        choices=COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN,
        help='the portions of the coq file hierarchy to exclude',
    )
    parser.add_argument(
        '--parent-prelude',
        dest='dirpath_parent_prelude',
        metavar='PARENT_PRELUDE_DIRPATH',
        type=Path,
        default=None,
        help='the prelude that should be used by generated prelude files'
    )
    parser.add_argument(
        '--execute',
        dest='execute',
        action='store_true',
        help='display the file-prepopulation plan without modifying the filesystem',
    )

    args = parser.parse_args()

    # If TARGET_NAME contains a period, the Coq module names get complicated.
    if '.' in args.target_name:
        raise ValueError("TARGET argument cannot contain a period.")

    # ensure that if [args.dirpath_parent_prelude] is supplied, it corresponds to an
    # actual [prelude/] subdirectory containing [.v] files for all [COQ_PRELUDE_HIERARHY.keys()]
    if args.dirpath_parent_prelude:
        if args.dirpath_parent_prelude.parts[-1] != 'prelude':
            err_msg = ' '.join([
                format_ansi_msg('Error:', ANSI_RED),
                str(args.dirpath_parent_prelude),
                'does not refer to a [prelude/] directory.'
            ])
            print(err_msg)
            return 1

        parent_prelude_filenames = [
            relative_prelude_filepath.stem
            for relative_prelude_filepath in args.dirpath_parent_prelude.iterdir()
            if relative_prelude_filepath.is_file()
        ]
        missing_prelude_files = []
        for prelude_filename in COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN:
            if prelude_filename not in parent_prelude_filenames:
                missing_prelude_files.append(prelude_filename)

        if missing_prelude_files:
            err_msg = ' '.join([
                format_ansi_msg('Error:', ANSI_RED),
                'the following files are missing from',
                str(args.dirpath_parent_prelude) + ':',
                missing_prelude_files
            ])
            print(err_msg)
            return 1

    return CoqHierarchyBuilder(
        args.dirpath_prf,
        args.target_name,
        args.excluded_hierarchy,
        args.dirpath_parent_prelude,
    ).run(args.execute)

if __name__ == "__main__":
    exit(main())
