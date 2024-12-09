#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.

import argparse
from linter_util import *
from linter import CoqLinter, RuntimeError_PartialLint
from util import *
from os.path import abspath, basename, exists, isfile, isdir, join

DESCRIPTION = f"""
Lint the supplied directories to ensure that the layout/content of the
contained file(s) matches the configured policies. By default a common
policy will be applied which forbids relative imports/exports.

[--proof-dirs]/[--extra-code-proofs] can be supplied if linting based
on the inferred category of proof artifact is desired.
"""

# TODOS:
# - flesh out linters for other proof artifact categories
# - better support for creating/ingesting policies
# - build some policy invariants (i.e. constrain lemma names)

GLOBAL_ALLOW_DENY_POLICY_NO_RESTRICTIONS = mk_allow_deny_policy(
    eager_allow_list=[],
    allow_list=[SentenceMatchers.SENTENCE(FRAGMENTS.ANYTHING)],
    deny_list=[],
)
GLOBAL_ALLOW_DENY_POLICY_COMMON = mk_allow_deny_policy(
    # allow imports/exports (and elpi-[From ... Extra Dependency ... as ...]) ...
    eager_allow_list=[
        SentenceMatchers.IMPORT_NO_FROM,
        SentenceMatchers.EXPORT_NO_FROM,
        SentenceMatchers.ELPI_EXTRA_DEPENDENCY
    ],
    allow_list=[SentenceMatchers.SENTENCE(FRAGMENTS.ANYTHING)],
    # ... but only if they don't use [From]
    deny_list=[
        (SentenceMatchers.IMPORT, err_fmt_prohibited_use_of_from),
        (SentenceMatchers.EXPORT, err_fmt_prohibited_use_of_from),
    ],
)
GENERIC_COQ_LINTER_NO_RESTRICTIONS = CoqLinter(mk_policy(GLOBAL_ALLOW_DENY_POLICY_NO_RESTRICTIONS))
GENERIC_COQ_LINTER_COMMON = CoqLinter(mk_policy(GLOBAL_ALLOW_DENY_POLICY_COMMON))
COQ_LINTERS = {
    'model': GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'ghost': GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'defs':  GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'spec':  GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'hints': GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'proof': CoqLinter(
        mk_policy(
            # extend_allow_deny_policy(
            #     IMPORT_EXPORT_POLICY,
                mk_allow_deny_policy(
                    code_proof_matchers_eager_allow_list,
                    code_proof_matchers_allow_list,
                    code_proof_matchers_deny_list,
                ),
            # ),
            # /-- Allow anything within the body of a proof (so long as it doesn't conflict
            # v   with the toplevel [code_proof_matchers_deny_list]
            proof_policies=mk_allow_deny_policy(
                # /-- NOTE: in the future we many want to prohibit adding/removing hints
                # v   mid-proof.
                eager_allow_list=[
                    SentenceMatchers.REGISTER_HINTS,
                    SentenceMatchers.UNREGISTER_HINTS,
                ],
                allow_list=[SentenceMatchers.SENTENCE(FRAGMENTS.ANYTHING)],
            ),
        )
    ),
    'prelude':  GENERIC_COQ_LINTER_NO_RESTRICTIONS,
    'upstream': GENERIC_COQ_LINTER_NO_RESTRICTIONS,
}
if set(COQ_PROOF_ARTIFACT_CATEGORIES) != COQ_LINTERS.keys():
    msg = format_ansi_msg('domain mismatch: COQ_PROOF_ARTIFACT_CATEGORIES & COQ_LINTERS', ANSI_RED)
    raise RuntimeError(msg)

IMPORT_EXPORT_PASS_CATEGORY = '<IMPORT-EXPORT-PASS>'
# NOTE: we already test that the file exists before we attempt to open it
def lint_coq_file(validated_coq_filepath, category, fail_on_runtime_error=False):
    # v-- NOTE: special-case to support "common" linting which doesn't infer proof artifact category
    if category == IMPORT_EXPORT_PASS_CATEGORY:
        with open(validated_coq_filepath, 'r', encoding='UTF-8') as f:
            # v-- NOTE: simply warn if a file can't be processed
            if fail_on_runtime_error:
                return GENERIC_COQ_LINTER_COMMON.run(f)
            else:
                try:
                    return GENERIC_COQ_LINTER_COMMON.run(f)
                except RuntimeError_PartialLint as e:
                    err_fmt = err_fmt_likely_nested_comment if e.parsing_issue else err_fmt_unknown
                    return e.partial_linting_errors + [(err_fmt(str(e)), -1, -1)]
                except RuntimeError as e:
                    return [(err_fmt_unknown(str(e)), -1, -1)]

    # NOTE: for now we lint every file (and use a trivial allow-anything policy for uncategorized files).
    # In the future we could log the uncategorized files so that we can determine a more specific policy
    # to apply.
    #
    # NOTE: '<UNRECOGNIZED>' should match the sentinel used by [util.py#enumerage_coq_file_hierarchy]
    if category == '<UNRECOGNIZED>':
        with open(validated_coq_filepath, 'r', encoding='UTF-8') as f:
            return GENERIC_COQ_LINTER_NO_RESTRICTIONS.run(f)

    if category not in COQ_PROOF_ARTIFACT_CATEGORIES:
        msg = ' '.join([
            format_ansi_msg('Error:', ANSI_RED),
            f'{category} should be one of {COQ_PROOF_ARTIFACT_CATEGORIES_STRING}.'
        ])
        raise RuntimeError(msg)

    with open(validated_coq_filepath, 'r', encoding='UTF-8') as f:
        return COQ_LINTERS[category].run(f)

COQ_LINT_DISALLOWED_TARGET = 'disallowed_target'
COQ_LINT_CODE_PROOF        = 'code_proof'
def lint_proof_dir(validated_proof_dir):
    coq_file_hierarchy = enumerate_coq_file_hierarchy(validated_proof_dir)
    errors = {}

    for category, resolved_coq_filepaths in coq_file_hierarchy.items():
        for resolved_coq_filepath in resolved_coq_filepaths:
            # NOTE: for now we lint every file (and use a trivial allow-anything policy for uncategorized files).
            # In the future we could log the uncategorized files so that we can determine a more specific policy
            # to apply.
            #
            # if not category in COQ_PROOF_ARTIFACT_CATEGORIES:
            #     errors.setdefault(COQ_LINT_DISALLOWED_TARGET, []).append(resolved_coq_filepath)
            # else:
                coq_lint_errors = lint_coq_file(resolved_coq_filepath, category)
                if coq_lint_errors:
                    errors.setdefault(
                        COQ_LINT_CODE_PROOF,
                        {}
                    )[resolved_coq_filepath] = coq_lint_errors

    return errors

# TODO: port to [pathlib]
def report_code_proof_errors(filename, errors, use_ci_output_format, nested=False):
    if nested:
        header_prefix = '\t+'
        error_newline_replacement = '\n\t\t'
        error_prefix = '\t\t*'
    else:
        header_prefix = '-'
        error_newline_replacement = '\n\t'
        error_prefix = '\t+'

    absolute_filename = abspath(filename)
    print(f'{header_prefix} {format_file_hyperlink(absolute_filename, absolute_filename, no_hyperlinks=use_ci_output_format)}')

    for (error, starting_lineno, ending_lineno) in errors:
        if starting_lineno == ending_lineno:
            line_str = f'line {starting_lineno}'
        else:
            line_str = f'lines {starting_lineno}-{ending_lineno}'
        # v-- make sure the code listing is aligned properly
        formatted_error = error.replace('\n', error_newline_replacement)
        formatted_line_str = format_file_hyperlink(
            absolute_filename,
            line_str,
            lineno=starting_lineno,
            no_hyperlinks=use_ci_output_format,
        )

        print(f'{error_prefix} [{formatted_line_str}] {formatted_error}')

# TODO: port to [pathlib]
def report_proof_dir_errors(resolved_dirpath, errors, use_ci_output_format):
    print(f'- {str(resolved_dirpath)}')

    for disallowed_target in errors.get(COQ_LINT_DISALLOWED_TARGET, []):
        msg = ' '.join([
            f'{format_ansi_msg(disallowed_target.relative_to(resolved_dirpath), ANSI_BOLD)}',
            f'does not clearly fall into one of the supported proof categories:',
            ', '.join(COQ_LINTERS.keys()),
        ])
        print(f'\t+ {msg}')

    for proof_file_name, code_proof_errors in errors.get(COQ_LINT_CODE_PROOF, {}).items():
        report_code_proof_errors(proof_file_name, code_proof_errors, use_ci_output_format, nested=True)

# TODO: consider further tweaks to the output when [use_ci_output_format] is true (e.g. un-batch errors, use standard error/warning prefixes, etc...)
def report_errors(
        missing_targets,
        non_coq_code_proof_files,
        non_dir_proof_dirs,
        non_proof_proof_dirs,
        linting_results,
        use_ci_output_format):
    if (    not missing_targets    and not non_coq_code_proof_files
        and not non_dir_proof_dirs and not non_proof_proof_dirs
        and not linting_results):
        return False

    if missing_targets or non_coq_code_proof_files or non_dir_proof_dirs or non_proof_proof_dirs:
        print(f'{format_ansi_msg("Argument Errors:", ANSI_BOLD)}')

        if missing_targets:
            print('- Missing Targets:')
            for missing_target in missing_targets:
                print(f'\t+ {missing_target}')

        if non_coq_code_proof_files:
            print('- Non-Coq Code Proof Files:')
            for non_coq_code_proof_file in non_coq_code_proof_files:
                print(f'\t+ {non_coq_code_proof_file}')

        if non_dir_proof_dirs:
            print('- Non-Directory "Proof" Directories:')
            for non_dir_proof_dir in non_dir_proof_dirs:
                print(f'\t+ {non_dir_proof_dir}')

        if non_proof_proof_dirs:
            print('- Non-[proof/] "Proof" Directories:')
            for non_proof_proof_dir in non_proof_proof_dirs:
                print(f'\t+ {non_proof_proof_dir}')

    if linting_results:
        print(f'{format_ansi_msg("Linting Errors:", ANSI_BOLD)}')
        for resolved_path, errors in linting_results.items():
            if resolved_path.is_file():
                report_code_proof_errors(resolved_path, errors, use_ci_output_format)
            else:
                report_proof_dir_errors(resolved_path, errors, use_ci_output_format)

    return True

# NOTE: [args] comes from [args = parser.parse_args()] within [main]
def main_infer_categorizations(args):
    missing_targets = []
    non_coq_code_proof_files = []
    non_dir_proof_dirs = []
    non_proof_proof_dirs = []
    linting_results = {}

    validated_code_proof_filepaths = []
    validated_proof_dirpaths = []

    # TODO (JH): check that [relative_proof_dirpath] actually points to a directory ending
    # in [proof/]
    for relative_proof_dirpath in args.proof_dirs or []:
        try:
            resolved_proof_dirpath = relative_proof_dirpath.resolve(strict=True)
        except FileNotFoundError:
            missing_targets.append(str(relative_proof_dirpath))

        if resolved_proof_dirpath.is_dir():
#            if relative_proof_dirpath.parts[-1] != 'proof':
#                non_proof_proof_dirs.append(str(relative_proof_dirpath))
#            else:
                validated_proof_dirpaths.append(resolved_proof_dirpath)
        else:
            non_dir_proof_dirs.append(str(relative_proof_dirpath))

    for relative_code_proof_filepath in args.code_proof_files or []:
        try:
            resolved_code_proof_filepath = relative_code_proof_filepath.resolve(strict=True)
        except FileNotFoundError:
            missing_targets.append(str(relative_code_proof_filepath))

        if is_coq_file(resolved_code_proof_filepath):
            validated_code_proof_filepaths.append(resolved_code_proof_filepath)
        else:
            non_coq_code_proof_files.append(str(relative_code_proof_filepath))

    for validated_proof_dirpath in validated_proof_dirpaths:
        results = lint_proof_dir(validated_proof_dirpath)
        if results:
            linting_results[validated_proof_dirpath] = results

    for validated_code_proof_filepath in validated_code_proof_filepaths:
        results = lint_coq_file(validated_code_proof_filepath, 'proof')
        if errors:
            linting_results[validated_code_proof_filepath] = results

    any_errors = report_errors(
        missing_targets,
        non_coq_code_proof_files,
        non_dir_proof_dirs,
        non_proof_proof_dirs,
        linting_results,
        args.use_ci_output_format,
    )
    return 1 if any_errors else 0

# NOTE: [args] comes from [args = parser.parse_args()] within [main]
def main_common_policy(args):
    unresolved_common_targets      = []
    resolved_common_file_targets   = []
    resolved_common_dir_targets    = []

    # 1) try to resolve all common targets to fully qualified filepaths (partitioning based on
    #    file vs. dir)
    for relative_common_target in args.common_targets:
        try:
            resolved_common_target = relative_common_target.resolve(strict=True)
        except FileNotFoundError:
            unresolved_common_targets.append(str(relative_common_target))
            continue

        if resolved_common_target.is_dir():
            resolved_common_dir_targets.append(resolved_common_target)
        else:
            resolved_common_file_targets.append(resolved_common_target)

    # 2) collect all [.v] files which are (recursively) accessible from
    #    [resolved_common_{file, dir}_targets]
    non_v_file_targets        = []
    resolved_v_file_targets   = []
    # 2.a) ensure that all [resolved_common_file_targets] are coq files
    for resolved_common_file_target in resolved_common_file_targets:
        if is_coq_file(resolved_common_file_target):
            resolved_v_file_targets.append(resolved_common_file_target)
        else:
            non_v_file_targets.append(resolved_common_file_target)
    # 2.b) recursively gather all [.v] files contained within [resolved_common_dir_targets]
    for resolved_common_dir_target in resolved_common_dir_targets:
        resolved_v_file_targets.extend(resolved_common_dir_target.rglob('*.v'))

    # 3) lint all of the [.v] files using the [GLOBAL_ALLOW_DENY_POLICY_COMMON]
    linting_results = {}
    for resolved_v_file_target in resolved_v_file_targets:
        linting_result = lint_coq_file(
            resolved_v_file_target,
            IMPORT_EXPORT_PASS_CATEGORY,
            args.fail_on_runtime_error
        )
        if linting_result:
            linting_results[resolved_v_file_target] = linting_result

    # ) report errors and return
    any_errors = report_errors(
        unresolved_common_targets,
        non_v_file_targets,
        [],
        [],
        linting_results,
        args.use_ci_output_format,
    )
    return 1 if any_errors else 0

def main():
    parser = argparse.ArgumentParser(
        prog=f'{basename(__file__)}',
        description=DESCRIPTION,
    )
    parser.add_argument(
        "common_targets",
        metavar='COMMON_TARGETS',
        type=Path,
        nargs='*',
        help='[.v] files/directories to be linted using the common BedRock policy'
    )
    parser.add_argument(
        '--proof-dirs',
        metavar='PROOF_DIRS',
        type=Path,
        nargs='+',
        dest='proof_dirs',
        help='proof directories to be linted using inferred proof-artifact categories; NO [COMMON_TARGETS]',
    )
    parser.add_argument(
        '--extra-code-proofs',
        metavar='CODE_PROOF_FILES',
        type=Path,
        nargs='+',
        dest='code_proof_files',
        help='lint specific code-proof files in addition to proof directories; NO [COMMON_TARGETS]',
    )
    parser.add_argument(
        '--use-ci-output-format',
        action='store_true',
        dest='use_ci_output_format',
        help='tweak the output format so that it fits better with CI tooling',
    )
    parser.add_argument(
        '--fail-on-runtime-error',
        action='store_true',
        dest='fail_on_runtime_error',
        help='fail if the linter experiences a runtime error',
    )

    args = parser.parse_args()

    any_common_targets = (args.common_targets and args.common_targets != [])
    any_inferred_targets = (
        (args.proof_dirs and args.proof_dirs != []) or
        (args.code_proof_files and args.code_proof_files != [])
    )

    # NOTE: [len(sys.argv) == 1] check ensures that
    if any_common_targets and any_inferred_targets:
        print(fr'If [--proof-dirs] and/or [--extra-code-proofs] are supplied, no unnamed targets may be supplied to [{basename(__file__)}]; this can be relaxed in the future')
    elif any_common_targets:
        return main_common_policy(args)
    elif any_inferred_targets:
        return main_infer_categorizations(args)
    else:
        parser.print_help()
        return 0

if __name__ == "__main__":
    exit(main())
