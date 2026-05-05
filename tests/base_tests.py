from dataclasses import replace
import difflib
import os
import logging
from typing import Any, NamedTuple, Optional
import unittest
import datetime

from ppp_classes import IFWILDCARDS_CHOICES, ONWARNING_CHOICES, PPPStateOptions
from ppp_enmappings import PPPExtraNetworkMappings  # type: ignore
from ppp_wildcards import PPPWildcards  # type: ignore
from ppp import PromptPostProcessor  # type: ignore
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory  # type: ignore


class InputTuple(NamedTuple):
    prompt: str = ""
    negative_prompt: str = ""


class OutputTuple(NamedTuple):
    prompt: str = ""
    negative_prompt: str = ""
    variables: dict[str, Any] = None


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
        self.defopts = PPPStateOptions(
            debug_level=DEBUG_LEVEL.full,
            on_warning=ONWARNING_CHOICES.stop,
            strict_operators=True,
            process_wildcards=True,
            if_wildcards=IFWILDCARDS_CHOICES.stop,
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
            combinatorial_shuffle=False,
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

    def init_ppp(
        self,
        ppp: Optional[str | PromptPostProcessor] = None,
        combinatorial: bool = False,
        combinatorial_limit: int = 0,
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
                        combinatorial_limit=combinatorial_limit,
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
                        combinatorial_limit=combinatorial_limit,
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
                    combinatorial_limit=combinatorial_limit,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            )
        return the_obj

    def _comp_diff(self, result: str, expected: str) -> list[str]:
        return list(
            difflib.ndiff(
                result.splitlines(True),
                expected.splitlines(True),
                linejunk=None,
                charjunk=None,
            )
        )

    def process(
        self,
        input_prompts: InputTuple,
        expected_output: Optional[OutputTuple | list[OutputTuple]] = None,
        seed: int = 1,
        ppp: Optional[str | PromptPostProcessor] = None,
        interrupted: bool = False,
        combinatorial: bool = False,
        combinatorial_limit: int = 0,
        specific_wc_folders: Optional[list[str]] = None,
        specific_em_folders: Optional[list[str]] = None,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (InputTuple): The input prompts.
            expected_output (OutputTuple | list[OutputTuple], optional): The expected output. When a list is provided, the test will run once for each expected output, using the same input prompt, but seed will be incremented for each iteration.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (Optional[str | PromptPostProcessor], optional): The PromptPostProcessor instance or type. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.
            combinatorial (bool, optional): The combinatorial flag. Defaults to False.
            combinatorial_limit (int, optional): The combinatorial limit. Defaults to 0.
            specific_wc_folders (Optional[list[str]], optional): A list of specific wildcard folders to refresh. Defaults to None.
            specific_em_folders (Optional[list[str]], optional): A list of specific extranetwork mapping folders to refresh. Defaults to None.

        Returns:
            None
        """
        if specific_wc_folders is not None:
            self.wildcards_obj.refresh_wildcards(
                DEBUG_LEVEL.full,
                specific_wc_folders,
            )
        if specific_em_folders is not None:
            self.extranetwork_maps_obj.refresh_extranetwork_mappings(
                DEBUG_LEVEL.full,
                specific_em_folders,
            )
        the_obj: PromptPostProcessor = self.init_ppp(ppp, combinatorial, combinatorial_limit)
        out = (
            [OutputTuple("", "", None)]
            if expected_output is None
            else expected_output if isinstance(expected_output, list) else [expected_output]
        )
        if the_obj.state.options.do_combinatorial:
            # combinatorial
            errors = []
            the_obj.process_prompts_group_start()
            result = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            the_obj.process_prompts_group_end()
            self.assertTrue(
                self.interrupted == interrupted,
                f"Interrupted flag is incorrect: got {self.interrupted} but expected {interrupted}",
            )
            if not self.interrupted and expected_output is not None:
                if len(result) != len(out):
                    errors.append(f"Incorrect number of combinations: got {len(result)} but expected {len(out)}")
                for out_prompt, out_negative_prompt, out_variables in out:
                    found = None
                    for r_prompt, r_negative_prompt, r_variables in result:
                        if r_prompt == out_prompt and r_negative_prompt == out_negative_prompt:
                            found = OutputTuple(r_prompt, r_negative_prompt, r_variables)
                            break
                    if not found:
                        errors.extend(
                            [
                                "Combination not found in output",
                                "Prompt:",
                                out_prompt,
                                "Negative Prompt:",
                                out_negative_prompt,
                            ]
                        )
                    elif out_variables:
                        missing_vars = {}
                        incorrect_vars = {}
                        expected_values = {}
                        sorted_var_keys = sorted(out_variables.keys())
                        for var_name in sorted_var_keys:
                            var_value = out_variables[var_name]
                            if var_name not in found.variables:
                                missing_vars[var_name] = var_value
                            elif found.variables[var_name] != var_value:
                                incorrect_vars[var_name] = found.variables[var_name]
                                expected_values[var_name] = var_value
                        if missing_vars or incorrect_vars:
                            errors.extend(
                                [
                                    "Combination found, but variables do not match",
                                    "Prompt:",
                                    out_prompt,
                                    "Negative Prompt:",
                                    out_negative_prompt,
                                ]
                            )
                            if missing_vars:
                                errors.append("Missing variables:")
                                errors.append(str(missing_vars))
                            if incorrect_vars:
                                errors.append("Incorrect variables:")
                                errors.extend(self._comp_diff(str(incorrect_vars), str(expected_values)))
            if errors:
                raise AssertionError("\n".join(errors))
            return

        # non-combinatorial
        errors = []
        the_obj.process_prompts_group_start()
        for eo in out:
            result = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            self.assertTrue(
                self.interrupted == interrupted,
                f"Interrupted flag is incorrect: got {self.interrupted} but expected {interrupted}",
            )
            if not self.interrupted and expected_output is not None:
                result_prompt, result_negative_prompt, output_variables = result[0] if result else (None, None, None)
                if result_prompt != eo.prompt or result_negative_prompt != eo.negative_prompt:
                    errors.append("Incorrect result")
                    if result_prompt != eo.prompt:
                        errors.append("Prompt:")
                        errors.extend(self._comp_diff(result_prompt, eo.prompt))
                    if result_negative_prompt != eo.negative_prompt:
                        errors.append("Negative Prompt:")
                        errors.extend(self._comp_diff(result_negative_prompt, eo.negative_prompt))
                if eo.variables:
                    missing_vars = {}
                    incorrect_vars = {}
                    expected_values = {}
                    sorted_var_keys = sorted(eo.variables.keys())
                    for var_name in sorted_var_keys:
                        var_value = eo.variables[var_name]
                        if var_name not in output_variables:
                            missing_vars[var_name] = var_value
                        elif output_variables[var_name] != var_value:
                            incorrect_vars[var_name] = output_variables[var_name]
                            expected_values[var_name] = var_value
                    if missing_vars or incorrect_vars:
                        errors.append("Result correct, but variables do not match")
                        if missing_vars:
                            errors.append("Missing variables:")
                            errors.append(str(missing_vars))
                        if incorrect_vars:
                            errors.append("Incorrect variables:")
                            errors.extend(self._comp_diff(str(incorrect_vars), str(expected_values)))
            seed += 1
        the_obj.process_prompts_group_end()
        if errors:
            raise AssertionError("\n".join(errors))
