#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.

from pathlib import Path
from os import listdir
from os.path import abspath, isabs, isdir, join

ANSI_ESCAPE   = '\033'
ANSI_ENDC     = f'{ANSI_ESCAPE}[0m'
ANSI_BOLD     = f'{ANSI_ESCAPE}[1m'
ANSI_ITALIC   = f'{ANSI_ESCAPE}[3m'
ANSI_RED      = f'{ANSI_ESCAPE}[91m'
ANSI_BOLD_RED = f'{ANSI_ESCAPE}[1;91m'
ANSI_MAGENTA  = f'{ANSI_ESCAPE}[95m'
def format_ansi_msg(msg, ANSI_CODE):
    return f'{ANSI_CODE}{msg}{ANSI_ENDC}'

# v-- cf. https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
def format_hyperlink(hyperlink_open_uri, msg, no_hyperlinks=False):
    if no_hyperlinks: return msg

    # NOTE: we could use the [id] param to cause the code-listings to act as a multiline
    # hyperlink.
    hyperlink_open_params = f''
    hyperlink_open  = f'{ANSI_ESCAPE}]8;{hyperlink_open_params};{hyperlink_open_uri}{ANSI_ESCAPE}\\'
    hyperlink_close = f'{ANSI_ESCAPE}]8;;{ANSI_ESCAPE}\\'

    return f'{hyperlink_open}{msg}{hyperlink_close}'

# v-- cf. https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
def format_file_hyperlink(filename, msg, lineno=None, no_hyperlinks=False):
    hyperlink_open_uri = f'file://{abspath(filename)}' + (f':{lineno}' if lineno else f'')
    return format_hyperlink(hyperlink_open_uri, msg, no_hyperlinks=no_hyperlinks)


# NOTE: helpful BlueRock links:
# - <https://bedrocksystems.atlassian.net/wiki/spaces/EN/pages/584417300/Coq+Style+Guide>
# - <https://bedrocksystems.atlassian.net/wiki/spaces/EN/pages/952565805/Scalable+vSwitch+File+Organization>
# - <https://bedrocksystems.atlassian.net/wiki/spaces/EN/pages/1130332164/vSwitch+File+Reorganization+Instructions#Proof-Artifact-Categories>

COQ_COPYRIGHT = lambda year_str: f"""(*
 * Copyright (C) BlueRock Security, Inc. {year_str}
 *
 * This software is distributed under the terms of the BlueRock Open-Source License.
 * See the LICENSE-BlueRock file in the repository root for details.
 *)"""

COQ_PRELUDE_HIERARCHY = {
    'model': [],
    'ghost': ['model'],
    'defs': ['ghost'],
    'spec': ['defs'],
    'hints': ['defs'],
    'proof': ['spec', 'hints'],
}
COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN = list(COQ_PRELUDE_HIERARCHY.keys())
COQ_PROOF_ARTIFACT_CATEGORIES = COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN + [
    'prelude',
    'upstream',
]
COQ_PROOF_ARTIFACT_CATEGORIES_STRING = (
    '/'.join(
        map(
            lambda target: '[' + target + '(.v)]',
            COQ_PROOF_ARTIFACT_CATEGORIES,
        )
    )
)

def MK_HIERARCHICAL_EXTENSION_STRING_FOR(target, category):
    deps = COQ_PRELUDE_HIERARCHY[category]
    if not deps:
        return 'N/A'

    return ' & '.join(map(lambda dep: f'[{target}/prelude/{dep}.v]', deps))
def MK_HIERARCHICAL_DEPENDENCY_STRING_FOR(target, category):
    deps = COQ_PRELUDE_HIERARCHY[category]
    if not deps:
        return 'N/A'

    return ' & '.join(map(lambda dep: f'[{target}/{dep}.v]', deps))

MK_COQ_PRELUDE_COMMENT_FOR = (lambda target, category: f"""

(** [{target}/prelude/{category}.v] should [Export] the following:
 *  - parent prelude [Export]s: [<PARENT PRELUDE DIR>/{category}.v], if applicable
 *  - prelude [Export]s:        {MK_HIERARCHICAL_EXTENSION_STRING_FOR(target, category)}
 *  - hierarchical [Export]s:   {MK_HIERARCHICAL_DEPENDENCY_STRING_FOR(target, category)}
 *  - dependencies:             any additional dependencies/settings/scopes/etc...
 *)
(** FIXME add missing hierarchical [Export]s if they are available. *)

""")
COQ_PRELUDE_HIERARCHY_COMMENTS_FOR = lambda target: {
    category: MK_COQ_PRELUDE_COMMENT_FOR(target, category)
    for category in COQ_PRELUDE_HIERARCHY.keys()
}
if COQ_PRELUDE_HIERARCHY.keys() != COQ_PRELUDE_HIERARCHY_COMMENTS_FOR('').keys():
    raise RuntimeError(format_ansi_msg(
        'domain mismatch: COQ_PRELUDE_HIERARCHY_COMMENTS & COQ_PRELUDE_HIERARCHY',
        ANSI_RED,
    ))

PROOF_ARTIFACT_CONTENTS_STRINGS = {
    'model': 'operational and/or [Rep] model+theory',
    'ghost': 'ghost predicates and structural instances (not dependent on [work], e.g. [Persistent], [CFracSplittable_XXX], etc...)',
    'defs':  'spatial predicates and structural instances (not dependent on [work], e.g. [Persistent], [CFracSplittable_XXX], etc...)',
    'spec':  'specifications of C++ functions in terms of [model]/[ghost]/[defs]',
    'hints': '[pure]/[br_opacity] hints in terms of [model]/[ghost]/[defs], and non-structural instances',
    'proof': 'correctness proofs for C++ code + "private" proof artifacts',
}
if COQ_PRELUDE_HIERARCHY.keys() != PROOF_ARTIFACT_CONTENTS_STRINGS.keys():
    raise RuntimeError(format_ansi_msg(
        'domain mismatch: PROOF_ARTIFACT_CONTENTS_STRINGS & COQ_PRELUDE_HIERARCHY',
        ANSI_RED,
    ))

MK_COQ_PROOF_ARTIFACT_COMMENT_FOR = (lambda target, category: f"""

(** [{target}/{category}.v] should contain the following:
 *  - hierarchical [Import]s:      [{target}/prelude/{category}.v]
 *  - hierarchical (re-)[Export]s: {MK_HIERARCHICAL_DEPENDENCY_STRING_FOR(target, category)}
 *  - contents:                    {PROOF_ARTIFACT_CONTENTS_STRINGS[category]}
 *)
(** FIXME add missing hierarchical (re-)[Export]s if they are available. *)

""")
COQ_PROOF_ARTIFACT_CATEGORY_COMMENTS_FOR = lambda target: {
    category: MK_COQ_PROOF_ARTIFACT_COMMENT_FOR(target, category)
    for category in COQ_PRELUDE_HIERARCHY.keys()
}
if COQ_PRELUDE_HIERARCHY.keys() != COQ_PROOF_ARTIFACT_CATEGORY_COMMENTS_FOR('').keys():
    raise RuntimeError(format_ansi_msg(
        'domain mismatch: COQ_PROOF_ARTIFACT_CATEGORY_COMMENTS & COQ_PRELUDE_HIERARCHY',
        ANSI_RED,
    ))

def is_coq_file(path):
    return path.suffix == '.v'

# NOTE: must be invoked with a real [dirname]
def enumerate_coq_file_hierarchy(resolved_dirpath):
    hierarchy = {key: set() for key in COQ_PROOF_ARTIFACT_CATEGORIES + ['<UNRECOGNIZED>']}

    for resolved_coq_filepath in resolved_dirpath.rglob('*.v'):
        matched = False

        # Heuristic to determine where [resolved_coq_filepath] maps in the [hierarchy]
        # 1) check whether the file is part of the 'prelude'                                   (fast/common)
        # 2) for part in [<relative dirnames in reverse order> + <filename>]:
        #    a) check if [part in hierarchy.keys()]                                            (fast/common)
        #    b) check whether anything in [hierarchy.keys()] appears as a substring of parts   (slow/uncommon)

        parts = list(resolved_coq_filepath.relative_to(resolved_dirpath).parts)
        resolved_coq_filepath_parts = parts[-2::-1] + [parts[-1]]
        if 'prelude' in resolved_coq_filepath_parts:
            matched = True
            hierarchy['prelude'].add(resolved_coq_filepath)
        else:
            for resolved_coq_filepath_part in resolved_coq_filepath_parts:
                if matched: break

                if resolved_coq_filepath_part in hierarchy.keys():
                    matched = True
                    hierarchy[resolved_coq_filepath_part].add(resolved_coq_filepath)
                else:
                    for proof_artifact_category in hierarchy.keys():
                        if resolved_coq_filepath_part.find(proof_artifact_category) != -1:
                            matched = True
                            hierarchy[proof_artifact_category].add(resolved_coq_filepath)
                            break

        if not matched:
            hierarchy['<UNRECOGNIZED>'].add(resolved_coq_filepath)

    return hierarchy
