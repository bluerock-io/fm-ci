#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.
from datetime import datetime
from enum import Enum
from functools import reduce
import operator
from pathlib import Path
from util import *

# construct/display/execute plans for building hierarchies of Coq files
# based on [COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN]
#
# NOTE: plans are of the form:
# [[[
# PLAN := {
#   <PATH>: {
#     'exists': <PATH exists?>,
#     'is_file': <PATH.is_file()>
#     'children': <RECURSE PLAN or None>
#   }
# }
# ]]]
class CoqHierarchyPlan:
    def __init__(self,
                 relative_dirpath_prf,
                 target_name,
                 excluded_hierarchy,
                 relative_dirpath_parent_prelude):
        self._relative_dirpath_prf            = relative_dirpath_prf
        self._target_name                     = target_name
        self._excluded_hierarchy              = excluded_hierarchy
        self._relative_dirpath_parent_prelude = relative_dirpath_parent_prelude

        self._resolved_dirpath_prf    = self._relative_dirpath_prf.resolve()
        self._resolved_dirpath_target = self._resolved_dirpath_prf / (self._target_name + '/')
        self._resolved_dirpath_target_prelude = (
            self._resolved_dirpath_prf / (self._target_name + '/prelude/')
        )
        if (self._target_name.endswith('_hpp') or self._target_name.endswith('_cpp')):
            self._resolved_filepath_targets = [
                self._resolved_dirpath_prf / (self._target_name + '_spec.v'),
                self._resolved_dirpath_prf / (self._target_name + '_proof.v'),
            ]
        else:
            self._resolved_filepath_targets = [
                self._resolved_dirpath_prf / (self._target_name + '.v'),
            ]

        self._plan = None

    def has_plan(self):
        return bool(self._plan)

    def mk_plan_node(exists, is_file, children):
        return {
            'exists': exists,
            'is_file': is_file,
            'children': children,
        }

    def over_hierarchy(self, f_process, ignore_filter=False):
        return reduce(
            operator.__or__,
            map(
                lambda name: f_process(name + '.v'),
                [nm
                 for nm in COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN
                 if ignore_filter or nm not in self._excluded_hierarchy],
            ),
        )

    def display_plan_prefix(depth):
        if depth == 0:
            return '+'
        elif depth == 1:
            return '|-'
        else:
            return '|' + ('\t' * (depth - 1)) + '|-'

    def display_hierarchy_plan_aux(self, resolved_dirpath, info, depth=0):
        exists   = info['exists']
        children = info['children']

        relative_dirpath = (
            self._relative_dirpath_prf / resolved_dirpath.relative_to(self._resolved_dirpath_prf)
        )
        exists_msg = (
            f'{format_ansi_msg("(exists)", ANSI_BOLD)}' if exists else
            f'{format_ansi_msg("(new)", ANSI_BOLD_RED)}'
        )

        print(' '.join([
            CoqHierarchyPlan.display_plan_prefix(depth),
            str(relative_dirpath),
            exists_msg,
        ]))

        for resolved_dirpath_child, info_child in (children or dict()).items():
            self.display_hierarchy_plan_aux(resolved_dirpath_child, info_child, depth+1)

    def display_hierarchy_plan(self):
        for dirpath, info in self._plan.items():
            self.display_hierarchy_plan_aux(dirpath, info)

    def compute_hierarchy_plan(self):
        def process_for(resolved_dirpath):
            def process(target_name):
                resolved_filepath_target = resolved_dirpath / target_name

                return {
                    resolved_filepath_target: CoqHierarchyPlan.mk_plan_node(
                        resolved_filepath_target.is_file(),
                        True,
                        None,
                    )
                }

            return process

        self._plan = {
            self._resolved_dirpath_prf: CoqHierarchyPlan.mk_plan_node(
                self._resolved_dirpath_prf.is_dir(),
                False,
                dict(),
            )
        }

        children = self._plan[self._resolved_dirpath_prf]['children']
        children |= {
            resolved_filepath_target: CoqHierarchyPlan.mk_plan_node(
                resolved_filepath_target.is_file(),
                True,
                None
            )
            for resolved_filepath_target in self._resolved_filepath_targets
        }
        children |= {
            self._resolved_dirpath_target: CoqHierarchyPlan.mk_plan_node(
                self._resolved_dirpath_target.is_dir(),
                False,
                self.over_hierarchy(process_for(self._resolved_dirpath_target)) | {
                    self._resolved_dirpath_target_prelude: CoqHierarchyPlan.mk_plan_node(
                        self._resolved_dirpath_target_prelude.is_dir(),
                        False,
                        self.over_hierarchy(
                            process_for(self._resolved_dirpath_target_prelude),
                            # v-- NOTE: we want to include prelude files for the full hierarchy
                            ignore_filter=True,
                        )
                    )
                }
            )
        }

    # TODOS (JH):
    # - modify [generate_dependency_sentences] s.t. the prelude exports the appropriate
    #   non-prelude files (according to the [COQ_PRELUDE_HERARCHY] and [self._excluded_hierarchy]).
    # - modify [generate_dependency_sentences] s.t. it returns a triple of the form:
    #   [[[
    #   (<PARENT PRELUDE DEP>, <HIERARCHICAL PRELUDE DEPS>, <HIERARCHICAL FILE DEPS>)
    #   ]]]
    #   where:
    #   + <PARENT PRELUDE DEP>: if [self._relative_dirpath_parent_prelude], an export
    #     of the same prelude file from the parent prelude.
    #   + <HIERARCHICAL PRELUDE DEPS>: exports of the hierarchical prelude dependencies
    #     from this prelude.
    #   + <HIERARCHICAL FILE DEPS>: exports of hierarchical files if they exist
    #
    # NOTE: we ensure that all of the prelude files exist in the local [prelude/]
    # /and/ the parent prelude
    def generate_dependency_sentences(self, resolved_path):
        filename = resolved_path.stem
        is_prelude_file = resolved_path.match('prelude/*.v')
        relative_dirpath_target = self._relative_dirpath_prf / self._target_name
        local_dep_prefix = '.'.join(relative_dirpath_target.parts)

        dependency_sentences = []

        if is_prelude_file:
            for dep_filename in COQ_PRELUDE_HIERARCHY[filename]:
                local_prelude_dependency = '.'.join([local_dep_prefix, 'prelude', dep_filename])
                dependency_sentences.append(' '.join([
                    'Require Export',
                    local_prelude_dependency,
                ]) + '.\n')

            if self._relative_dirpath_parent_prelude:
                parent_dep_prefix = '.'.join(
                    # NOTE: drop the trailing [prelude/] -----v
                    self._relative_dirpath_parent_prelude.parents[0].parts
                )
                parent_prelude_dependency = '.'.join([parent_dep_prefix, 'prelude', filename])
                dependency_sentences.append(' '.join([
                    'Require Export',
                    parent_prelude_dependency,
                ]) + '.\n')
        else: # a regular [TARGET.v]/[TARGET/XXX.v] file, not a [TARGET/prelude/XXX.v] file
            # NOTE: it might be possible to autogenerate imports for other files
            if filename in COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN:
                local_prelude_dependency = '.'.join([local_dep_prefix, 'prelude', filename])
                dependency_sentences.append(' '.join([
                    'Require Import',
                    local_prelude_dependency,
                ]) + '.\n')

        return dependency_sentences

    def populate_file_help_comment(self, resolved_path):
        filename = resolved_path.stem
        if filename in COQ_PROOF_ARTIFACT_CATEGORIES_AUTOGEN:
            is_prelude_file = resolved_path.match('prelude/*.v')

            if is_prelude_file:
                return COQ_PRELUDE_HIERARCHY_COMMENTS_FOR(self._target_name)[filename]
            else:
                return COQ_PROOF_ARTIFACT_CATEGORY_COMMENTS_FOR(self._target_name)[filename]
        else:
            return ''

    def populate_file(self, resolved_path):
        with resolved_path.open('w', encoding='UTF-8') as f:
            f.write(COQ_COPYRIGHT(datetime.now().year))
            f.write(self.populate_file_help_comment(resolved_path))

            dependencies = self.generate_dependency_sentences(resolved_path)
            for dependency in dependencies:
                f.write(dependency)

    def execute_hierarchy_plan_aux(self, resolved_path, info):
        if not info['exists']:
            if info['is_file']:
                self.populate_file(resolved_path)
            else: # is_dir
                resolved_path.mkdir()

        if info['children']:
            for resolved_child_path, child_info in info['children'].items():
                self.execute_hierarchy_plan_aux(resolved_child_path, child_info)

    def execute_hierarchy_plan(self):
        if not self.has_plan():
            raise RuntimeError(
                '[execute_hierarchy_plan] should be executed after [compute_hierarchy_plan]'
            )

        for resolved_path, info in self._plan.items():
            self.execute_hierarchy_plan_aux(resolved_path, info)

class CoqHierarchyBuilder:
    def __init__(self,
                 relative_dirpath_prf,
                 target_name,
                 excluded_hierarchy,
                 relative_parent_prelude):

        self._hierarchy_plan = CoqHierarchyPlan(
            relative_dirpath_prf,
            target_name,
            excluded_hierarchy,
            relative_parent_prelude,
        )

    def run(self, execute):
        self._hierarchy_plan.compute_hierarchy_plan()

        if execute:
            self._hierarchy_plan.execute_hierarchy_plan()
        else:
            if not self._hierarchy_plan.has_plan():
                print(f'{format_ansi_msg("No new files will be created.", ANSI_BOLD)}')
            else:
                msg = format_ansi_msg(
                    'The new files from the following hierarchy will be created:',
                    ANSI_BOLD,
                )
                print(msg)
                self._hierarchy_plan.display_hierarchy_plan()

        return 0
