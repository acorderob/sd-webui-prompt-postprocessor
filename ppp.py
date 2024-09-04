import fnmatch
import logging
import math
import os
import re
import textwrap
import time
from collections import namedtuple
from enum import Enum
from typing import Callable, Optional

import lark
import lark.parsers
import numpy as np

from ppp_logging import DEBUG_LEVEL
from ppp_wildcards import PPPWildcards


class PromptPostProcessor:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """
    The PromptPostProcessor class is responsible for processing and manipulating prompt strings.
    """

    NAME = "Prompt Post-Processor"
    VERSION = (2, 5, 1)

    class IFWILDCARDS_CHOICES(Enum):
        ignore = "ignore"
        remove = "remove"
        warn = "warn"
        stop = "stop"

    DEFAULT_STN_SEPARATOR = ", "
    DEFAULT_PONY_SUBSTRINGS = ",".join(["pony", "pny", "pdxl"])
    DEFAULT_CHOICE_SEPARATOR = ", "
    WILDCARD_WARNING = '(WARNING TEXT "INVALID WILDCARD" IN BRIGHT RED:1.5)\nBREAK '
    WILDCARD_STOP = "INVALID WILDCARD! {0}\nBREAK "
    UNPROCESSED_STOP = "UNPROCESSED CONSTRUCTS!\nBREAK "

    def __init__(
        self,
        logger: logging.Logger,
        interrupt: Optional[Callable],
        model_info: dict[str, any],
        options: Optional[dict[str, any]] = None,
        grammar_content: Optional[str] = None,
        wildcards_obj: PPPWildcards = None,
    ):
        """
        Initializes the PPP object.

        Args:
            logger: The logger object.
            interrupt: The interrupt function.
            model_info: A dictionary with information for the loaded model.
            options: Optional. The options dictionary for configuring PPP behavior.
            grammar_content: Optional. The grammar content to be used for parsing.
            wildcards_obj: Optional. The wildcards object to be used for processing wildcards.
        """
        self.logger = logger
        self.rng = np.random.default_rng()  # gets seeded on each process prompt call
        self.the_interrupt = interrupt
        self.options = options
        self.model_info = model_info
        self.wildcard_obj = wildcards_obj

        # General options
        self.debug_level = DEBUG_LEVEL(options.get("debug_level", DEBUG_LEVEL.none.value))
        self.pony_substrings = list(
            x.strip() for x in (str(options.get("pony_substrings", self.DEFAULT_PONY_SUBSTRINGS))).split(",")
        )
        # Wildcards options
        self.wil_process_wildcards = options.get("process_wildcards", True)
        self.wil_keep_choices_order = options.get("keep_choices_order", False)
        self.wil_choice_separator = options.get("choice_separator", self.DEFAULT_CHOICE_SEPARATOR)
        self.wil_ifwildcards = self.IFWILDCARDS_CHOICES(
            options.get("if_wildcards", self.IFWILDCARDS_CHOICES.ignore.value)
        )
        # Send to negative options
        self.stn_ignore_repeats = options.get("stn_ignore_repeats", True)
        self.stn_join_attention = options.get("stn_join_attention", True)
        self.stn_separator = options.get("stn_separator", self.DEFAULT_STN_SEPARATOR)
        # Cleanup options
        self.cup_extraspaces = options.get("cleanup_extra_spaces", True)
        self.cup_emptyconstructs = options.get("cleanup_empty_constructs", True)
        self.cup_extraseparators = options.get("cleanup_extra_separators", True)
        self.cup_extraseparators2 = options.get("cleanup_extra_separators2", True)
        self.cup_breaks = options.get("cleanup_breaks", True)
        self.cup_breaks_eol = options.get("cleanup_breaks_eol", False)
        self.cup_ands = options.get("cleanup_ands", True)
        self.cup_ands_eol = options.get("cleanup_ands_eol", False)
        self.cup_extranetworktags = options.get("cleanup_extranetwork_tags", False)
        # Remove options
        self.rem_removeextranetworktags = options.get("remove_extranetwork_tags", False)

        # if self.debug_level != DEBUG_LEVEL.none:
        #    self.logger.info(f"Detected model info: {model_info}")

        # Process with lark (debug with https://www.lark-parser.org/ide/)
        if grammar_content is None:
            grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
            with open(grammar_filename, "r", encoding="utf-8") as file:
                grammar_content = file.read()
        self.parser_complete = lark.Lark(
            grammar_content,
            propagate_positions=True,
        )
        self.parser_choice = lark.Lark(
            grammar_content,
            propagate_positions=True,
            start="choice",
        )
        self.parser_choicesoptions = lark.Lark(
            grammar_content,
            propagate_positions=True,
            start="choicesoptions",
        )
        self.__init_sysvars()
        self.user_variables = {}

    def interrupt(self):
        if self.the_interrupt is not None:
            self.the_interrupt()

    def formatOutput(self, text: str) -> str:
        """
        Formats the output text by encoding it using unicode_escape and decoding it using utf-8.

        Args:
            text (str): The input text to be formatted.

        Returns:
            str: The formatted output text.
        """
        return text.encode("unicode_escape").decode("utf-8")

    def __init_sysvars(self):
        self.system_variables = {}
        sdchecks = {
            "sd1": self.model_info.get("is_sd1", False),
            "sd2": self.model_info.get("is_sd2", False),
            "sdxl": self.model_info.get("is_sdxl", False),
            "sd3": self.model_info.get("is_sd3", False),
            "flux": self.model_info.get("is_flux", False),
            "": True,
        }
        self.system_variables["_sd"] = [k for k, v in sdchecks.items() if v][0]
        model_filename = self.model_info.get("model_filename", "")
        is_pony = any(s in model_filename.lower() for s in self.pony_substrings)
        is_ssd = self.model_info.get("is_ssd", False)
        self.system_variables["_sdfullname"] = model_filename
        self.system_variables["_sdname"] = os.path.basename(model_filename)
        self.system_variables["_is_sd1"] = sdchecks["sd1"]
        self.system_variables["_is_sd2"] = sdchecks["sd2"]
        self.system_variables["_is_sdxl"] = sdchecks["sdxl"]
        self.system_variables["_is_ssd"] = is_ssd
        self.system_variables["_is_sdxl_no_ssd"] = sdchecks["sdxl"] and not is_ssd
        self.system_variables["_is_pony"] = sdchecks["sdxl"] and is_pony
        self.system_variables["_is_sdxl_no_pony"] = sdchecks["sdxl"] and not is_pony
        self.system_variables["_is_sd3"] = sdchecks["sd3"]
        self.system_variables["_is_sd"] = sdchecks["sd1"] or sdchecks["sd2"] or sdchecks["sdxl"] or sdchecks["sd3"]
        self.system_variables["_is_flux"] = sdchecks["flux"]

    def __add_to_insertion_points(
        self, negative_prompt: str, add_at_insertion_point: list[str], insertion_at: list[tuple[int, int]]
    ) -> str:
        """
        Adds the negative prompt to the insertion points.

        Args:
            negative_prompt (str): The negative prompt to be added.
            add_at_insertion_point (list): A list of insertion points.
            insertion_at (list): A list of insertion blocks.

        Returns:
            str: The modified negative prompt.
        """
        ordered_range = sorted(
            range(10), key=lambda x: insertion_at[x][0] if insertion_at[x] is not None else float("-inf"), reverse=True
        )
        for n in ordered_range:
            if insertion_at[n] is not None:
                ipp = insertion_at[n][0]
                ipl = insertion_at[n][1] - insertion_at[n][0]
                if negative_prompt[ipp - len(self.stn_separator) : ipp] == self.stn_separator:
                    ipp -= len(self.stn_separator)  # adjust for existing start separator
                    ipl += len(self.stn_separator)
                add_at_insertion_point[n].insert(0, negative_prompt[:ipp])
                if negative_prompt[ipp + ipl : ipp + ipl + len(self.stn_separator)] == self.stn_separator:
                    ipl += len(self.stn_separator)  # adjust for existing end separator
                endPart = negative_prompt[ipp + ipl :]
                if len(endPart) > 0:
                    add_at_insertion_point[n].append(endPart)
                negative_prompt = self.stn_separator.join(add_at_insertion_point[n])
            else:
                ipp = 0
                if negative_prompt.startswith(self.stn_separator):
                    ipp = len(self.stn_separator)
                add_at_insertion_point[n].append(negative_prompt[ipp:])
                negative_prompt = self.stn_separator.join(add_at_insertion_point[n])
        return negative_prompt

    def __add_to_start(self, negative_prompt: str, add_at_start: list[str]) -> str:
        """
        Adds the elements in `add_at_start` list to the start of the `negative_prompt` string.

        Args:
            negative_prompt (str): The original negative prompt string.
            add_at_start (list): The list of elements to be added at the start of the negative prompt.

        Returns:
            str: The updated negative prompt string with the elements added at the start.
        """
        if len(negative_prompt) > 0:
            ipp = 0
            if negative_prompt.startswith(self.stn_separator):
                ipp = len(self.stn_separator)  # adjust for existing end separator
            add_at_start.append(negative_prompt[ipp:])
        negative_prompt = self.stn_separator.join(add_at_start)
        return negative_prompt

    def __add_to_end(self, negative_prompt: str, add_at_end: list[str]) -> str:
        """
        Adds the elements in `add_at_end` list to the end of `negative_prompt` string.

        Args:
            negative_prompt (str): The original negative prompt string.
            add_at_end (list): The list of elements to be added at the end of `negative_prompt`.

        Returns:
            str: The updated negative prompt string with elements added at the end.
        """
        if len(negative_prompt) > 0:
            ipl = len(negative_prompt)
            if negative_prompt.endswith(self.stn_separator):
                ipl -= len(self.stn_separator)  # adjust for existing start separator
            add_at_end.insert(0, negative_prompt[:ipl])
        negative_prompt = self.stn_separator.join(add_at_end)
        return negative_prompt

    def __cleanup(self, text: str) -> str:
        """
        Trims the given text based on the specified cleanup options.

        Args:
            text (str): The text to be cleaned up.

        Returns:
            str: The resulting text.
        """
        escapedSeparator = re.escape(self.stn_separator)
        if self.cup_extraseparators:
            #
            # sendtonegative separator
            #
            # collapse separators
            text = re.sub(r"(?:\s*" + escapedSeparator + r"\s*){2,}", self.stn_separator, text)
            # remove separator after starting parenthesis or bracket
            text = re.sub(r"(\s*" + escapedSeparator + r"\s*[([])(?:\s*" + escapedSeparator + r"\s*)+", r"\1", text)
            # remove before colon or ending parenthesis or bracket
            text = re.sub(r"(?:\s*" + escapedSeparator + r"\s*)+([:)\]]\s*" + escapedSeparator + r"\s*)", r"\1", text)
        if self.cup_extraseparators2:
            # remove at start of prompt or line
            text = re.sub(r"^(?:\s*" + escapedSeparator + r"\s*)+", "", text, flags=re.MULTILINE)
            # remove at end of prompt or line
            text = re.sub(r"(?:\s*" + escapedSeparator + r"\s*)+$", "", text, flags=re.MULTILINE)
        if self.cup_extraseparators:
            #
            # regular comma separator
            #
            # collapse separators
            text = re.sub(r"(?:\s*,\s*){2,}", ", ", text)
            # remove separators after starting parenthesis or bracket
            text = re.sub(r"(\s*,\s*[([])(?:\s*,\s*)+", r"\1", text)
            # remove separators before colon or ending parenthesis or bracket
            text = re.sub(r"(?:\s*,\s*)+([:)\]]\s*,\s*)", r"\1", text)
        if self.cup_extraseparators2:
            # remove at start of prompt or line
            text = re.sub(r"^(?:\s*,\s*)+", "", text, flags=re.MULTILINE)
            # remove at end of prompt or line
            text = re.sub(r"(?:\s*,\s*)+$", "", text, flags=re.MULTILINE)
        if self.cup_breaks_eol:
            # replace spaces before break with EOL
            text = re.sub(r"[, ]+BREAK\b", "\nBREAK", text)
        if self.cup_breaks:
            # collapse separators and commas before BREAK
            text = re.sub(r"[, ]+BREAK\b", " BREAK", text)
            # collapse separators and commas after BREAK
            text = re.sub(r"\bBREAK[, ]+", "BREAK ", text)
            # collapse separators and commas around BREAK
            text = re.sub(r"[, ]+BREAK[, ]+", " BREAK ", text)
            # collapse BREAKs
            text = re.sub(r"\bBREAK(?:\s+BREAK)+\b", " BREAK ", text)
            # remove spaces between start of line and BREAK
            text = re.sub(r"^[ ]+BREAK\b", "BREAK", text, flags=re.MULTILINE)
            # remove spaces between BREAK and end of line
            text = re.sub(r"\bBREAK[ ]+$", "BREAK", text, flags=re.MULTILINE)
            # remove at start of prompt
            text = re.sub(r"\A(?:\s*BREAK\b\s*)+", "", text)
            # remove at end of prompt
            text = re.sub(r"(?:\s*\bBREAK\s*)+\Z", "", text)
        if self.cup_ands:
            # collapse ANDs with space after
            text = re.sub(r"\bAND(?:\s+AND)+\s+", "AND ", text)
            # collapse ANDs without space after
            text = re.sub(r"\bAND(?:\s+AND)+\b", "AND", text)
            # collapse separators and spaces before ANDs
            text = re.sub(r"[, ]+AND\b", " AND", text)
            # collapse separators and spaces after ANDs
            text = re.sub(r"\bAND[, ]+", "AND ", text)
            # remove at start of prompt
            text = re.sub(r"\A(?:AND\b\s*)+", "", text)
            # remove at end of prompt
            text = re.sub(r"(\s*\bAND)+\Z", "", text)
        if self.cup_extranetworktags:
            # remove spaces before <
            text = re.sub(r"\B\s+<(?!!)", "<", text)
            # remove spaces after >
            text = re.sub(r">\s+\B", ">", text)
        if self.cup_extraspaces:
            # remove spaces before comma
            text = re.sub(r"[ ]+,", ",", text)
            # remove spaces at end of line
            text = re.sub(r"[ ]+$", "", text, flags=re.MULTILINE)
            # remove spaces at start of line
            text = re.sub(r"^[ ]+", "", text, flags=re.MULTILINE)
            # remove extra whitespace after starting parenthesis or bracket
            text = re.sub(r"([,\.;\s]+[([])\s+", r"\1", text)
            # remove extra whitespace before ending parenthesis or bracket
            text = re.sub(r"\s+([)\]][,\.;\s]+)", r"\1", text)
            # remove empty lines
            text = re.sub(r"(?:^|\n)[ ]*\n", "\n", text)
            text = re.sub(r"\n[ ]*\n$", "\n", text)
            # collapse spaces
            text = re.sub(r"[ ]{2,}", " ", text)
            # remove spaces at start and end
            text = text.strip()
        return text

    def __processprompts(self, prompt, negative_prompt):
        self.user_variables = {}

        # Process prompt
        p_processor = self.TreeProcessor(self)
        p_parsed = self.parse_prompt("prompt", prompt, self.parser_complete)
        prompt = p_processor.start_visit("prompt", p_parsed, False)

        # Process negative prompt
        n_processor = self.TreeProcessor(self)
        n_parsed = self.parse_prompt("negative prompt", negative_prompt, self.parser_complete)
        negative_prompt = n_processor.start_visit("negative prompt", n_parsed, True)

        # Insertions in the negative prompt
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(self.formatOutput(f"New negative additions: {p_processor.add_at}"))
            self.logger.debug(self.formatOutput(f"New negative indexes: {n_processor.insertion_at}"))
        negative_prompt = self.__add_to_insertion_points(
            negative_prompt, p_processor.add_at["insertion_point"], n_processor.insertion_at
        )
        if len(p_processor.add_at["start"]) > 0:
            negative_prompt = self.__add_to_start(negative_prompt, p_processor.add_at["start"])
        if len(p_processor.add_at["end"]) > 0:
            negative_prompt = self.__add_to_end(negative_prompt, p_processor.add_at["end"])

        # Clean up
        prompt = self.__cleanup(prompt)
        negative_prompt = self.__cleanup(negative_prompt)

        # Check for wildcards not processed
        foundP = len(p_processor.detectedWildcards) > 0
        foundNP = len(n_processor.detectedWildcards) > 0
        if foundP or foundNP:
            self.logger.error("Found unprocessed wildcards!")
            ppwl = ", ".join(p_processor.detectedWildcards)
            npwl = ", ".join(n_processor.detectedWildcards)
            if foundP:
                self.logger.error(self.formatOutput(f"In the positive prompt: {ppwl}"))
            if foundNP:
                self.logger.error(self.formatOutput(f"In the negative prompt: {npwl}"))
            if self.wil_ifwildcards == self.IFWILDCARDS_CHOICES.warn:
                prompt = self.WILDCARD_WARNING + prompt
            elif self.wil_ifwildcards == self.IFWILDCARDS_CHOICES.stop:
                self.logger.error("Stopping the generation.")
                if foundP:
                    prompt = self.WILDCARD_STOP.format(ppwl) + prompt
                if foundNP:
                    negative_prompt = self.WILDCARD_STOP.format(npwl) + negative_prompt
                self.interrupt()
        return prompt, negative_prompt

    def process_prompt(
        self,
        original_prompt: str,
        original_negative_prompt: str,
        seed: int = 0,
    ):
        """
        Process the prompt and negative prompt by moving content to the negative prompt, and cleaning up.

        Args:
            original_prompt (str): The original prompt.
            original_negative_prompt (str): The original negative prompt.
            seed (int): The seed.

        Returns:
            tuple: A tuple containing the processed prompt and negative prompt.
        """
        try:
            if seed == -1:
                seed = np.random.randint(0, 2**32)
            self.rng = np.random.default_rng(seed & 0xFFFFFFFF)
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.debug_level = DEBUG_LEVEL(self.options.get("debug_level", DEBUG_LEVEL.none.value))
            if self.debug_level != DEBUG_LEVEL.none:
                self.logger.info(f"System variables: {self.system_variables}")
                self.logger.info(f"Input seed: {seed}")
                self.logger.info(self.formatOutput(f"Input prompt: {prompt}"))
                self.logger.info(self.formatOutput(f"Input negative_prompt: {negative_prompt}"))
            t1 = time.time()
            prompt, negative_prompt = self.__processprompts(prompt, negative_prompt)
            t2 = time.time()
            if self.debug_level != DEBUG_LEVEL.none:
                self.logger.info(self.formatOutput(f"Result prompt: {prompt}"))
                self.logger.info(self.formatOutput(f"Result negative_prompt: {negative_prompt}"))
                self.logger.info(f"Process prompt pair time: {t2 - t1:.3f} seconds")

            # Check for constructs not processed due to parsing problems
            fullcontent: str = prompt + negative_prompt
            if fullcontent.find("<ppp:") >= 0:
                self.logger.error("Found unprocessed constructs in prompt or negative prompt! Stopping the generation.")
                prompt = self.UNPROCESSED_STOP + prompt
                self.interrupt()
            return prompt, negative_prompt
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception(e)
            return original_prompt, original_negative_prompt

    def parse_prompt(self, prompt_description: str, prompt: str, parser: lark.Lark, raise_parsing_error: bool = False):
        t1 = time.time()
        try:
            if self.debug_level == DEBUG_LEVEL.full:
                self.logger.debug(self.formatOutput(f"Parsing {prompt_description}: '{prompt}'"))
            parsed_prompt = parser.parse(prompt)
            # we store the contents so we can use them later even if the meta position is not valid anymore
            for n in parsed_prompt.iter_subtrees():
                if isinstance(n, lark.Tree):
                    if n.meta.empty:
                        n.meta.content = ""
                    else:
                        n.meta.content = prompt[n.meta.start_pos : n.meta.end_pos]
        except lark.exceptions.UnexpectedInput:
            if raise_parsing_error:
                raise
            self.logger.exception(self.formatOutput(f"Parsing failed on prompt!: {prompt}"))
        t2 = time.time()
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug("Tree:\n" + textwrap.indent(re.sub(r"\n$", "", parsed_prompt.pretty()), "    "))
            self.logger.debug(f"Parse {prompt_description} time: {t2 - t1:.3f} seconds")
        return parsed_prompt

    class TreeProcessor(lark.visitors.Interpreter):
        """
        A class for interpreting and processing a tree generated by the prompt parser.

        Args:
            ppp (PromptPostProcessor): The PromptPostProcessor object.

        Attributes:
            add_at (dict): The dictionary to store the content to be added at different positions of the negative prompt.
            insertion_at (list): The list of insertion points in the negative prompt.
            detectedWildcards (list): The list of detected invalid wildcards or choices.
            result (str): The final processed prompt.
        """

        def __init__(self, ppp: "PromptPostProcessor"):
            super().__init__()
            self.__ppp = ppp
            self.AccumulatedShell = namedtuple("AccumulatedShell", ["type", "data"])
            self.NegTag = namedtuple("NegTag", ["start", "end", "content", "parameters", "shell"])
            self.__shell: list[self.AccumulatedShell] = []
            self.__negtags: list[self.NegTag] = []
            self.__already_processed: list[str] = []
            self.__is_negative = False
            self.add_at: dict = {"start": [], "insertion_point": [[] for x in range(10)], "end": []}
            self.insertion_at: list[tuple[int, int]] = [None for x in range(10)]
            self.detectedWildcards: list[str] = []
            self.result = ""

        def start_visit(self, prompt_description: str, parsed_prompt: lark.Tree, is_negative: bool = False) -> str:
            """
            Start the visit process.

            Args:
                prompt_description (str): The description of the prompt.
                parsed_prompt (Tree): The parsed prompt.
                is_negative (bool): Whether the prompt is negative or not.

            Returns:
                str: The processed prompt.
            """
            t1 = time.time()
            self.__is_negative = is_negative
            if self.__ppp.debug_level != DEBUG_LEVEL.none:
                self.__ppp.logger.info(f"Processing {prompt_description}...")
            self.visit(parsed_prompt)
            t2 = time.time()
            if self.__ppp.debug_level != DEBUG_LEVEL.none:
                self.__ppp.logger.info(f"Process {prompt_description} time: {t2 - t1:.3f} seconds")
            return self.result

        def __visit(
            self,
            node: lark.Tree | lark.Token | list[lark.Tree | lark.Token] | None,
            restore_state: bool = False,
            discard_content: bool = False,
        ) -> str:
            """
            Visit a node in the tree and process it or accumulate its value if it is a Token.

            Args:
                node (Tree|Token|list): The node or list of nodes to visit.
                restore_state (bool): Whether to restore the state after visiting the node.
                discard_content (bool): Whether to discard the content of the node.

            Returns:
                str: The result of the visit.
            """
            backup_result = self.result
            if restore_state:
                backup_shell = self.__shell.copy()
                backup_negtags = self.__negtags.copy()
                backup_already_processed = self.__already_processed.copy()
                backup_add_at = self.add_at.copy()
                backup_insertion_at = self.insertion_at.copy()
                backup_detectedwildcards = self.detectedWildcards.copy()
            if node is not None:
                if isinstance(node, list):
                    for child in node:
                        self.__visit(child)
                elif isinstance(node, lark.Tree):
                    self.visit(node)
                elif isinstance(node, lark.Token):
                    self.result += node
            added_result = self.result[len(backup_result) :]
            if discard_content or restore_state:
                self.result = backup_result
            if restore_state:
                self.__shell = backup_shell
                self.__negtags = backup_negtags
                self.__already_processed = backup_already_processed
                self.add_at = backup_add_at
                self.insertion_at = backup_insertion_at
                self.detectedWildcards = backup_detectedwildcards
            return added_result

        def __get_original_node_content(self, node: lark.Tree | lark.Token, default=None) -> str:
            return (
                node.meta.content
                if hasattr(node, "meta") and node.meta is not None and not node.meta.empty
                else default
            )

        def __get_user_variable_value(self, name: str, default="", evaluate=True) -> str:
            if evaluate:
                v = self.__ppp.user_variables.get(name, default)
                if isinstance(v, lark.Tree):
                    v = self.__visit(v, True)
            else:
                v = (
                    self.__ppp.user_variables[name]
                    if isinstance(self.__ppp.user_variables[name], str)
                    else self.__get_original_node_content(
                        self.__ppp.user_variables[name], default or "not evaluated yet"
                    )
                )
            return v

        def __set_user_variable_value(self, name: str, value: str):
            self.__ppp.user_variables[name] = value

        def __remove_user_variable(self, name: str):
            if name in self.__ppp.user_variables:
                del self.__ppp.user_variables[name]

        def __debug_end(self, construct: str, start_result: str, duration: float, info=None):
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                info = f"({info}) " if info is not None and info != "" else ""
                output = self.result[len(start_result) :]
                if output != "":
                    output = f" >> '{output}'"
                self.__ppp.logger.debug(
                    self.__ppp.formatOutput(f"TreeProcessor.{construct} {info}({duration:.3f} seconds){output}")
                )

        def __eval_condition(self, cond_var: str, cond_comp: str, cond_value: str | list[str]) -> bool:
            """
            Evaluate a condition based on the given variable, comparison, and value.

            Args:
                cond_var (str): The variable to be compared.
                cond_comp (str): The comparison operator.
                cond_value (str or list[str]): The value to be compared with.

            Returns:
                bool: The result of the condition evaluation.
            """
            var_value = self.__ppp.system_variables.get(cond_var, self.__get_user_variable_value(cond_var, None))
            if var_value is None:
                var_value = ""
                self.__ppp.logger.warning(f"Unknown variable {cond_var}")
            if isinstance(var_value, str):
                var_value = var_value.lower()
            if isinstance(cond_value, list):
                comp_ops = {
                    "contains": lambda x, y: y in x,
                    "in": lambda x, y: x == y,
                }
            else:
                cond_value = [cond_value]
                comp_ops = {
                    "eq": lambda x, y: x == y,
                    "ne": lambda x, y: x != y,
                    "gt": lambda x, y: x > y,
                    "lt": lambda x, y: x < y,
                    "ge": lambda x, y: x >= y,
                    "le": lambda x, y: x <= y,
                    "contains": lambda x, y: y in x,
                    "truthy": lambda x, y: bool(x),
                }
            if cond_comp not in comp_ops:
                return False
            cond_value_adjusted = list(
                (
                    c[1:-1].lower()
                    if c.startswith('"') or c.startswith("'")
                    else True if c.lower() == "true" else False if c.lower() == "false" else int(c)
                )
                for c in cond_value
            )
            result = False
            for c in cond_value_adjusted:
                var_value_adjusted = (
                    var_value
                    if isinstance(c, str)
                    else (
                        True
                        if isinstance(c, bool) and var_value != "false" and var_value is not False
                        else (
                            False
                            if isinstance(c, bool) and (var_value != "true" or var_value is False)
                            else int(var_value)
                        )
                    )
                )
                result = comp_ops[cond_comp](var_value_adjusted, c)
                if result:
                    break
            return result

        def __evaluate_if(self, condition: lark.Tree) -> bool:
            """
            Evaluate an if condition based on the given condition tree.

            Args:
                condition (Node): The condition tree to be evaluated.

            Returns:
                bool: The result of the if condition evaluation.
            """
            get_value = lambda n: n.value  # pylint: disable=unnecessary-lambda-assignment
            # if hasattr(condition, "children"):
            get_children = lambda n: n.children  # pylint: disable=unnecessary-lambda-assignment
            # else:
            #    get_children = lambda n: n  # pylint: disable=unnecessary-lambda-assignment
            # get_value = lambda n: n  # pylint: disable=unnecessary-lambda-assignment
            individualcondition = get_children(condition)[0]
            # we get the name of the variable and check for a preceding not
            invert = False
            first = get_value(get_children(individualcondition)[0])
            if first == "not":
                invert = True
                cond_var = get_value(get_children(individualcondition)[1])
                poscomp = 2
            else:
                cond_var = first
                poscomp = 1
            if poscomp >= len(get_children(individualcondition)):
                # no condition, just a variable
                cond_comp = "truthy"
                cond_value = "true"
            else:
                # we get the comparison (with possible not) and the value
                cond_comp = get_value(get_children(individualcondition)[poscomp])
                if cond_comp == "not":
                    invert = not invert
                    poscomp += 1
                    cond_comp = get_value(get_children(individualcondition)[poscomp])
                poscomp += 1
                cond_value_node = get_children(individualcondition)[poscomp]
                cond_value = (
                    list(get_value(v) for v in get_children(cond_value_node))
                    if isinstance(cond_value_node, (lark.Tree, list))
                    else cond_value_node.value if isinstance(cond_value_node, lark.Token) else cond_value_node
                )
            condresult = self.__eval_condition(cond_var, cond_comp, cond_value)
            if invert:
                condresult = not condresult
            return condresult

        def promptcomp(self, tree: lark.Tree):
            """
            Process a prompt composition construct in the tree.
            """
            start_result = self.result
            t1 = time.time()
            self.__visit(tree.children[0])
            if len(tree.children) > 1:
                if tree.children[1] is not None:
                    self.result += f":{tree.children[1]}"
                for i in range(2, len(tree.children), 3):
                    if self.__ppp.cup_ands:
                        self.result = re.sub(r"[, ]+$", "\n" if self.__ppp.cup_ands_eol else " ", self.result)
                    if self.result[-1:].isalnum():  # add space if needed
                        self.result += " "
                    self.result += "AND"
                    added_result = self.__visit(tree.children[i + 1], False, True)
                    if self.__ppp.cup_ands:
                        added_result = re.sub(r"^[, ]+", " ", added_result)
                    if added_result[0:1].isalnum():  # add space if needed
                        added_result = " " + added_result
                    self.result += added_result
                    if tree.children[i + 2] is not None:
                        self.result += f":{tree.children[i+2]}"
            t2 = time.time()
            self.__debug_end("promptcomp", start_result, t2 - t1)

        def scheduled(self, tree: lark.Tree):
            """
            Process a scheduling construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.time()
            before = tree.children[0]
            after = tree.children[-2]
            pos_str = tree.children[-1]
            pos = float(pos_str)
            if pos >= 1:
                pos = int(pos)
            # self.__shell.append(self.AccumulatedShell("sc", pos))
            self.result += "["
            if before is not None:
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(f"Shell scheduled before with position {pos}")
                self.__shell.append(self.AccumulatedShell("scb", pos))
                self.__visit(before)
                self.__shell.pop()
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(f"Shell scheduled after with position {pos}")
            self.__shell.append(self.AccumulatedShell("sca", pos))
            self.result += ":"
            self.__visit(after)
            self.__shell.pop()
            if self.__ppp.cup_emptyconstructs and self.result == start_result + "[:":
                self.result = start_result
            else:
                self.result += f":{pos_str}]"
            # self.__shell.pop()
            t2 = time.time()
            self.__debug_end("scheduled", start_result, t2 - t1, pos_str)

        def alternate(self, tree: lark.Tree):
            """
            Process an alternation construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.time()
            # self.__shell.append(self.AccumulatedShell("al", len(tree.children)))
            self.result += "["
            for i, opt in enumerate(tree.children):
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(f"Shell alternate option {i+1}")
                self.__shell.append(self.AccumulatedShell("alo", {"pos": i + 1, "len": len(tree.children)}))
                if i > 0:
                    self.result += "|"
                self.__visit(opt)
                self.__shell.pop()
            self.result += "]"
            if self.__ppp.cup_emptyconstructs and self.result == start_result + "[]":
                self.result = start_result
            # self.__shell.pop()
            t2 = time.time()
            self.__debug_end("alternate", start_result, t2 - t1)

        def emphasized(self, tree: lark.Tree):
            """
            Process a attention change construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.time()
            weight_str = tree.children[-1]
            if weight_str is not None:
                weight = float(weight_str)
            else:
                weight_str = ""
                weight = 1.1
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(f"Shell attention with weight {weight}")
            self.__shell.append(self.AccumulatedShell("at", weight))
            self.result += "("
            self.__visit(tree.children[:-1])
            if self.__ppp.cup_emptyconstructs and self.result == start_result + "(":
                self.result = start_result
            else:
                if weight_str != "":
                    self.result += f":{weight_str}"
                self.result += ")"
            self.__shell.pop()
            t2 = time.time()
            self.__debug_end("emphasized", start_result, t2 - t1, weight_str)

        def deemphasized(self, tree: lark.Tree):
            """
            Process a decrease attention construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.time()
            weight = 0.9
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(f"Shell attention with weight {weight}")
            self.__shell.append(self.AccumulatedShell("at", weight))
            self.result += "["
            self.__visit(tree.children)
            if self.__ppp.cup_emptyconstructs and self.result == start_result + "[":
                self.result = start_result
            else:
                self.result += "]"
            self.__shell.pop()
            t2 = time.time()
            self.__debug_end("deemphasized", start_result, t2 - t1)

        def commandstn(self, tree: lark.Tree):
            """
            Process a send to negative command in the tree and add it to the list of negative tags.
            """
            start_result = self.result
            info = None
            t1 = time.time()
            if not self.__is_negative:
                negtagparameters = tree.children[0]
                if negtagparameters is not None:
                    parameters = negtagparameters.value
                else:
                    parameters = ""
                content = self.__visit(tree.children[1::], False, True)
                self.__negtags.append(
                    self.NegTag(len(self.result), len(self.result), content, parameters, self.__shell.copy())
                )
                info = f"with {parameters or 'no parameters'} : {content}"
            else:
                self.__ppp.logger.warning("Ignored negative command in negative prompt")
                self.__visit(tree.children[1::])
            t2 = time.time()
            self.__debug_end("commandstn", start_result, t2 - t1, info)

        def commandstni(self, tree: lark.Tree):
            """
            Process a send to negative insertion point command in the tree and add it to the list of negative tags.
            """
            start_result = self.result
            info = None
            t1 = time.time()
            if self.__is_negative:
                negtagparameters = tree.children[0]
                if negtagparameters is not None:
                    parameters = negtagparameters.value
                else:
                    parameters = ""
                self.__negtags.append(
                    self.NegTag(len(self.result), len(self.result), "", parameters, self.__shell.copy())
                )
                info = f"with {parameters or 'no parameters'}"
            else:
                self.__ppp.logger.warning("Ignored negative insertion point command in positive prompt")
            t2 = time.time()
            self.__debug_end("commandstni", start_result, t2 - t1, info)

        def __varset(
            self,
            command: str,
            variable: str,
            immediateevaluation: str | None,
            adding: str | None,
            content: lark.Tree | None,
        ):
            """
            Process a generic set command in the tree.
            """
            t1 = time.time()
            start_result = self.result
            if variable.startswith("_"):
                self.__ppp.logger.warning(f"Invalid variable name '{variable}' detected!")
                self.__ppp.interrupt()
                return
            info = variable
            value_description = self.__get_original_node_content(content, None)
            value = content
            if adding is not None:
                info += f" += '{value_description}'"
                raw_oldvalue = self.__ppp.user_variables.get(variable, None)
                if raw_oldvalue is None:
                    newvalue = value
                    self.__ppp.logger.warning(f"Unknown variable {variable}")
                elif isinstance(raw_oldvalue, str):
                    newvalue = lark.Tree(
                        lark.Token("RULE", "varvalue"),
                        [lark.Token("plain", raw_oldvalue), value],
                        # Meta should be {"content": raw_oldvalue + value},
                    )
                else:
                    newvalue = lark.Tree(
                        lark.Token("RULE", "varvalue"),
                        [raw_oldvalue, value],
                        # Meta should be {"content": raw_oldvalue.meta.content + value.meta.content},
                    )
            else:
                newvalue = value
            if immediateevaluation is not None:
                newvalue = self.__visit(newvalue, False, True)
                info += " =! "
            else:
                info += " = "
            self.__set_user_variable_value(variable, newvalue)
            currentvalue = self.__get_user_variable_value(variable, None, False)
            if currentvalue is None:
                info += "not evaluated yet"
            else:
                info += f"'{currentvalue}'"
            t2 = time.time()
            self.__debug_end(command, start_result, t2 - t1, info)

        def variableset(self, tree: lark.Tree):
            """
            Process a DP set variable command in the tree and add it to the dictionary of variables.
            """
            self.__varset("variableset", tree.children[0], tree.children[2], tree.children[1], tree.children[3])

        def commandset(self, tree: lark.Tree):
            """
            Process a set command in the tree and add it to the dictionary of variables.
            """
            self.__varset("commandset", tree.children[0], tree.children[1], tree.children[2], tree.children[3])

        def __varecho(self, command: str, variable: str, default: lark.Tree | None):
            """
            Process a generic echo command in the tree.
            """
            t1 = time.time()
            start_result = self.result
            value = self.__get_user_variable_value(variable, None)
            if default is not None:
                default_value = self.__visit(default, True)  # for log
            if value is None:
                if default is not None:
                    value = self.__visit(default, False, True)
                else:
                    value = ""
                    self.__ppp.logger.warning(f"Unknown variable {variable}")
            self.result += value
            t2 = time.time()
            info = variable
            if default is not None:
                info += f" with default '{default_value}'"
            self.__debug_end(command, start_result, t2 - t1, info)

        def variableuse(self, tree: lark.Tree):
            """
            Process a DP use variable command in the tree.
            """
            self.__varecho("variableuse", tree.children[0], tree.children[1])

        def commandecho(self, tree: lark.Tree):
            """
            Process an echo command in the tree.
            """
            self.__varecho("commandecho", tree.children[0], tree.children[1])

        def commandif(self, tree: lark.Tree):
            """
            Process an if command in the tree.
            """
            t1 = time.time()
            start_result = self.result
            for i, n in enumerate(tree.children):
                content = n.children[-1]
                if len(n.children) == 2:  # its not an else
                    # has a condition
                    condition = n.children[0]
                    c = self.__get_original_node_content(condition, f"condition {i}")
                    if self.__evaluate_if(condition):
                        self.__visit(content)
                        t2 = time.time()
                        self.__debug_end("commandif", start_result, t2 - t1, c)
                        return
                else:  # its an else
                    self.__visit(content)
                    t2 = time.time()
                    self.__debug_end("commandif", start_result, t2 - t1, "else")
                    return

        def extranetworktag(self, tree: lark.Tree):
            """
            Process an extra network construct in the tree.
            """
            t1 = time.time()
            start_result = self.result
            if not self.__ppp.rem_removeextranetworktags:
                # keep extra network construct
                self.result += self.__get_original_node_content(tree, f"<{tree.children[0]}>")
            t2 = time.time()
            self.__debug_end("extranetworktag", start_result, t2 - t1)

        def __get_choices(self, options: lark.Tree | None, choice_values: list[lark.Tree]) -> str:
            """
            Select choices based on the options.

            Args:
                is_wildcard (bool): A flag indicating whether the choices are from a wildcard.
                options (Tree): The tree object representing the options construct.
                choice_values (list[Tree]): A list of choice tree objects.

            Returns:
                str: The selected choice.
            """
            sampler: str = "~"
            repeating: bool = False
            from_value: int = 1
            to_value: int = 1
            separator: str = self.__ppp.wil_choice_separator
            if options is not None:
                if len(options.children) == 1:
                    sampler = options.children[0] if options.children[0] is not None else "~"
                else:
                    sampler = options.children[0].children[0] if options.children[0] is not None else "~"
                    repeating = options.children[1].children[0] == "r" if options.children[1] is not None else False
                    if len(options.children) == 4:
                        ifrom = 2
                        ito = 2
                        isep = 3
                    else:  # 6
                        ifrom = 2
                        ito = 3
                        isep = 4
                    from_value = int(options.children[ifrom].children[0]) if options.children[ifrom] is not None else 1
                    to_value = int(options.children[ito].children[0]) if options.children[ito] is not None else 1
                    separator = (
                        self.__visit(options.children[isep], False, True)
                        if options.children[isep] is not None
                        else self.__ppp.wil_choice_separator
                    )
            if sampler != "~":
                self.__ppp.logger.warning(f"Unsupported sampler '{sampler}' in wildcard/choices options!")
                self.__ppp.interrupt()
                return ""
            if from_value < 0:
                from_value = 1
            elif from_value > len(choice_values):
                from_value = len(choice_values)
            if to_value < 1:
                to_value = 1
            elif (to_value > len(choice_values) and not repeating) or from_value > to_value:
                to_value = len(choice_values)
            num_choices = (
                self.__ppp.rng.integers(from_value, to_value, endpoint=True) if from_value < to_value else from_value
            )
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(
                    self.__ppp.formatOutput(
                        f"Selecting {'repeating ' if repeating else ''}{num_choices} choices and separating with '{separator}'"
                    )
                )
            if num_choices > 0:
                weights = []
                included_choices = 0
                excluded_choices = 0
                excluded_weights_sum = 0
                for i, c in enumerate(choice_values):
                    c.choice_index = i  # we index them to later sort the results
                    w = float(c.children[0].children[0]) if c.children[0] is not None else 1.0
                    if w > 0 and (c.children[1] is None or self.__evaluate_if(c.children[1].children[0])):
                        weights.append(w)
                        included_choices += 1
                    else:
                        weights.append(-1)
                        excluded_choices += 1
                        excluded_weights_sum += w
                if excluded_choices > 0:  # we need to redistribute the excluded weights
                    weights = [w + excluded_weights_sum / included_choices if w >= 0 else 0.0 for w in weights]
                weights = np.array(weights)
                weights /= weights.sum()  # normalize weights
                selected_choices: list[lark.Tree] = list(
                    self.__ppp.rng.choice(choice_values, size=num_choices, p=weights, replace=repeating)
                )
                if self.__ppp.wil_keep_choices_order:
                    selected_choices = sorted(selected_choices, key=lambda x: x.choice_index)
                selected_choices_text = []
                for i, c in enumerate(selected_choices):
                    t1 = time.time()
                    choice_content = self.__visit(c.children[2], False, True)
                    t2 = time.time()
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug(
                            f"Adding choice {i+1} ({t2-t1:.3f} seconds):\n"
                            + textwrap.indent(re.sub(r"\n$", "", c.pretty()), "    ")
                        )
                    selected_choices_text.append(choice_content)
                # remove comments
                results = [re.sub(r"\s*#[^\n]*(?:\n|$)", "", r, flags=re.DOTALL) for r in selected_choices_text]
                return separator.join(results)
            return ""

        def wildcard(self, tree: lark.Tree):
            """
            Process a wildcard construct in the tree.
            """
            t1 = time.time()
            start_result = self.result
            options = tree.children[0]
            wildcard_key = tree.children[1].value
            wc = self.__get_original_node_content(tree, f"?__{wildcard_key}__")
            if self.__ppp.wil_process_wildcards:
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(f"Processing wildcard: {wildcard_key}")
                wildcard_keys = fnmatch.filter(self.__ppp.wildcard_obj.wildcards.keys(), wildcard_key)
                if len(wildcard_keys) == 0:
                    self.detectedWildcards.append(wc)
                    self.result += wc
                    t2 = time.time()
                    self.__debug_end("wildcard", start_result, t2 - t1, wc)
                    return
                variablename = None
                if tree.children[2] is not None:
                    variablename = tree.children[2].children[0]  # should be a token
                    variablevalue = self.__visit(tree.children[2].children[1], False, True)
                    variablebackup = self.__ppp.user_variables.get(variablename, None)
                    self.__remove_user_variable(variablename)
                    self.__set_user_variable_value(variablename, variablevalue)
                choice_values_obj_all = []
                for key in wildcard_keys:
                    wildcard = self.__ppp.wildcard_obj.wildcards.get(key, None)
                    if wildcard is None:
                        self.detectedWildcards.append(wc)
                        self.result += wc
                        t2 = time.time()
                        self.__debug_end("wildcard", start_result, t2 - t1, wc)
                        return
                    choice_values_obj = wildcard.get("choices_obj", None)
                    options_obj = wildcard.get("options_obj", None)
                    if choice_values_obj is None:
                        t1 = time.time()
                        choice_values_obj = []
                        choices = wildcard["choices"]
                        try:
                            options_obj = self.__ppp.parse_prompt(
                                "as choices options", choices[0], self.__ppp.parser_choicesoptions, True
                            )
                            n = 1
                        except lark.exceptions.UnexpectedInput:
                            options_obj = None
                            n = 0
                            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                                self.__ppp.logger.debug("Does not have options")
                        wildcard["options_obj"] = options_obj
                        for cv in choices[n:]:
                            try:
                                choice_values_obj.append(
                                    self.__ppp.parse_prompt("choice", cv, self.__ppp.parser_choice, True)
                                )
                            except lark.exceptions.UnexpectedInput as e:
                                self.__ppp.logger.warning(
                                    f"Error parsing choice '{cv}' in wildcard '{key}'! : {e.__class__.__name__}"
                                )
                        wildcard["choices_obj"] = choice_values_obj
                        t2 = time.time()
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(f"Processed choices for wildcard '{key}' ({t2-t1:.3f} seconds)")
                    if options_obj is not None:
                        if options is None:
                            options = options_obj
                        else:
                            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                                self.__ppp.logger.debug(f"Options for wildcard '{key}' are ignored!")
                    choice_values_obj_all += choice_values_obj
                self.result += self.__get_choices(options, choice_values_obj_all)
                if variablename is not None:
                    self.__remove_user_variable(variablename)
                    if variablebackup is not None:
                        self.__ppp.user_variables[variablename] = variablebackup
            elif self.__ppp.wil_ifwildcards != self.__ppp.IFWILDCARDS_CHOICES.remove:
                self.detectedWildcards.append(wc)
                self.result += wc
            t2 = time.time()
            self.__debug_end("wildcard", start_result, t2 - t1, f"'{wc}'")

        def choices(self, tree: lark.Tree):
            """
            Process a choices construct in the tree.
            """
            t1 = time.time()
            start_result = self.result
            options = tree.children[0]
            choice_values = tree.children[1::]
            ch = self.__get_original_node_content(tree, "?{...}")
            if self.__ppp.wil_process_wildcards:
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Processing choices:")
                self.result += self.__get_choices(options, choice_values)
            elif self.__ppp.wil_ifwildcards != self.__ppp.IFWILDCARDS_CHOICES.remove:
                self.detectedWildcards.append(ch)
                self.result += ch
            t2 = time.time()
            self.__debug_end("choices", start_result, t2 - t1, f"'{ch}'")

        def __default__(self, tree):
            t1 = time.time()
            start_result = self.result
            self.__visit(tree.children)
            t2 = time.time()
            self.__debug_end(tree.data.value, start_result, t2 - t1)

        def start(self, tree):
            self.result = ""
            t1 = time.time()
            self.__visit(tree.children)
            # process the found negative tags
            for negtag in self.__negtags:
                if self.__ppp.stn_join_attention:
                    # join consecutive attention elements
                    for i in range(len(negtag.shell) - 1, 0, -1):
                        if negtag.shell[i].type == "at" and negtag.shell[i - 1].type == "at":
                            negtag.shell[i - 1] = self.AccumulatedShell(
                                "at",
                                math.floor(100 * negtag.shell[i - 1].data * negtag.shell[i].data)
                                / 100,  # we limit the new weight to two decimals
                            )
                            negtag.shell.pop(i)
                start = ""
                end = ""
                for s in negtag.shell:
                    match s.type:
                        case "at":
                            if s.data == 0.9:
                                start += "["
                                end = "]" + end
                            elif s.data == 1.1:
                                start += "("
                                end = ")" + end
                            else:
                                start += "("
                                end = f":{s.data})" + end
                        # case "sc":
                        case "scb":
                            start += "["
                            end = f"::{s.data}]" + end
                        case "sca":
                            start += "["
                            end = f":{s.data}]" + end
                        # case "al":
                        case "alo":
                            start += "[" + ("|" * int(s.data["pos"] - 1))
                            end = ("|" * int(s.data["len"] - s.data["pos"])) + "]" + end
                content = start + negtag.content + end
                position = negtag.parameters or "s"
                if position.startswith("i"):
                    n = int(position[1])
                    self.insertion_at[n] = [negtag.start, negtag.end]
                elif len(content) > 0:
                    if content not in self.__already_processed:
                        if self.__ppp.stn_ignore_repeats:
                            self.__already_processed.append(content)
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(
                                self.__ppp.formatOutput(f"Adding content at position {position}: {content}")
                            )
                        if position == "e":
                            self.add_at["end"].append(content)
                        elif position.startswith("p"):
                            n = int(position[1])
                            self.add_at["insertion_point"][n].append(content)
                        else:  # position == "s" or invalid
                            self.add_at["start"].append(content)
                    else:
                        self.__ppp.logger.warning(self.__ppp.formatOutput(f"Ignoring repeated content: {content}"))
            t2 = time.time()
            self.__debug_end("start", "", t2 - t1)
