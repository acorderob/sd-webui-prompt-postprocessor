import os
import logging
from typing import NamedTuple, Optional
import unittest
import datetime

from ppp_enmappings import PPPExtraNetworkMappings  # pylint: disable=import-error
from ppp_wildcards import PPPWildcards  # pylint: disable=import-error
from ppp import PromptPostProcessor  # pylint: disable=import-error
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory  # pylint: disable=import-error


class PromptPair(NamedTuple):
    prompt: str = ""
    negative_prompt: str = ""


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

        self.lf = PromptPostProcessorLogFactory(None, log_filename)
        self.ppp_logger = self.lf.log
        self.ppp_logger.setLevel(logging.DEBUG)
        self.grammar_content = None
        self.interrupted = False
        self.defopts = {
            "debug_level": DEBUG_LEVEL.full.value,
            "on_warning": PromptPostProcessor.ONWARNING_CHOICES.stop.value,
            "process_wildcards": True,
            "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
            "choice_separator": ", ",
            "keep_choices_order": False,
            "stn_separator": ", ",
            "stn_ignore_repeats": True,
            "do_cleanup": True,
            "cleanup_variables": True,
            "cleanup_empty_constructs": True,
            "cleanup_extra_separators": True,
            "cleanup_extra_separators2": True,
            "cleanup_extra_separators_include_eol": False,
            "cleanup_extra_spaces": True,
            "cleanup_breaks": True,
            "cleanup_breaks_eol": False,
            "cleanup_ands": True,
            "cleanup_ands_eol": False,
            "cleanup_extranetwork_tags": True,
            "cleanup_merge_attention": True,
            "remove_extranetwork_tags": False,
        }
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

    def process(
        self,
        input_prompts: PromptPair,
        expected_output_prompts: Optional[PromptPair | list[PromptPair]] = None,
        seed: int = 1,
        ppp: Optional[str | PromptPostProcessor] = None,
        interrupted: bool = False,
        variables: dict[str, str] | None = None,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (PromptPair): The input prompts.
            expected_output_prompts (PromptPair | list[PromptPair], optional): The expected prompts.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (Optional[str | PromptPostProcessor], optional): The PromptPostProcessor instance or type. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.
            variables (dict[str,str]|None, optional): Output variables to check. Defaults to None.

        Returns:
            None
        """
        if isinstance(ppp, str):
            if ppp == "nocup":
                the_obj = PromptPostProcessor(
                    self.ppp_logger,
                    self.interrupt,
                    self.def_env_info,
                    {
                        **self.defopts,
                        "do_cleanup": False,
                        "cleanup_variables": False,
                        "cleanup_empty_constructs": False,
                        "cleanup_extra_separators": False,
                        "cleanup_extra_separators2": False,
                        "cleanup_extra_separators_include_eol": False,
                        "cleanup_extra_spaces": False,
                        "cleanup_breaks": False,
                        "cleanup_breaks_eol": False,
                        "cleanup_ands": False,
                        "cleanup_ands_eol": False,
                        "cleanup_extranetwork_tags": False,
                        "cleanup_merge_attention": False,
                    },
                    self.grammar_content,
                    self.wildcards_obj,
                    self.extranetwork_maps_obj,
                )
            # elif ppp == "comfyui":
            #     the_obj = PromptPostProcessor(
            #         self.ppp_logger,
            #         self.interrupt,
            #         {
            #             **self.def_env_info,
            #             "app": "comfyui",
            #             "model_class": "SDXL",
            #         },
            #         self.defopts,
            #         self.grammar_content,
            #         self.wildcards_obj,
            #         self.extranetwork_maps_obj,
            #     )
        else:
            the_obj = ppp
        if not the_obj:
            the_obj = PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            )
        out = (
            [PromptPair("", "")]
            if expected_output_prompts is None
            else expected_output_prompts if isinstance(expected_output_prompts, list) else [expected_output_prompts]
        )
        for eo in out:
            result_prompt, result_negative_prompt, output_variables = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            self.assertEqual(self.interrupted, interrupted, "Interrupted flag is incorrect")
            if not self.interrupted:
                if expected_output_prompts is not None:
                    self.assertEqual(result_prompt, eo.prompt, "Incorrect prompt")
                    self.assertEqual(result_negative_prompt, eo.negative_prompt, "Incorrect negative prompt")
                if variables is not None:
                    for var_name, var_value in variables.items():
                        self.assertIn(
                            var_name, output_variables, f"Variable '{var_name}' not found in output variables"
                        )
                        self.assertEqual(
                            output_variables[var_name],
                            var_value,
                            f"Variable '{var_name}' has incorrect value",
                        )
            seed += 1
