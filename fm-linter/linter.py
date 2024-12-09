#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.
from collections import deque
from coq_regexes import *
from coq_sentence_parser import SentenceParser
from linter_util import *
from util import *

class RuntimeError_PartialLint(RuntimeError):
    def __init__(self, message, partial_linting_errors, parsing_issue=False):
        super().__init__(message)
        self.partial_linting_errors = partial_linting_errors
        self.parsing_issue = parsing_issue

# KNOWN LIMITATIONS:
# 1) multiple sentences on a single line
# 2) lines ending with [.] which do not conclude a sentence
# 3) nested comments
#
# TODOS:
# - check for conflicts between the toplevel policy and the specific
#   subpolicies
# - define config language/knobs in terms of invariants over stacks
# - track specific [_XXX_errors] as opposed to just [_errors]
class CoqLinter:
    def __init__(self, policy):
        validate_policy_shape(policy)
        self._policy = policy

        self._section_ctx_nm     = 'section'
        self._module_type_ctx_nm = 'module_type'
        self._module_ctx_nm      = 'module'
        self._nes_ctx_nm         = 'nes'
        self._proof_ctx_nm       = 'proof'
        self._toplevel_ctx_nm    = 'toplevel'

        self.reset()

    def reset(self):
        self._filename = None
        self._errors = []

        # Track stacks of names for [Section]s/[Module Type]s/[Module]s/[NES]/[Proof]
        #
        # NOTE: we use these like stacks even though [dequeue] permits queue-like operations.
        self._info_stacks = {
            self._section_ctx_nm:     deque(),
            self._module_type_ctx_nm: deque(),
            self._module_ctx_nm:      deque(),
            self._nes_ctx_nm:         deque(),
            self._proof_ctx_nm:       deque(),
        }

        # Track stack of contexts (with an implicit ['toplevel'] context)
        self._context_stack        = deque([self._toplevel_ctx_nm])

        # The linter always checks to see whether a [Proof] line has been observed after
        # a lemma statement.
        #
        # NOTE: the corresponding [self._nested_proof_stack] accounts for
        # [Set Nested Proofs Allowed].
        self._program_definition       = False
        self._elide_proof_line         = False
        self._expect_proof_line        = False
        self._proof_line_seen          = False
        self._proof_line_unseen_logged = False
        self._nested_proof_stack    = deque()

        # /-- NOTE: allow dangling [Next Obligations] to [enter_proof_ctx]; this allows
        # v   chaining of these proofs.
        self._next_obligation_enter_proof_ctx = False

    def current_ctx(self):        return self._context_stack[0]

    def in_toplevel_ctx(self):    return self.current_ctx() == self._toplevel_ctx_nm
    def in_section_ctx(self):     return self.current_ctx() == self._section_ctx_nm
    def in_module_type_ctx(self): return self.current_ctx() == self._module_type_ctx_nm
    def in_module_ctx(self):      return self.current_ctx() == self._module_ctx_nm
    def in_nes_ctx(self):         return self.current_ctx() == self._nes_ctx_nm
    def in_proof_ctx(self):       return self.current_ctx() == self._proof_ctx_nm

    def toplevel_policy(self):
        return self._policy['global_policies']
    def ctx_policy(self):
        if self.in_toplevel_ctx():
            return self._policy['global_policies']
        elif self.in_section_ctx():
            return self._policy['section_policies']
        elif self.in_module_type_ctx():
            return self._policy['module_type_policies']
        elif self.in_module_ctx():
            return self._policy['module_policies']
        elif self.in_nes_ctx():
            return self._policy['nes_policies']
        elif self.in_proof_ctx():
            return self._policy['proof_policies']
        else:
            msg = ' '.join([
                'Context stack error',
                '(' + format_ansi_msg(self._filename, ANSI_BOLD) + '):',
                format_ansi_msg(self.current_ctx(), ANSI_BOLD),
                'should be one of:',
                ', '.join(map(
                    lambda nm: format_ansi_msg(nm, ANSI_BOLD),
                    self._info_stacks.keys(),
                )) + '.',
            ])
            raise RuntimeError_PartialLint(msg, self._errors)

    def _enter_ctx(self, ctx, info, starting_lineno):
        if ctx not in self._info_stacks.keys():
            msg = ' '.join([
                'Context stack error',
                '(' + format_ansi_msg(self._filename, ANSI_BOLD) + ':' + str(starting_lineno) + '):',
                format_ansi_msg(ctx, ANSI_BOLD),
                'should be one of:'
                ', '.join(map(
                    lambda nm: format_ansi_msg(nm, ANSI_BOLD),
                    self._info_stacks.keys(),
                )) + '.'
            ])
            raise RuntimeError_PartialLint(msg, self._errors)

        # Push information onto the appropriate stacks ...
        self._context_stack.appendleft(ctx)
        self._info_stacks[ctx].appendleft(info)
        # ... and check generic policy invariants using this newly recorded information
        self.check_policy_invariant()

    def enter_section_ctx(self, info, starting_lineno):     self._enter_ctx(self._section_ctx_nm, info, starting_lineno)
    def enter_module_type_ctx(self, info, starting_lineno): self._enter_ctx(self._module_type_ctx_nm, info, starting_lineno)
    def enter_module_ctx(self, info, starting_lineno):      self._enter_ctx(self._module_ctx_nm, info, starting_lineno)
    def enter_nes_ctx(self, info, starting_lineno):         self._enter_ctx(self._nes_ctx_nm, info, starting_lineno)
    def enter_proof_ctx(self, info, starting_lineno, program_definition=False, elide_proof_line=False):
        self._next_obligation_enter_proof_ctx = False

        self._enter_ctx(self._proof_ctx_nm, info, starting_lineno)
        self._nested_proof_stack.appendleft((
            self._program_definition,
            self._elide_proof_line,
            self._expect_proof_line,
            self._proof_line_seen,
            self._proof_line_unseen_logged,
        ))
        self._program_definition       = program_definition
        self._elide_proof_line         = elide_proof_line
        self._expect_proof_line        = False
        self._proof_line_seen          = False
        self._proof_line_unseen_logged = False

    def _exit_ctx(self, ctx, staring_lineno):
        if self.in_toplevel_ctx():
            msg = ' '.join([
                'Context stack error',
                '(' + format_ansi_msg(self._filename, ANSI_BOLD) + ':' + str(staring_lineno) + '):',
                format_ansi_msg(self._toplevel_ctx_nm, ANSI_BOLD),
                'should never be popped.',
            ])
            raise RuntimeError_PartialLint(msg, self._errors)

        current_ctx = self.current_ctx()
        if ctx != current_ctx:
            msg = ' '.join([
                'Context stack error',
                '(' + format_ansi_msg(self._filename, ANSI_BOLD) + ':' + str(staring_lineno) + '):',
                'currently in context',
                format_ansi_msg(current_ctx, ANSI_BOLD),
                'but attempting to exit context',
                format_ansi_msg(ctx, ANSI_BOLD) + '.',
            ])
            raise RuntimeError_PartialLint(msg, self._errors)
        else:
            self._context_stack.popleft()
            self._info_stacks[current_ctx].popleft()
            self.check_policy_invariant(is_enter=False)

    def exit_section_ctx(self, starting_lineno):     self._exit_ctx(self._section_ctx_nm, starting_lineno)
    def exit_module_type_ctx(self, starting_lineno): self._exit_ctx(self._module_type_ctx_nm, starting_lineno)
    def exit_module_ctx(self, starting_lineno):      self._exit_ctx(self._module_ctx_nm, starting_lineno)
    def exit_nes_ctx(self, starting_lineno):         self._exit_ctx(self._nes_ctx_nm, starting_lineno)
    def exit_proof_ctx(self, starting_lineno):
        self._exit_ctx(self._proof_ctx_nm, starting_lineno)

        if self._program_definition:
            self._next_obligation_enter_proof_ctx = True

        self._program_definition,
        self._elide_proof_line,
        self._expect_proof_line,
        self._proof_line_seen,
        self._proof_line_unseen_logged = (
            self._nested_proof_stack.popleft()
        )

    # Check general or [sentence]-specific policies - modifying [self._errors]
    # if violations are found.
    def check_policy_invariant(self, is_enter=True):
        current_ctx = self.current_ctx()

        if is_enter:
            # check context invariants of [self._policy[f'{context}_policy']]
            pass
        else:
            # NOTE: in the future we might want to check some policy invariants
            # when exiting a context, but for now we don't check anything.
            pass

    def check_policy_aux(self, sentence, starting_lineno, ending_lineno):
        toplevel_policy = self.toplevel_policy()
        ctx_policy      = None if self.in_toplevel_ctx() else self.ctx_policy()

        # 1) check [current_ctx] (then global) "eager_allow_list" policies
        if ctx_policy:
            for allow in ctx_policy['eager_allow_list']:
                if allow.match(sentence):
                    return
        for allow in toplevel_policy['eager_allow_list']:
            if allow.match(sentence):
                return

        # 2) check [current_ctx] (then global) "deny_list" policies
        if ctx_policy:
            for disallow, err_fmt in ctx_policy['deny_list']:
                if disallow.match(sentence):
                    self._errors.append((err_fmt(sentence), starting_lineno, ending_lineno))
                    return
        for disallow, err_fmt in toplevel_policy['deny_list']:
            if disallow.match(sentence):
                self._errors.append((err_fmt(sentence), starting_lineno, ending_lineno))
                return

        # 3) check [current_ctx] (then global) "allow_list" policies
        if ctx_policy:
            for allow in ctx_policy['allow_list']:
                if allow.match(sentence):
                    return
        for allow in toplevel_policy['allow_list']:
            if allow.match(sentence):
                return


        # 4) UNRECOGNIZED SENTENCE: update [current_ctx] and/or global policy
        self._errors.append((
            err_fmt_unknown(sentence),
            starting_lineno,
            ending_lineno
        ))

    def check_policy(self, sentence, starting_lineno, ending_lineno):
        if (        self.in_proof_ctx()
            and     self._expect_proof_line
            and not self._program_definition
            and not self._proof_line_seen
            and not self._proof_line_unseen_logged):
            # a proof which doesn't start with a [Proof] line
            self._errors.append((
                # lemma name at head of proof stack -------v
                err_fmt_missing_proof_begin(
                    self._info_stacks[self._proof_ctx_nm][0][0],
                    sentence
                ),
                starting_lineno,
                ending_lineno
            ))
            self._proof_line_unseen_logged = True

        self._expect_proof_line = not self._elide_proof_line and self.in_proof_ctx()

        self.check_policy_aux(sentence, starting_lineno, ending_lineno)

    def is_interactive_sentence(sentence):
        # v-- NOTE: special case for [Definition ....] w/out [:=]
        if SentenceMatchers.DEFINITION.match(sentence) or SentenceMatchers.FIXPOINT.match(sentence):
            # v-- NOTE: this might miss [Definition ... (foo:=bar) ...] w/out [:=]
            return len(re.findall(fr':=', sentence)) == 0

        # v-- NOTE: special case for [#[... program ...]]
        if len(re.findall(FRAGMENTS.DEFINITELY_PROGRAM, sentence)) != 0:
            return True

        def mk_pat(left_delimiter, right_delimiter, exclude_other=True):
            if exclude_other:
                left_contents = FRAGMENTS.ANYTHING_BUT_CHARS(right_delimiter)
                right_contents = FRAGMENTS.ANYTHING_BUT_CHARS(left_delimiter)
            else:
                left_contents = FRAGMENTS.ANYTHING
                right_contents = FRAGMENTS.ANYTHING

            pat = ''.join([
                fr'{left_delimiter}',
                fr'{left_contents}',
                FRAGMENTS.MAYBE_SPACES,
                fr':=',
                FRAGMENTS.MAYBE_SPACES,
                fr'({right_contents}|\({right_contents}\)\%{FRAGMENTS.NON_SPACES})',
                fr'{right_delimiter}'
            ])
            return pat

        all_allowed_colon_equals_matches = (
            list(re.finditer(mk_pat(r'let', r'in', exclude_other=False), sentence)) +
            list(re.finditer(mk_pat(r'\(', r'\)'), sentence)) +
            list(re.finditer(mk_pat(r'\[', r'\]'), sentence)) +
            list(re.finditer(mk_pat(r'\{', r'\}'), sentence)) +
            list(re.finditer(mk_pat(r'\<', r'\>'), sentence)) +
            list(re.finditer(mk_pat(r'\|', r'\|'), sentence))
        )
        all_allowed_colon_equals_matches.sort(key=lambda match: match.start())

        # NOTE: [all_allowed_colon_equals_matches] misses arguments of the form
        # [(FOO:=...(...(BAR)...))], so we manually special-case that form here
        # by counting parens as we walk out in either direction from the [:=]
        # match
        def check_allowed_special_case_nested_parens(colon_equals_match):
            # Valid matches will be of the form:
            # 1) open paren
            # 2) name
            # 3) :=
            # 4) any valid string containing balanced parentheses
            # 5) close paren

            seen_lparen = False
            i_left = colon_equals_match.start()
            i_right = colon_equals_match.end()

            # validate open paren
            while 0 <= i_left:
                c = sentence[i_left]
                if c == '(':
                    # open paren validated
                    seen_lparen = True
                    break
                elif c == ')':
                    # defined arguments can only have a name appear on the LHS
                    return False
                else:
                    i_left -= 1
            # NOTE: [sentence[i_left]] is the nearest open paren (w/out any intervening close paren)

            if not seen_lparen: return False

            open_paren_count = 0
            while i_right < len(sentence):
                c = sentence[i_right]
                if c == '(':
                    open_paren_count += 1
                elif c == ')':
                    if open_paren_count == 0:
                        return True
                    else:
                        open_paren_count -= 1

                i_right += 1

            # v-- couldn't find a matching close-paren to balance the open-paren
            return False

        def check_allowed(colon_equals_match):
            allowed = False

            for allowed_colon_equals_match in all_allowed_colon_equals_matches:
                if (colon_equals_match.start() <= allowed_colon_equals_match.start()):
                    # NOTE: the allowed patterns containing [:=] are bigger than [:=]
                    # so we use [<=] instead of [<].
                    continue
                elif (    allowed_colon_equals_match.start() <= colon_equals_match.start()
                      and colon_equals_match.end() <= allowed_colon_equals_match.end()):
                    allowed = True
                    break
                elif allowed_colon_equals_match.end() <= colon_equals_match.start():
                    # NOTE: match spans are sorted so if we go past the end we know
                    # we've found a [:=] which isn't allowed
                    continue

            return allowed or check_allowed_special_case_nested_parens(colon_equals_match)

        # If a [:=] is found which isn't "allowed", we conclude that we've found a non-interactive
        # definition (i.e. [Module foo ... := bar.], [Instance baz : ... := _.], etc...)
        allowed_results = map(check_allowed, re.finditer(r':=', sentence))
        return allowed_results is not [] and all(allowed_results)

    def try_handle_ctx_entry(self, sentence, starting_lineno, ending_lineno):
        # Enter proof
        # NOTE: interactive [Instance]s/[Definition]s/etc... complicate things
        proof_ctx_entered = False
        lemma_match = SentenceMatchers.ANY_LEMMA.match(sentence)
        anonymous_instance_match = SentenceMatchers.ANY_ANONYMOUS_INSTANCE.match(sentence)
        goal_match = SentenceMatchers.ANY_GOAL.match(sentence)
        if lemma_match or anonymous_instance_match:
            # NOTE: if arguments are provided (i.e. [foo (X:=Y)] then this simple [re.search]
            # misses certain lemmas.
            if CoqLinter.is_interactive_sentence(sentence):
                program_definition = (re.match(FRAGMENTS.DEFINITELY_PROGRAM, sentence) is not None)
                # elide_proof_line = (re.match(FRAGMENTS.INTERACTIVE_INSTANCE, sentence) is not None)
                # v-- NOTE: easier to always allow [Proof] to be elided, for now
                elide_proof_line = True
                if lemma_match:
                    NM   = lemma_match.group(GroupNames.LEMMA_NM_KEY)
                    ARGS = lemma_match.group(GroupNames.LEMMA_ARGS_KEY)
                    STMT = lemma_match.group(GroupNames.LEMMA_STMT_KEY)
                else:
                    NM   = '<anonymous instance>'
                    ARGS = anonymous_instance_match.group(GroupNames.ANON_INSTANCE_ARGS_KEY)
                    STMT = anonymous_instance_match.group(GroupNames.ANON_INSTANCE_STMT_KEY)
                self.enter_proof_ctx(
                    (NM, ARGS, STMT, starting_lineno, ending_lineno),
                    starting_lineno,
                    program_definition=program_definition,
                    elide_proof_line=elide_proof_line
                )
                proof_ctx_entered = True
            else:
                # /-- NOTE: we encountered a non-interactive proof
                # v   (i.e. [Instance foo : ... := ...])
                return False
        elif goal_match:
            self.enter_proof_ctx((
                '<anonymous goal>',
                '',
                goal_match.group(GroupNames.GOAL_STMT_KEY),
                starting_lineno,
                ending_lineno,
            ), starting_lineno, elide_proof_line=True)
            proof_ctx_entered = True
        # v-- TODO: add a regex to match [#[program]] declarations
        elif re.match(
                fr'{FRAGMENTS.SENTENCE_BEGIN}{FRAGMENTS.MAYBE_SPACES}{FRAGMENTS.DEFINITELY_PROGRAM}',
                sentence
        ):
            self.enter_proof_ctx((
                sentence,
                starting_lineno,
                ending_lineno,
            ), starting_lineno, program_definition=True)
            proof_ctx_entered = True
        elif SentenceMatchers.DEFINITION.match(sentence) or SentenceMatchers.FIXPOINT.match(sentence):
           if CoqLinter.is_interactive_sentence(sentence):
                self.enter_proof_ctx((
                    sentence,
                    starting_lineno,
                    ending_lineno,
                ), starting_lineno, elide_proof_line=True)
                proof_ctx_entered = True
        # v-- TODO: add a regex to match [Equations] declarations
        elif re.match(
                fr'{FRAGMENTS.SENTENCE_BEGIN}{FRAGMENTS.MAYBE_SPACES}Equations',
                sentence
        ):
           if CoqLinter.is_interactive_sentence(sentence):
                self.enter_proof_ctx((
                    sentence,
                    starting_lineno,
                    ending_lineno,
                ), starting_lineno, program_definition=True)
                proof_ctx_entered = True

        # NOTE: slight optimization; once a proof context is entered, only "proof"-things
        # are allowed.
        # TODO: permit linting the proof-body contents of a one-liner proof.
        if (       SentenceMatchers.PROOF_ONELINER.match(sentence)
                or (self._elide_proof_line and SentenceMatchers.PROOF_END.match(sentence))):
            # /-- NOTE: the proof oneline might be a [Next Obligation] which isn't first - in which
            # v   case the linter won't be in a proof ctx.
            if self.in_proof_ctx():
                self.exit_proof_ctx(starting_lineno)
            return True
        elif (self.in_proof_ctx() or self._next_obligation_enter_proof_ctx) and SentenceMatchers.PROOF_BEGIN.match(sentence):
            next_obligation_match = re.match(
                ''.join([
                    FRAGMENTS.MAYBE_SPACES,
                    '(Fail{FRAGMENTS.SPACES})?'
                    ,'Next',
                    FRAGMENTS.SPACES,
                    'Obligation',
                ]),
                sentence
            )
            if self._next_obligation_enter_proof_ctx and next_obligation_match:
                self.enter_proof_ctx((
                    sentence,
                    starting_lineno,
                    ending_lineno
                ), starting_lineno, program_definition=True)
            self._proof_line_seen = True
            return True
        else:
            # Try to enter [Section]
            section_match = SentenceMatchers.NEST_SECTION_BEGIN.match(sentence)
            if section_match:
                self.enter_section_ctx((
                    section_match.group(GroupNames.SECTION_NM_KEY),
                    starting_lineno,
                    ending_lineno,
                ), starting_lineno)
                return True

            # Try to enter [Module]/[Module Type]
            #
            # NOTE: overlapping regexes between [Module]/[Module Type]; try the more
            # specific one first.
            module_type_match = SentenceMatchers.NEST_MODULE_TYPE_BEGIN.match(sentence)
            module_match      = SentenceMatchers.NEST_MODULE_BEGIN.match(sentence)
            if module_type_match:
                if CoqLinter.is_interactive_sentence(sentence):
                    self.enter_module_type_ctx((
                        module_type_match.group(GroupNames.MODULE_TYPE_NM_KEY),
                        module_type_match.group(GroupNames.MODULE_TYPE_SIG_KEY),
                        starting_lineno,
                        ending_lineno,
                    ), starting_lineno)
                    return True
                else:
                    # /-- NOTE: we encountered a non-interactive module type
                    # v   (i.e. [Module Type foo : ... := ...])
                    return False
            elif module_match:
                if CoqLinter.is_interactive_sentence(sentence):
                    self.enter_module_ctx((
                        module_match.group(GroupNames.MODULE_NM_KEY),
                        module_match.group(GroupNames.MODULE_SIG_KEY),
                        starting_lineno,
                        ending_lineno,
                    ), starting_lineno)
                    return True
                else:
                    # /-- NOTE: we encountered a non-interactive module
                    # v   (i.e. [Module foo : ... := ...])
                    return False

            # Try to enter [NES] namespace
            nes_match = SentenceMatchers.NEST_NES_BEGIN.match(sentence)
            if nes_match:
                self.enter_nes_ctx((
                    nes_match.group(GroupNames.NES_NM_KEY),
                    starting_lineno,
                    ending_lineno,
                ), starting_lineno)
                return True

        return proof_ctx_entered

    def try_handle_ctx_exit(self, sentence, starting_lineno, ending_lineno):
        # NOTE: [try_handle_ctx_enter] handles oneline proofs since it also scans for [Proof] -
        # which doesn't exit the proof context by itself.
        if (SentenceMatchers.PROOF_END.match(sentence)):
            self.exit_proof_ctx(starting_lineno)
            return True

        nest_end_match = SentenceMatchers.NEST_END.match(sentence)
        if nest_end_match:
            if self.in_section_ctx():
                self.exit_section_ctx(starting_lineno)
                return True
            elif self.in_module_type_ctx():
                self.exit_module_type_ctx(starting_lineno)
                return True
            elif self.in_module_ctx():
                self.exit_module_ctx(starting_lineno)
                return True
            elif self.in_nes_ctx():
                self.exit_nes_ctx(starting_lineno)
                return True
            else:
                # print(self._context_stack)
                # print(self._info_stacks)
                msg = ' '.join([
                    '(' + format_ansi_msg(self._filename, ANSI_BOLD) + '):',
                    format_ansi_msg(nest_end_match.group(GroupNames.NEST_END_NM_KEY), ANSI_BOLD),
                    'ends a nested context which was not recognized as',
                    'a [Section]/[Module]/[Module Type]/[NES] namespace.',
                ])
                raise RuntimeError_PartialLint(msg, self._errors)

        return False

    def run(self, f):
        self.reset()
        self._filename = f.name
        sentence_parser = SentenceParser(f)

        # Psueodocode of loop (for each non-[None] [result]):
        # 1) Check if the [comment_snippets] contain a [NOLINT] substring
        # 2) Check if a new context was entered and if so, push info onto the appropiate stack
        #    and continue
        # 3) Check if the existing context was exited and if so, pop from the appropriate stack
        #    and continue
        # 4) check the current sentence against the (contextual) policy - if linting hasn't been disabled
        #
        # NOTE: [coqc] ensures that things are properly bracketed/nested.
        while True:
            try:
                result = sentence_parser.get_next_sentence(inside_interactive_proof=self.in_proof_ctx())
            except RuntimeError as e:
                raise RuntimeError_PartialLint(e, self._errors, parsing_issue=True)

            if not result: break
            sentence, starting_lineno, ending_lineno, comment_snippets, maybe_nested_comment = result

            # 1) Check if the [comment_snippets] contain a "[[NOLINT]]" substring
            #
            # NOTE: in the future we could attempt to disable linting for entire
            # modules/sections/etc...
            nolint_next_sentence = any(map(
                lambda comment_snippet: '[[NOLINT]]' in comment_snippet,
                comment_snippets
            ))

            # print('~~~~~~~~~~~~~~~~~~~~~~~~~~')
            # print(self._context_stack)
            # print(self._program_definition)
            # print(self._next_obligation_enter_proof_ctx)
            # print(sentence)
            # print(comment_snippets)

            # 3/4): check for context entry/exit and continue if found.
            if (   self.try_handle_ctx_entry(sentence, starting_lineno, ending_lineno)
                or self.try_handle_ctx_exit(sentence, starting_lineno, ending_lineno)):
                continue
            else:
                # 5) check the current sentence against the (contextual) policy (if linting hasn't been disabled
                if not nolint_next_sentence:
                    self.check_policy(sentence, starting_lineno, ending_lineno)

        return self._errors
