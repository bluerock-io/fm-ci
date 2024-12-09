#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.
from copy import deepcopy
from coq_regexes import *
from util import format_ansi_msg, ANSI_RED, ANSI_MAGENTA

# TODOS:
# - hyperlink errors
# - use standard coq error format

def ERR_FMT(msg, ANSI_COLOR=ANSI_RED):
    def callback(sentence):
        formatted_sentence = sentence.replace('\n', '\n|')
        return f'{format_ansi_msg(msg + ":", ANSI_COLOR)}\n|{formatted_sentence}'

    return callback

def err_fmt_missing_proof_begin(lemma_nm, sentence):
    return ERR_FMT(f'Expected [Proof] line for [{lemma_nm}] but found')(sentence)
err_fmt_prohibited_use_of_from   = ERR_FMT(f'The [From] keyword should not be used; prefer fully qualified [Import]s/[Export]s')
err_fmt_set_outside_prelude      = ERR_FMT(f'Flags should be set in a prelude file')
err_fmt_open_outside_prelude     = ERR_FMT(f'Scopes should be opened in a prelude file')
err_fmt_close_outside_prelude    = ERR_FMT(f'Scopes should be closed in a prelude file')
err_fmt_specify_upstream         = ERR_FMT(f'[Specify] this function upstream')
err_fmt_derive_upstream          = ERR_FMT(f'Upstream this [derive] clause')
err_fmt_definition_upstream      = ERR_FMT(f'Upstream this [Definition]')
err_fmt_instance_upstream        = ERR_FMT(f'Upstream this [Instance]')
err_fmt_inductive_upstream       = ERR_FMT(f'Upstream this [Inductive] or [Variant]')
err_fmt_ltac_upstream            = ERR_FMT(f'Upstream this [Ltac]')
err_fmt_implicit_types_upstream  = ERR_FMT(
    f'If this [Implicit Types] is needed, declare in a prelude file'
)
err_fmt_hint_outside_hint_module = ERR_FMT(f'Hints should be [#[export]]ed from some hint module')
err_fmt_unwanted_hint            = ERR_FMT(f'If hints aren\'t used they shouldn\'t be imported')
err_fmt_non_spec_ok_proof        = ERR_FMT(
    f'Code proof files should only contain C++ code proofs; upstream this'
)
def err_fmt_spec_ok_name_mismatch(lhs_spec_nm, rhs_spec_nm, sentence):
    return ERR_FMT(
        f'The lemma should be named [{rhs_spec_nm}_ok] rather than [{lhs_spec_nm}_ok]'
    )(sentence)
err_fmt_unknown = ERR_FMT(f'the linting policy needs to be extended', ANSI_MAGENTA)
err_fmt_likely_nested_comment = ERR_FMT(f'the sentence and/or file likely contains a nested comment (which the regex-based parser can not handle)', ANSI_MAGENTA)

# extend [base_policy] with [policy_extensions] - failing if there are conflicting
# allow/deny policies (permissible overrides: eager allow -> deny -> allow) and otherwise
# preferring the [policy_extensions]
def extend_allow_deny_policy(base_policy, policy_extensions):
    extended_policy = deepcopy(base_policy)

    # Policy extension pseudocode:
    # 1) extend allow (and fail if the [SentenceMatcher] appears in the "eager allow" or "deny" lists)
    # 2) extend deny and prune allow (and fail if the [SentenceMatcher] appears in the "eager allow" list)
    # 3) extend eager allow and prune deny/allow
    # 4) extend other policy options
    #
    # NOTE: we can't easily check whether a more specific [SentenceMatcher] is used; hopefully this won't
    # matter too much if we expose an interface of curated policies to clients (like [clang-tidy]/[clang-format])

    # 1) extend allow
    for allowed in policy_extensions['allow_list']:
        if allowed in extended_policy['eager_allow_list'] or list(filter(lambda df: allowed is df[0], extended_policy['deny_list'])) != []:
            raise RuntimeError(f'attempting to override deny or eager-allow list with allow regex: {allowed}')
        else:
            if allowed not in extended_policy['allow_list']:
                extended_policy['allow_list'].append(allowed)

    # 2) extend deny and prune allow
    for deny, fmt in policy_extensions['deny_list']:
        if deny in extended_policy['eager_allow_list']:
            raise RuntimeError(f'attempting to override eager-allow list with deny regex: {deny}')
        else:
            if deny in extended_policy['allow_list']:
                extended_policy['allow_list'].remove(deny)

            existing_deny_policy = False
            for i in range(len(extended_policy['deny_list'])):
                tmp_deny, tmp_fmt = extended_policy['deny_list'][i]
                if deny is tmp_deny:
                    existing_deny_policy = True
                    extended_policy['deny_list'][i] = (deny, fmt)
            if not existing_deny_policy:
                extended_policy['deny_list'].append((deny, fmt))

    # 3) extend eager-allow and prune deny/allow
    for eager_allow in policy_extensions['eager_allow_list']:
        if eager_allow in extended_policy['allow_list']:
            extended_policy['allow_list'].remove(eager_allow)

        # NOTE: important to iterate in reverse order so that we can safely
        # [del] the indices.
        for i in range(len(extended_policy['deny_list']))[::-1]:
            deny, fmt = extended_policy['deny_list'][i]
            if eager_allow is deny:
                del extended_policy['deny_list'][i]

        if eager_allow not in extended_policy['eager_allow_list']:
            extended_policy['eager_allow_list'].append(eager_allow)

    # 4) extend other policy options
    for policy_nm in (policy_extensions.keys() - mk_allow_deny_policy().keys()):
        extended_policy[policy_nm] = policy_extensions[policy_nm]

    return extended_policy

def mk_allow_deny_policy(eager_allow_list=[],allow_list=[], deny_list=[]):
    return {
        'eager_allow_list': eager_allow_list,
        'allow_list': allow_list,
        'deny_list':  deny_list,
    }

# TODO (JH): if all policies are created using [mk_policy] then the linter only
# needs to check the most specific policy.
# NOTE: provides some defaults for the various policies which can be overwritten
def mk_policy(
        global_policies,
        section_policies=dict(),
        module_type_policies=dict(),
        module_policies=dict(),
        nes_policies=dict(),
        proof_policies=dict(),
):
    global_policies = mk_allow_deny_policy() | {'depth': 5} | global_policies
    section_policies = extend_allow_deny_policy(
        global_policies,
        mk_allow_deny_policy() | {'depth': 3} | section_policies,
    )
    module_type_policies = extend_allow_deny_policy(
        global_policies,
        mk_allow_deny_policy() | {'depth': 3} | module_type_policies,
    )
    module_policies = extend_allow_deny_policy(
        global_policies,
        mk_allow_deny_policy() | {'depth': 3} | module_policies,
    )
    nes_policies = extend_allow_deny_policy(
        global_policies,
        mk_allow_deny_policy() | {'depth': 5} | nes_policies,
    )
    proof_policies = extend_allow_deny_policy(
        global_policies,
        mk_allow_deny_policy() | {'depth': 1} | proof_policies,
    )

    return {
        'global_policies':      global_policies,
        'section_policies':     section_policies,
        'module_type_policies': module_type_policies,
        'module_policies':      module_policies,
        'nes_policies':         nes_policies,
        'proof_policies':       proof_policies,
    }
def validate_policy_shape(policy):
    reference_policy =  mk_policy(mk_allow_deny_policy())

    for subpolicy_nm, reference_subpolicy in reference_policy.items():
        if subpolicy_nm not in policy:
            msg = ' '.join([
                format_ansi_msg(subpolicy_nm, ANSI_BOLD),
                'unrecognized; should be one of',
                ', '.join(reference_policy.keys()) + '.'
            ])
            raise RuntimeError(msg)

        # v-- TODO: consider checking the types within the [subpolicy]
        subpolicy = policy[subpolicy_nm]
        if subpolicy.keys() != reference_subpolicy.keys():
            msg = ' '.join([
                'subpolicy',
                format_ansi_msg(subpolicy_nm, ANSI_BOLD),
                'contains a different set of keys',
                '(' + ', '.join(subpolicy.keys()) + ')',
                'than the reference policy',
                '(' + ', '.join(reference_subpolicy.keys()) + ').'
            ])
            raise RuntimeError(msg)


# NOTE: the following [SentenceMatchers] are handled specially:
# - PROOF_BEGIN/PROOF_END (when the proof is not a oneliner)
# - NEST_BEGIN{_LOCAL_HINTS}/NEST_END
# - SPEC_OK_STATEMENT

code_proof_matchers_eager_allow_list = [
    SentenceMatchers.LOCAL_NOTATION,
    SentenceMatchers.LOCAL_REGISTER_HINTS,
    SentenceMatchers.LOCAL_SET_BR_WORK_TIMEOUT,
]

code_proof_matchers_allow_list = [
    SentenceMatchers.IMPORT,
    SentenceMatchers.EXPORT,
    SentenceMatchers.INCLUDE,
    SentenceMatchers.CONTEXT,
    SentenceMatchers.NES_OPEN,
    SentenceMatchers.IMPLICIT_TYPES,
    # /-- NOTE: allow proof files to override pieces of [Ltac] w/[idtac] - which
    # v   is sometimes necessary for performance.
    SentenceMatchers.LTAC_OVERRIDE_W_IDTAC,
]

# TODO (JH): Determine when - if ever - we want to allow these in code-proof files.
code_proof_matchers_deny_list = [
    (SentenceMatchers.SET,                  err_fmt_set_outside_prelude),
    (SentenceMatchers.OPEN,                 err_fmt_open_outside_prelude),
    (SentenceMatchers.CLOSE,                err_fmt_close_outside_prelude),
    (SentenceMatchers.SPECIFY,              err_fmt_specify_upstream),
    (SentenceMatchers.DEFINITION,           err_fmt_definition_upstream),
    (SentenceMatchers.DERIVE,               err_fmt_derive_upstream),
    (SentenceMatchers.INTERACTIVE_INSTANCE, err_fmt_instance_upstream),
    (SentenceMatchers.DEFINED_INSTANCE,     err_fmt_instance_upstream),
    (SentenceMatchers.INDUCTIVE,            err_fmt_inductive_upstream),
    (SentenceMatchers.LTAC,                 err_fmt_ltac_upstream),
    #(SentenceMatchers.IMPLICIT_TYPES,       err_fmt_implicit_types_upstream),
    (SentenceMatchers.REGISTER_HINTS,       err_fmt_hint_outside_hint_module),
    (SentenceMatchers.UNREGISTER_HINTS,     err_fmt_unwanted_hint),
]
