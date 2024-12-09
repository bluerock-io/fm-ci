#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.
import re

class FRAGMENTS:
    LCURLY               = '{'
    RCURLY               = '}'

    SPACES               = fr'\s+'
    MAYBE_SPACES         = fr'\s*'
    ANYTHING             = fr'[\s\S]+'
    MAYBE_ANYTHING       = fr'[\s\S]*'

    ANYTHING_BUT_CHARS   = lambda but_chars: fr'[^{but_chars}]+'

    SENTENCE_BEGIN       = fr'^{MAYBE_SPACES}'
    SENTENCE_END         = fr'{MAYBE_SPACES}\.$'

    BEGIN_COMMENT        = fr'{MAYBE_SPACES}\(\*(\*)*'
    # NOTE: specs sometimes use mangled names of the form
    # ["...... X*)"], so we must exclude those from the match
    END_COMMENT          = fr'{MAYBE_SPACES}\*\)(?!\")'

    # v-- Non-whitespace which is followed by some pattern.
    NON_SPACES_THEN      = lambda then_regex: fr'\S+(?={then_regex})'
    NON_SPACES           = NON_SPACES_THEN('')
    # v-- NOTE: matches leading whitespace
    SPACED_STUFF         = fr'({SPACES}{NON_SPACES_THEN(fr"({SPACES}|{SENTENCE_END})")})+'

    # TODO (JH): determine the right way to set up matchers for sentences
    # that can begin with many different attributes in the same [#[...]] block.
    ATTRIBUTE            = lambda attr_regex: fr'\s*(#\[.*{attr_regex}.*\])'
    ATTRIBUTE_ONLY       = lambda only_regex: fr'\s*(#\[.*only\({only_regex}\).*\])'
    ONLY_SOMETHING       = ATTRIBUTE_ONLY(ANYTHING)
    LOCAL                = fr'({ATTRIBUTE("local")}|Local)'
    GLOBAL               = fr'({ATTRIBUTE("global")}|Global)'
    EXPORT               = fr'({ATTRIBUTE("export")}|Export)'
    MAYBE_LOCALITY       = fr'(({LOCAL}|{GLOBAL}|{EXPORT}){SPACES})?'
    POLYMORPHIC          = fr'({ATTRIBUTE("polymorphic")}|Polymorphic)'
    MAYBE_POLYMORPHIC    = fr'(({POLYMORPHIC}){SPACES})?'
    PROGRAM              = fr'({ATTRIBUTE("program")}|({ATTRIBUTE(".*")})?{MAYBE_SPACES}Program)'
    MAYBE_PROGRAM        = fr'(({PROGRAM}){MAYBE_SPACES})?'
    DEFINITELY_PROGRAM   = fr'({PROGRAM}){MAYBE_SPACES}'
    BR_LOCK              = fr'br\.lock'
    MAYBE_BR_LOCK        = fr'({BR_LOCK}{SPACES})?'
    REQUIRE_IMPORT       = fr'(Require{SPACES})?Import'
    REQUIRE_EXPORT       = fr'(Require{SPACES})?Export'
    DEFINITELY_FROM      = fr'From{SPACED_STUFF}{SPACES}'
    MAYBE_FROM           = fr'({DEFINITELY_FROM})?'
    NES_OPEN             = fr'{MAYBE_LOCALITY}NES\.Open{SPACED_STUFF}'
    PROOF_BEGIN          = fr'{MAYBE_SPACES}(Next{SPACES}Obligation|Proof)({SPACES}using{SPACED_STUFF})?'
    PROOF_END            = fr'{MAYBE_SPACES}(Qed|Admitted|Abort|Defined|(Admit{SPACES}Obligations))'
    LEMMA                = fr'(Theorem|Lemma|Example|Corollary)'
    SPECIFY              = fr'Specify'
    DEFINITION           = fr'{MAYBE_LOCALITY}{MAYBE_BR_LOCK}{MAYBE_SPACES}Definition'
    FIXPOINT             = fr'{MAYBE_LOCALITY}{MAYBE_SPACES}Fixpoint'
    INDUCTIVE            = fr'(Inductive|Variant)'
    LTAC                 = fr'{MAYBE_LOCALITY}{MAYBE_SPACES}Ltac'
    INTERACTIVE_INSTANCE = fr'{MAYBE_LOCALITY}{MAYBE_SPACES}Instance'
    DEFINED_INSTANCE     = fr'{MAYBE_LOCALITY}{MAYBE_SPACES}(Existing|Declare){MAYBE_SPACES}Instance'
    IMPLICIT_TYPES       = fr'Implicit Types?'
    DERIVE               = fr'derive'

    COLON_EQUAL_NOT_NAMED_ARGUMENT = fr':=(?!{NON_SPACES}\))'

    MAYBE_UNIVERSE_POLYMORPHIC_NAME = ''.join([
        NON_SPACES,
        '(',
        ''.join([
            '@',
            LCURLY,
            ANYTHING_BUT_CHARS(LCURLY+RCURLY),
            RCURLY,
        ]),
        ')?',
    ])

class GroupNames:
    SECTION_NM_KEY = 'SECTION_NM'

    MODULE_TYPE_NM_KEY  = 'MODULE_TYPE_NM'
    MODULE_TYPE_SIG_KEY = 'MODULE_TYPE_SIG'

    MODULE_NM_KEY = 'MODULE_NM'
    MODULE_SIG_KEY = 'MODULE_SIG'

    NES_NM_KEY = 'NES_NM'

    NEST_END_NM_KEY = 'NEST_END_NM'

    LEMMA_NM_KEY   = 'LEMMA_NM'
    LEMMA_ARGS_KEY = 'LEMMA_ARGS'
    LEMMA_STMT_KEY = 'LEMMA_STMT'

    GOAL_STMT_KEY = 'GOAL_STMT'

    SPEC_OK_LHS_NM_KEY = 'SPEC_OK_LHS_NM'
    SPEC_OK_RHS_NM_KEY = 'SPEC_OK_RHS_NM'

    ANON_INSTANCE_ARGS_KEY = 'ANON_INSTANCE_ARGS'
    ANON_INSTANCE_STMT_KEY = 'ANON_INSTANCE_STMT'

class SentenceMatchers:
    SENTENCE = lambda body_regex: re.compile(
        fr'{FRAGMENTS.SENTENCE_BEGIN}{body_regex}{FRAGMENTS.SENTENCE_END}'
    )

    MK_IMPORT = lambda begin_regex: ''.join([
        fr'{begin_regex}',
        fr'{FRAGMENTS.REQUIRE_IMPORT}{FRAGMENTS.SPACED_STUFF}'
    ])
    MK_EXPORT = lambda begin_regex: ''.join([
        fr'{begin_regex}',
        fr'{FRAGMENTS.REQUIRE_EXPORT}{FRAGMENTS.SPACED_STUFF}'
    ])
    IMPORT         = SENTENCE(MK_IMPORT(FRAGMENTS.MAYBE_FROM))
    IMPORT_NO_FROM = SENTENCE(MK_IMPORT(FRAGMENTS.MAYBE_SPACES))
    EXPORT         = SENTENCE(MK_EXPORT(FRAGMENTS.MAYBE_FROM))
    EXPORT_NO_FROM = SENTENCE(MK_EXPORT(FRAGMENTS.MAYBE_SPACES))
    INCLUDE = SENTENCE(fr'{FRAGMENTS.MAYBE_SPACES}Include{FRAGMENTS.SPACED_STUFF}')
    ELPI_EXTRA_DEPENDENCY = SENTENCE(
        fr'{FRAGMENTS.DEFINITELY_FROM}Extra{FRAGMENTS.SPACES}Dependency{FRAGMENTS.SPACED_STUFF}'
    )

    DERIVE  = SENTENCE(fr'({FRAGMENTS.ONLY_SOMETHING}{FRAGMENTS.MAYBE_SPACES})?{FRAGMENTS.DERIVE}{FRAGMENTS.ANYTHING}')

    SET     = SENTENCE(fr'{FRAGMENTS.MAYBE_LOCALITY}Set{FRAGMENTS.SPACED_STUFF}')
    OPEN    = SENTENCE(fr'{FRAGMENTS.MAYBE_LOCALITY}Open{FRAGMENTS.SPACED_STUFF}')
    CLOSE   = SENTENCE(fr'{FRAGMENTS.MAYBE_LOCALITY}Close{FRAGMENTS.SPACED_STUFF}')

    LOCAL_SET_BR_WORK_TIMEOUT = SENTENCE(
        fr'{FRAGMENTS.LOCAL}{FRAGMENTS.MAYBE_SPACES}Set BR Work Timeout{FRAGMENTS.ANYTHING}'
    )
    LOCAL_NOTATION = SENTENCE(
        fr'{FRAGMENTS.LOCAL}{FRAGMENTS.MAYBE_SPACES}Notation{FRAGMENTS.ANYTHING}'
    )

    NEST_SECTION_BEGIN        = SENTENCE(''.join([
        fr'Section{FRAGMENTS.SPACES}',
        fr'(?P<{GroupNames.SECTION_NM_KEY}>{FRAGMENTS.NON_SPACES})',
    ]))
    # v-- NOTE: doesn't separately match the body of a [Module Type] (supplied using [:=])
    NEST_MODULE_TYPE_BEGIN    = SENTENCE(''.join([
        fr'Module{FRAGMENTS.SPACES}Type{FRAGMENTS.SPACES}',
        fr'(?P<{GroupNames.MODULE_TYPE_NM_KEY}>{FRAGMENTS.NON_SPACES})',
        fr'({FRAGMENTS.SPACES}(?P<{GroupNames.MODULE_TYPE_SIG_KEY}>{FRAGMENTS.MAYBE_ANYTHING}))?',
    ]))
    # v-- NOTE: doesn't separately match the body of a [Module] (supplied using [:=])
    NEST_MODULE_BEGIN         = SENTENCE(''.join([
        fr'Module{FRAGMENTS.SPACES}',
        fr'(Import|Export)?{FRAGMENTS.MAYBE_SPACES}',
        fr'(?P<{GroupNames.MODULE_NM_KEY}>{FRAGMENTS.NON_SPACES})',
        fr'({FRAGMENTS.SPACES}(?P<{GroupNames.MODULE_SIG_KEY}>{FRAGMENTS.MAYBE_ANYTHING}))?',
    ]))
    NEST_NES_BEGIN            = SENTENCE(''.join([
        fr'NES\.Begin{FRAGMENTS.SPACES}(?P<{GroupNames.NES_NM_KEY}>{FRAGMENTS.NON_SPACES})'
    ]))
    NEST_END                  = SENTENCE(''.join([
        fr'(NES.End|End)',
        fr'(?P<{GroupNames.NEST_END_NM_KEY}>{FRAGMENTS.SPACED_STUFF})',
    ]))

    NES_OPEN = SENTENCE(FRAGMENTS.NES_OPEN)
    CONTEXT = SENTENCE(fr'Context{FRAGMENTS.SPACED_STUFF}')

    PROOF_BEGIN    = SENTENCE(fr'{FRAGMENTS.PROOF_BEGIN}{FRAGMENTS.MAYBE_ANYTHING}')
    PROOF_END      = SENTENCE(fr'{FRAGMENTS.MAYBE_ANYTHING}{FRAGMENTS.PROOF_END}')
    PROOF_ONELINER = SENTENCE(fr'{FRAGMENTS.MAYBE_ANYTHING}{FRAGMENTS.PROOF_BEGIN}{FRAGMENTS.MAYBE_ANYTHING}{FRAGMENTS.PROOF_END}')

    SPECIFY        = SENTENCE(fr'{FRAGMENTS.SPECIFY}{FRAGMENTS.ANYTHING}')
    DEFINITION     = SENTENCE(fr'{FRAGMENTS.DEFINITION}{FRAGMENTS.ANYTHING}')
    FIXPOINT       = SENTENCE(fr'{FRAGMENTS.FIXPOINT}{FRAGMENTS.ANYTHING}')
    INDUCTIVE      = SENTENCE(fr'{FRAGMENTS.INDUCTIVE}{FRAGMENTS.ANYTHING}')
    LTAC           = SENTENCE(fr'{FRAGMENTS.LTAC}{FRAGMENTS.ANYTHING}(?<!:):={FRAGMENTS.ANYTHING}')
    LTAC_OVERRIDE_W_IDTAC = SENTENCE(
        fr'{FRAGMENTS.LTAC}{FRAGMENTS.ANYTHING}::={FRAGMENTS.MAYBE_SPACES}idtac'
    )
    IMPLICIT_TYPES = SENTENCE(fr'{FRAGMENTS.IMPLICIT_TYPES}{FRAGMENTS.ANYTHING}')

    INTERACTIVE_INSTANCE = SENTENCE(fr'{FRAGMENTS.INTERACTIVE_INSTANCE}{FRAGMENTS.ANYTHING}')
    DEFINED_INSTANCE     = SENTENCE(fr'{FRAGMENTS.DEFINED_INSTANCE}{FRAGMENTS.ANYTHING}')

    LOCAL_REGISTER_HINTS = SENTENCE(
        fr'{FRAGMENTS.LOCAL}{FRAGMENTS.MAYBE_SPACES}Hint Resolve{FRAGMENTS.SPACED_STUFF}'
    )
    REGISTER_HINTS   = SENTENCE(
        fr'{FRAGMENTS.MAYBE_LOCALITY}Hint (Extern|Resolve){FRAGMENTS.SPACED_STUFF}'
    )
    UNREGISTER_HINTS = SENTENCE(fr'{FRAGMENTS.MAYBE_LOCALITY}Remove Hints{FRAGMENTS.SPACED_STUFF}')

    LEMMA_SHAPE = lambda NM_PAT, ARGS_PAT, STMT_PAT: (''.join([
        fr'{FRAGMENTS.MAYBE_POLYMORPHIC}',
        fr'{FRAGMENTS.MAYBE_LOCALITY}',
        fr'(Theorem|Lemma|Example|{FRAGMENTS.INTERACTIVE_INSTANCE}){FRAGMENTS.SPACES}',
        fr'(?P<{GroupNames.LEMMA_NM_KEY}>{NM_PAT})',
        fr'(?P<{GroupNames.LEMMA_ARGS_KEY}>{ARGS_PAT})?{FRAGMENTS.MAYBE_SPACES}',
        fr':{FRAGMENTS.MAYBE_SPACES}(?P<{GroupNames.LEMMA_STMT_KEY}>{STMT_PAT})',
    ]))
    ANY_LEMMA = SENTENCE(LEMMA_SHAPE(
        ''.join([
            '(',
            FRAGMENTS.NON_SPACES,
            '|)',
        ]),
        FRAGMENTS.ANYTHING,
        FRAGMENTS.ANYTHING
    ))
    SPEC_OK   = SENTENCE(LEMMA_SHAPE(
        fr'(?P<{GroupNames.SPEC_OK_LHS_NM_KEY}>{FRAGMENTS.NON_SPACES})_ok',
        FRAGMENTS.ANYTHING,
        ''.join([
            fr'{FRAGMENTS.ANYTHING}\|--{FRAGMENTS.SPACES}',
            fr'(?P<{GroupNames.SPEC_OK_RHS_NM_KEY}>{FRAGMENTS.NON_SPACES})',
        ])
    ))

    GOAL_SHAPE = lambda STMT_PAT: (''.join([
        fr'{FRAGMENTS.MAYBE_LOCALITY}',
        fr'Goal{FRAGMENTS.SPACES}',
        fr'(?P<{GroupNames.GOAL_STMT_KEY}>{STMT_PAT})',
    ]))
    ANY_GOAL   = SENTENCE(GOAL_SHAPE(FRAGMENTS.ANYTHING))

    ANY_ANONYMOUS_INSTANCE_SHAPE = lambda ARGS_PAT, STMT_PAT: (''.join([
        fr'{FRAGMENTS.MAYBE_POLYMORPHIC}',
        fr'{FRAGMENTS.MAYBE_LOCALITY}',
        fr'{FRAGMENTS.INTERACTIVE_INSTANCE}{FRAGMENTS.MAYBE_SPACES}',
        fr'(?P<{GroupNames.ANON_INSTANCE_ARGS_KEY}>{ARGS_PAT})?{FRAGMENTS.MAYBE_SPACES}',
        fr':{FRAGMENTS.MAYBE_SPACES}(?P<{GroupNames.ANON_INSTANCE_STMT_KEY}>{STMT_PAT})',
    ]))
    ANY_ANONYMOUS_INSTANCE = SENTENCE(
        ANY_ANONYMOUS_INSTANCE_SHAPE(FRAGMENTS.ANYTHING, FRAGMENTS.ANYTHING)
    )
