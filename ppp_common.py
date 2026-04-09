import ast
import logging
import os
import re
import textwrap
import time
import lark

from ppp_logging import log
from ppp_classes import ONWARNING_CHOICES, PPPInterrupt, PPPState
from ppp_utils import escape_single_quotes, format_output


def parse_prompt(
    state: PPPState,
    prompt_description: str,
    prompt: str,
    parser: lark.Lark,
    raise_parsing_error: bool = False,
):
    """
    Parses a prompt using the specified parser.

    Args:
        prompt_description (str): The description of the prompt.
        prompt (str): The prompt to be parsed.
        parser (lark.Lark): The parser to be used.
        raise_parsing_error (bool): Whether to raise a parsing error.

    Returns:
        Tree: The parsed prompt.
    """
    t1 = time.monotonic_ns()
    parsed_prompt = None
    try:
        log(
            state.logger,
            state.options.debug_level,
            logging.DEBUG,
            f"Parsing {prompt_description}: '{escape_single_quotes(prompt)}'",
        )
        parsed_prompt = parser.parse(prompt)
        # we store the contents so we can use them later even if the meta position is not valid anymore
        if isinstance(parsed_prompt, lark.Tree):
            for n in parsed_prompt.iter_subtrees():
                if isinstance(n, lark.Tree):
                    if n.meta.empty:
                        n.meta.content = ""
                    else:
                        n.meta.content = prompt[n.meta.start_pos : n.meta.end_pos]
    except lark.exceptions.UnexpectedInput:
        if raise_parsing_error:
            raise
        log(
            state.logger,
            state.options.debug_level,
            logging.ERROR,
            f"Parsing failed on prompt!: {escape_single_quotes(prompt)}",
        )
    t2 = time.monotonic_ns()
    log(
        state.logger,
        state.options.debug_level,
        logging.DEBUG,
        f"Parse {prompt_description} time: {(t2 - t1) / 1_000_000_000:.3f} seconds",
    )
    if parsed_prompt:
        log(
            state.logger,
            state.options.debug_level,
            logging.DEBUG,
            "Tree:\n"
            + textwrap.indent(
                re.sub(r"\n$", "", (parsed_prompt.pretty() if isinstance(parsed_prompt, lark.Tree) else parsed_prompt)),
                "    ",
            ),
        )
    return parsed_prompt


def warn_or_stop(state: PPPState, is_negative: bool, message: str, e: Exception = None):
    INVALID_CONTENT_STOP = "INVALID CONTENT! {0}\nBREAK "
    if state.options.on_warning == ONWARNING_CHOICES.stop:
        raise PPPInterrupt(
            message,
            INVALID_CONTENT_STOP.format(message) if not is_negative else "",
            INVALID_CONTENT_STOP.format(message) if is_negative else "",
        ) from e
    log(state.logger, state.options.debug_level, logging.WARNING, format_output(message))


def load_grammar() -> str:
    # Process with lark (debug with https://www.lark-parser.org/ide/)
    grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
    with open(grammar_filename, "r", encoding="utf-8") as file:
        grammar_content = file.read()
    return grammar_content


def preprocess_grammar(grammar_content: str, options: dict[str, bool], logger: logging.Logger, debug_level: int) -> str:
    """
    Preprocesses the grammar content to handle conditional compilation directives.

    Args:
        grammar_content (str): The raw grammar content.
        options (dict[str,bool]): Options for preprocessing.
        logger (logging.Logger): The logger object.
        debug_level (int): The debug level for logging.

    Returns:
        str: The preprocessed grammar content.
    """
    lines = grammar_content.split("\n")
    result_lines = []
    skip_current_block = []
    all_blocks_skipped = []

    def eval_bool_expr(expr: str, constants: dict[str, bool]) -> bool:
        """
        Evaluates a boolean expression using known constants.
        Supports: and, or, not, parentheses, and named constants.

        Args:
            expr (str): The boolean expression to evaluate.
            constants (dict[str, bool]): A dictionary of constant values.
        Returns:
            bool: The result of the evaluated expression.
        """
        tree = ast.parse(expr, mode="eval")

        def _eval(node) -> bool:
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(_eval(v) for v in node.values)
                if isinstance(node.op, ast.Or):
                    return any(_eval(v) for v in node.values)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                return not _eval(node.operand)
            if isinstance(node, ast.Name):
                return bool(constants[node.id])  # raises KeyError for unknown names
            if isinstance(node, ast.Constant) and isinstance(node.value, bool):
                return node.value
            raise ValueError(f"Unsupported construct: {ast.dump(node)}")

        return _eval(tree)

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("//#if"):
            # Extract condition from the #if directive
            conditions = stripped_line[5:].strip()
            # Evaluate the conditions
            skip_current_block.append(not eval_bool_expr(conditions, options))
            all_blocks_skipped.append(skip_current_block[-1])
        elif stripped_line.startswith("//#elif"):
            if not skip_current_block:
                log(logger, debug_level, logging.WARNING, "Unmatched //#elif directive found in grammar content.")
            elif all_blocks_skipped[-1]:
                # Extract condition from the #elif directive
                conditions = stripped_line[7:].strip()
                # Evaluate the conditions
                skip_current_block[-1] = not eval_bool_expr(conditions, options)
                if not skip_current_block[-1]:
                    all_blocks_skipped[-1] = False
            else:
                skip_current_block[-1] = True
        elif stripped_line.startswith("//#else"):
            if not skip_current_block:
                log(logger, debug_level, logging.WARNING, "Unmatched //#else directive found in grammar content.")
            elif all_blocks_skipped[-1]:
                skip_current_block[-1] = False
            else:
                skip_current_block[-1] = True
        elif stripped_line.startswith("//#endif"):
            if not skip_current_block:
                log(logger, debug_level, logging.WARNING, "Unmatched //#endif directive found in grammar content.")
            else:
                skip_current_block.pop()
                all_blocks_skipped.pop()
        elif stripped_line.startswith("//#"):
            log(
                logger,
                debug_level,
                logging.WARNING,
                f"Unrecognized directive found in grammar content: {stripped_line}",
            )
        elif not any(skip_current_block):
            # Include the line if we're not skipping any current block
            result_lines.append(stripped_line)
    # Check for unclosed blocks at the end
    if skip_current_block:
        raise PPPInterrupt(
            f"Found {len(skip_current_block)} unclosed conditional directive(s) at the end of the grammar file"
        )
    return "\n".join(result_lines)
