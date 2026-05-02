from dataclasses import replace
import os
import logging
from typing import NamedTuple, Optional
import unittest
import datetime

from ppp_classes import IFWILDCARDS_CHOICES, ONWARNING_CHOICES, PPPStateOptions
from ppp_enmappings import PPPExtraNetworkMappings  # type: ignore
from ppp_wildcards import PPPWildcards  # type: ignore
from ppp import PromptPostProcessor  # type: ignore
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory  # type: ignore


class PromptPair(NamedTuple):
    prompt: str = ""
    negative_prompt: str = ""


class OutputTuple(NamedTuple):
    prompt: str = ""
    negative_prompt: str = ""
    variables: dict[str, str] = None


class TestPromptPostProcessorBase(unittest.TestCase):
    """
    A test case class for testing the PromptPostProcessor class.
    """

    def setUp(self, enable_file_logging=False):
        """
        Set up the test case by initializing the necessary objects and configurations.

        Args:
            enable_file_logging (bool): Whether to enable logging to a file. Defaults to True.
        """
        self.enable_file_logging = enable_file_logging
        test_name = self.id().split(".")[-1]  # Extract the test method name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.enable_file_logging:
            log_filename = f"tests/logs/{test_name}_{timestamp}.log"
        else:
            log_filename = None  # Disable file logging

        self.lf = PromptPostProcessorLogFactory(log_filename)
        self.ppp_logger = self.lf.log
        self.ppp_logger.setLevel(logging.DEBUG)
        self.grammar_content = None
        self.interrupted = False
        self.defopts = PPPStateOptions(
            debug_level=DEBUG_LEVEL.full,
            on_warning=ONWARNING_CHOICES.stop,
            strict_operators=True,
            process_wildcards=True,
            if_wildcards=IFWILDCARDS_CHOICES.ignore,
            choice_separator=", ",
            keep_choices_order=False,
            stn_separator=", ",
            stn_ignore_repeats=True,
            cup_do_cleanup=True,
            cup_cleanup_variables=True,
            cup_empty_constructs=True,
            cup_extra_separators=True,
            cup_extra_separators2=True,
            cup_extra_separators_include_eol=False,
            cup_extra_spaces=True,
            cup_breaks=True,
            cup_breaks_eol=False,
            cup_ands=True,
            cup_ands_eol=False,
            cup_extranetwork_tags=True,
            cup_merge_attention=True,
            cup_remove_extranetwork_tags=False,
            do_combinatorial=False,
            combinatorial_limit=0,
        )
        self.def_env_info = {
            "app": "tests",
            "ppp_config": None,
            "model_class": "SDXL",
            "property_base": {"is_sdxl": True},
            "models_path": "./webui/models",
            "model_filename": "./webui/models/Stable-diffusion/testmodel.safetensors",
        }
        self.interrupted = False
        self.wildcards_obj = PPPWildcards(self.lf.log)
        self.extranetwork_maps_obj = PPPExtraNetworkMappings(self.lf.log)
        self.wildcards_obj.refresh_wildcards(
            DEBUG_LEVEL.full,
            [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "wildcards")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "wildcards2")),
            ],
            """
            yaml_input:
                wildcardI:
                    - choice1
                    - choice2
                    - choice3
            """,
        )
        self.extranetwork_maps_obj.refresh_extranetwork_mappings(
            DEBUG_LEVEL.full,
            [os.path.abspath(os.path.join(os.path.dirname(__file__), "enmappings"))],
            """
            """,
        )
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()

    def interrupt(self):
        self.interrupted = True

    def init_obj(
        self, ppp: Optional[str | PromptPostProcessor] = None, combinatorial: bool = False
    ) -> PromptPostProcessor:
        if isinstance(ppp, str):
            if ppp == "nocup":
                the_obj = PromptPostProcessor(
                    self.ppp_logger,
                    self.def_env_info,
                    replace(
                        self.defopts,
                        cup_do_cleanup=False,
                        cup_cleanup_variables=False,
                        cup_empty_constructs=False,
                        cup_extra_separators=False,
                        cup_extra_separators2=False,
                        cup_extra_separators_include_eol=False,
                        cup_extra_spaces=False,
                        cup_breaks=False,
                        cup_breaks_eol=False,
                        cup_ands=False,
                        cup_ands_eol=False,
                        cup_extranetwork_tags=False,
                        cup_merge_attention=False,
                        do_combinatorial=combinatorial,
                    ),
                    self.grammar_content,
                    self.interrupt,
                    self.wildcards_obj,
                    self.extranetwork_maps_obj,
                )
            elif ppp == "nostrict":
                the_obj = PromptPostProcessor(
                    self.ppp_logger,
                    self.def_env_info,
                    replace(
                        self.defopts,
                        strict_operators=False,
                        do_combinatorial=combinatorial,
                    ),
                    self.grammar_content,
                    self.interrupt,
                    self.wildcards_obj,
                    self.extranetwork_maps_obj,
                )
        else:
            the_obj = ppp
        if not the_obj:
            the_obj = PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    do_combinatorial=combinatorial,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            )
        return the_obj

    def process(
        self,
        input_prompts: PromptPair,
        expected_output: Optional[OutputTuple | list[OutputTuple]] = None,
        seed: int = 1,
        ppp: Optional[str | PromptPostProcessor] = None,
        interrupted: bool = False,
        combinatorial: bool = False,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (PromptPair): The input prompts.
            expected_output (OutputTuple | list[OutputTuple], optional): The expected output. When a list is provided, the test will run once for each expected output, using the same input prompt, but seed will be incremented for each iteration.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (Optional[str | PromptPostProcessor], optional): The PromptPostProcessor instance or type. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.
            combinatorial (bool, optional): The combinatorial flag. Defaults to False.

        Returns:
            None
        """
        the_obj: PromptPostProcessor = self.init_obj(ppp, combinatorial)
        out = (
            [OutputTuple("", "", None)]
            if expected_output is None
            else expected_output if isinstance(expected_output, list) else [expected_output]
        )
        if the_obj.state.options.do_combinatorial:
            # combinatorial
            errors = []
            result = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            if self.interrupted != interrupted:
                errors.append(f"Interrupted flag is incorrect: expected {interrupted}, got {self.interrupted}")
            elif expected_output is not None:
                if len(result) != len(out):
                    errors.append(f"Incorrect number of combinations (expected {len(out)}, got {len(result)})")
                for out_prompt, out_negative_prompt, out_variables in out:
                    found = None
                    for r_prompt, r_negative_prompt, r_variables in result:
                        if r_prompt == out_prompt and r_negative_prompt == out_negative_prompt:
                            found = OutputTuple(r_prompt, r_negative_prompt, r_variables)
                            break
                    if not found:
                        errors.append(f"Combination '{out_prompt}' / '{out_negative_prompt}' not found in output")
                    elif out_variables:
                        unmatched_vars = {}
                        expected_values = {}
                        for var_name, var_value in out_variables.items():
                            if var_name not in found.variables or found.variables[var_name] != var_value:
                                unmatched_vars[var_name] = (
                                    found.variables[var_name] if var_name in found.variables else None
                                )
                                expected_values[var_name] = var_value
                        if unmatched_vars:
                            errors.append(
                                f"Combination '{out_prompt}' / '{out_negative_prompt}' found, but variables do not match: expected {expected_values}, got {unmatched_vars}"
                            )
            self.assertFalse(
                bool(errors),
                "\n" + "\n".join(errors),
            )
            return
        # non-combinatorial
        errors = []
        for eo in out:
            result = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            if self.interrupted != interrupted:
                errors.append(f"Interrupted flag is incorrect: expected {interrupted}, got {self.interrupted}")
            elif expected_output is not None:
                result_prompt, result_negative_prompt, output_variables = result[0]
                if result_prompt != eo.prompt or result_negative_prompt != eo.negative_prompt:
                    errors.append(
                        f"Incorrect result '{eo.prompt}' / '{eo.negative_prompt}', got '{result_prompt}' / '{result_negative_prompt}'"
                    )
                if eo.variables:
                    unmatched_vars = {}
                    expected_values = {}
                    for var_name, var_value in eo.variables.items():
                        if var_name not in output_variables or output_variables[var_name] != var_value:
                            unmatched_vars[var_name] = (
                                output_variables[var_name] if var_name in output_variables else None
                            )
                            expected_values[var_name] = var_value
                    if unmatched_vars:
                        errors.append(
                            f"Result '{eo.prompt}' / '{eo.negative_prompt}' found, but variables do not match: expected {expected_values}, got {unmatched_vars}"
                        )
            seed += 1
        self.assertFalse(
            bool(errors),
            "\n" + "\n".join(errors),
        )
