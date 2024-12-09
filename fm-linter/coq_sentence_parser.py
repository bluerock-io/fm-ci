#!/usr/bin/env python3

# Copyright (c) 2023 BlueRock Security, Inc.
from collections import deque
from coq_regexes import *

# TODO: use serapi/coq-lsp/etc... instead of a custom python script
# Rodolphe: Coq bug minimizer - which splits things into sentences

# [SentenceParser(f)] holds a handle to file [f] and exposes [get_next_sentence()] for stepping
# sequentially through the file.
#
# NOTE: [f.close()] will be invoked when the end of the file is reached; [close()] is idempotent
# so this is compatible with a caller using [with open(...) as f:]
class SentenceParser:
    def __init__(self, f):
        self._lineno = 0
        self._comment_depth = 0
        self._file = f
        self._filename = f.name

    # strip:
    # - ALWAYS: trailing whitespace
    # - INSIDE AN INTERACTIVE PROOF: proof selectors, including:
    #   + leading/trailing curly braces
    #   + leading sequences of [-]/[+]/[*]
    def coq_rstrip(line, inside_interactive_proof=False):
        if inside_interactive_proof:
            def replace_match_with_spaces(match):
                return ' ' * len(match.group(0))

            # first, attempt to remove leading sequences of [-]/[+]/[*]
            line = re.sub(FRAGMENTS.SENTENCE_BEGIN + fr'-+',  replace_match_with_spaces, line)
            line = re.sub(FRAGMENTS.SENTENCE_BEGIN + fr'\++', replace_match_with_spaces, line)
            line = re.sub(FRAGMENTS.SENTENCE_BEGIN + fr'\*+', replace_match_with_spaces, line)

            # then, attempt to remove leading/trailing curly braces
            line = re.sub(r'^\s*[{}\s]+', replace_match_with_spaces, line)
            line = re.sub(r'[{}\s]+\s*$', replace_match_with_spaces, line)

        # finally, return the [rstrip()]ped line
        return line.rstrip()

    # Skip all whitespace/comments/proof-body organization and return a triple containing the next
    # ([rstrip()]ped) line and its line number - in addition to a list of all of the stripped comments
    # preceeding/within the sentence.
    #
    # NOTES:
    # - [f] is left at the beginning of the very next line (i.e. line number + 1).
    # - [coqc] ensures that comment delimiters are properly balanced so we can rely on a
    #   simple stack to accurately skip toplevel comments; comments which are nested within
    #   sentences will should not impact the other matching logic.
    def get_next_line_and_stripped_comments(self, inside_interactive_proof=False):
        comment_snippets = list()

        while True:
            self._lineno += 1
            line = self._file.readline()

            if not line:
                if self._comment_depth != 0:
                    raise RuntimeError(
                        f'[{self._file.name}]: unbalanced [(*]'
                    )
                self._file.close()
                return None

            # Search for begin/end double-quotes in this line and use pairs to prune comment delimiters
            # which appear within those strings.
            #
            # NOTES:
            # - doesn't account for multi-line strings (i.e. ignores a single double-quote)
            # - doesn't handle double-quotes included in strings (i.e. by [""] in Coq)
            double_quotes = list(re.finditer('(?<!")"(?!")', line))
            prune_comment_delimiters_in_string = len(double_quotes) != 0 and len(double_quotes) % 2 == 0
            if prune_comment_delimiters_in_string:
                double_quotes.sort(key=lambda match: match.start())
                string_quotes = list(zip(double_quotes[::2], double_quotes[1::2]))

            # Search for begin/end comments in this line and replace the portions of the line which
            # are within those comments by [' '] (space character).
            comment_start_delimiters = list(re.finditer(FRAGMENTS.BEGIN_COMMENT, line))
            comment_end_delimiters   = list(re.finditer(FRAGMENTS.END_COMMENT, line))
            comment_delimiters = (
                list(zip(comment_start_delimiters, [True] * len(comment_start_delimiters))) +
                list(zip(comment_end_delimiters, [False] * len(comment_end_delimiters)))
            )
            # prune comment delimiters which "look like" they are part of a string
            if prune_comment_delimiters_in_string:
                def delimiter_not_in_string(info):
                    info_start, info_end = info[0].start(), info[0].end()

                    for start_quote, end_quote in string_quotes:
                        if info_start >= start_quote.end() and info_end < end_quote.start():
                            return False

                    return True

                comment_delimiters = list(filter(delimiter_not_in_string, comment_delimiters))
            comment_delimiters.sort(key=lambda info: info[0].start())

            # /-- If this line contains no comment delimiters but we're still inside of a
            # v   comment then we simply skip the line
            if not comment_delimiters and self._comment_depth != 0:
                comment_snippets.append(line)
                continue

            comment_start_delimiter_lifo = deque()
            for match, is_start_delimiter in comment_delimiters:
                # /-- Accumulate a LIFO of comment start delimiters which can be used to cancel
                # v   comment end delimiters as they appear
                if is_start_delimiter:
                    self._comment_depth += 1
                    comment_start_delimiter_lifo.appendleft(match)
                else:
                    self._comment_depth -= 1
                    if self._comment_depth < 0:
                        raise RuntimeError(
                            f'[{self._file.name}#{match.start()}-{match.end()}]: unbalanced [*)]: {line}'
                        )

                    # Either the /entire/ prefix of [line] is part of a comment or /a suffix/
                    # of the prefix (bounded by [start_delimiter_lifo.popleft().start()]) is
                    # part of a comment.
                    if not comment_start_delimiter_lifo:
                        match_start = 0
                    else:
                        if self._comment_depth == 0:
                            match_start = comment_start_delimiter_lifo.popleft().start()
                        else:
                            match_start = 0
                    comment_snippets.append(line[match_start:match.end()])
                    line = (
                        line[:match_start] +
                        (' ' * (match.end() - match_start)) +
                        line[match.end():]
                    )

            # Some comment-start delimiter is not matched with an end delimiter which means
            # the suffix of [line] is part of a comment.
            #
            # NOTE: Take the outermost [re.Matcher] by popping from the back of the LIFO.
            if comment_start_delimiter_lifo:
                match_start = comment_start_delimiter_lifo.pop().start()
                comment_snippets.append(line[match_start:])
                line = line[:match_start] + (' ' * (len(line) - match_start))

            stripped_line = SentenceParser.coq_rstrip(line, inside_interactive_proof=inside_interactive_proof)
            # v-- The line only consisted of whitespace and/or comments
            if not stripped_line: continue

            # NOTE: the parser can sometimes mess up when nested comments are encountered - including
            # part of the comment in in the following sentence. Therefore, if we detect any nested
            # delimiters in the [comment_snippets] we return additional information to the caller
            candidate_comment_snippets = comment_snippets[1:len(comment_snippets)-1]
            comment_snippets_might_contain_nested_comment = bool(candidate_comment_snippets and any(map(
                lambda comment_snippet: (
                       re.match(FRAGMENTS.BEGIN_COMMENT, comment_snippet)
                    or re.match(FRAGMENTS.END_COMMENT, comment_snippet)
                ),
                candidate_comment_snippets
            )))

            # print('-----------------------------')
            # print(comment_snippets)

            return (stripped_line, self._lineno, comment_snippets, comment_snippets_might_contain_nested_comment)

    # Return a quadruple containing the next sentence and its start/end line numbers - followed by
    # the list of comment snippets erased before/within the sentence.
    #
    # NOTE: [f] is left at the beginning of the very next line (i.e. end line number + 1).
    def get_next_sentence(self, inside_interactive_proof=False):
        result = self.get_next_line_and_stripped_comments(inside_interactive_proof=inside_interactive_proof)
        if not result: return None
        line, starting_lineno, comment_snippets, comment_snippets_might_contain_nested_comment = result
        ending_lineno = starting_lineno

        while not re.search(FRAGMENTS.SENTENCE_END, line):
            result = self.get_next_line_and_stripped_comments(inside_interactive_proof=inside_interactive_proof)
            if not result:
                raise RuntimeError(
                    f'[{self._filename}#{starting_lineno}-{ending_lineno}]: end of file reached with an unterminated sentence: {line}'
                )
            new_line, ending_lineno, new_comment_snippets, new_comment_snippets_might_contain_nested_comment = result
            comment_snippets_might_contain_nested_comment = (
                   comment_snippets_might_contain_nested_comment
                or new_comment_snippets_might_contain_nested_comment
            )
            comment_snippets.extend(new_comment_snippets)
            line += '\n' + new_line

        return (line, starting_lineno, ending_lineno, comment_snippets, comment_snippets_might_contain_nested_comment)
