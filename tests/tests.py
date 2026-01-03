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
            "is_sd1": False,
            "is_sd2": False,
            "is_sdxl": True,
            "is_ssd": False,
            "is_sd3": False,
            "is_flux": False,
            "is_auraflow": False,
            "model_class": "DiffusionEngine",
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
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (PromptPair): The input prompts.
            expected_output_prompts (PromptPair | list[PromptPair], optional): The expected prompts.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (Optional[str | PromptPostProcessor], optional): The PromptPostProcessor instance or type. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.

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
            elif ppp == "comfyui":
                the_obj = PromptPostProcessor(
                    self.ppp_logger,
                    self.interrupt,
                    {
                        **self.def_env_info,
                        "app": "comfyui",
                        "model_class": "SDXL",
                    },
                    self.defopts,
                    self.grammar_content,
                    self.wildcards_obj,
                    self.extranetwork_maps_obj,
                )
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
            result_prompt, result_negative_prompt, _ = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            self.assertEqual(self.interrupted, interrupted, "Interrupted flag is incorrect")
            if not self.interrupted and expected_output_prompts is not None:
                self.assertEqual(result_prompt, eo.prompt, "Incorrect prompt")
                self.assertEqual(result_negative_prompt, eo.negative_prompt, "Incorrect negative prompt")
            seed += 1


class TestPromptPostProcessor(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Send To Negative tests

    def test_stn_simple(self):  # negtags with different parameters and separations
        self.process(
            PromptPair(
                "flowers<ppp:stn>red<ppp:/stn>, <ppp:stn s>green<ppp:/stn>, <ppp:stn e>blue<ppp:/stn><ppp:stn p0>yellow<ppp:/stn>, <ppp:stn p1>purple<ppp:/stn><ppp:stn p2>black<ppp:/stn>",
                "<ppp:stn i0/>normal quality<ppp:stn i1>, worse quality<ppp:stn i2/>",
            ),
            PromptPair("flowers", "red, green, yellow, normal quality, purple, worse quality, black, blue"),
        )

    def test_stn_complex(self):  # complex negtags
        self.process(
            PromptPair(
                "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
                "normal quality, <ppp:stn i0/>, bad quality<ppp:stn i1/>, worse quality",
            ),
            PromptPair(
                "flowers",
                "red, (pink:1.21), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
            ),
        )

    def test_stn_complex_nocleanup(self):  # complex negtags with no cleanup
        self.process(
            PromptPair(
                "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
                "normal quality, <ppp:stn i0/>, bad quality<ppp:stn i1/>, worse quality",
            ),
            PromptPair(
                " (()), flowers , ,  ",
                "red, ((pink)), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
            ),
            ppp="nocup",
        )

    def test_stn_inside_attention(self):  # negtag inside attention
        self.process(
            PromptPair(
                "[<ppp:stn>neg1<ppp:/stn>] this is a ((test<ppp:stn e>neg2<ppp:/stn>) (test:2.0): 1.5 ) (red<ppp:stn>[square]<ppp:/stn>:1.5)",
                "normal quality",
            ),
            PromptPair(
                "this is a ((test) (test:2):1.5) (red:1.5)", "[neg1], ([square]:1.5), normal quality, (neg2:1.65)"
            ),
        )

    def test_stn_inside_alternation(self):  # negtag inside alternation
        self.process(
            PromptPair(
                "this is a (([complex<ppp:stn>neg1<ppp:/stn>|simple<ppp:stn>neg2<ppp:/stn>|regular<ppp:stn>neg3<ppp:/stn>] test)(test:2.0):1.5)",
                "normal quality",
            ),
            PromptPair(
                "this is a (([complex|simple|regular] test)(test:2):1.5)",
                "([neg1||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
            ),
        )

    def test_stn_inside_alternation_recursive(self):  # negtag inside alternation (recursive alternation)
        self.process(
            PromptPair(
                "this is a (([complex<ppp:stn>neg1<ppp:/stn>[one|two<ppp:stn>neg12<ppp:/stn>||three|four(<ppp:stn>neg14<ppp:/stn>)]|simple<ppp:stn>neg2<ppp:/stn>|regular<ppp:stn>neg3<ppp:/stn>] test)(test:2.0):1.5)",
                "normal quality",
            ),
            PromptPair(
                "this is a (([complex[one|two||three|four]|simple|regular] test)(test:2):1.5)",
                "([neg1||]:1.65), ([[|neg12|||]||]:1.65), ([[||||(neg14)]||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
            ),
        )

    def test_stn_inside_scheduling(self):  # negtag inside scheduling
        self.process(
            PromptPair("this is [abc<ppp:stn>neg1<ppp:/stn>:def<ppp:stn e>neg2<ppp:/stn>: 5 ]", "normal quality"),
            [PromptPair("this is [abc:def:5]", "[neg1::5], normal quality, [neg2:5]")],
        )

    def test_stn_complex_features(self):  # complex negtags with AND, BREAK and other features
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loratrigger <lora:xxx:1> AND AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality, <ppp:stn i0/>",
            ),
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]:0.5 AND loratrigger <lora:xxx:1> AND hypernettrigger <hypernet:yyy>:0.3",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
        )

    def test_stn_complex_features_newformat(self):  # complex negtags with AND, BREAK and other features (new format)
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loratrigger <lora:xxx:1> AND AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality, <ppp:stn i0/>",
            ),
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]:0.5 AND loratrigger <lora:xxx:1> AND hypernettrigger <hypernet:yyy>:0.3",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
        )

    def test_stn_inside_alternation_recursive_2(self):  # negtag inside alternation (recursive alternation)
        self.process(
            PromptPair(
                "[pos1<ppp:stn>neg1<ppp:/stn>[pos11|pos12<ppp:stn>neg12<ppp:/stn>||pos14|pos15<ppp:stn>neg15<ppp:/stn>]|pos2<ppp:stn>neg2<ppp:/stn>|pos3<ppp:stn>neg3<ppp:/stn>]",
                "",
            ),
            PromptPair(
                "[pos1[pos11|pos12||pos14|pos15]|pos2|pos3]",
                "[neg1||], [[|neg12|||]||], [[||||neg15]||], [|neg2|], [||neg3]",
                # "[neg1[|neg12|||neg15]|neg2|neg3]", # expected output if the constructs were unified
            ),
        )

    # Cleanup tests

    def test_cl_simple(self):  # simple cleanup
        self.process(
            PromptPair("  this is a ((test ), , ,  (), ,   [] ( , test ,:2.0):1.5), (red:1.5)  ", "  normal quality  "),
            PromptPair("this is a ((test), (test,:2):1.5), (red:1.5)", "normal quality"),
        )

    def test_cl_complex(self):  # complex cleanup
        self.process(
            PromptPair(
                "  this is BREAKABLE a ((test)), ,AND AND(() [] <lora:test> ANDERSON (test:2.0):1.5) :o BREAK \n BREAK (red:1.5)  ",
                "  [:hands, feet, :0.15]normal quality  ",
            ),
            PromptPair(
                "this is BREAKABLE a (test:1.21) AND(<lora:test> ANDERSON (test:2):1.5) :o BREAK (red:1.5)",
                "[:hands, feet, :0.15]normal quality",
            ),
        )

    def test_cl_removenetworktags(self):  # remove network tags
        self.process(
            PromptPair("this is a <lora:test:1> test__yaml/wildcard7__", ""),
            PromptPair("this is a test", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {**self.defopts, "remove_extranetwork_tags": True},
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cl_dontremoveseparatorsoneol(self):  # don't remove separators on eol
        self.process(
            PromptPair("this is a test,\nsecond line", ""),
            PromptPair("this is a test,\nsecond line", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "cleanup_extra_separators2": False,
                    "cleanup_extra_separators_include_eol": False,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cl_separatorswitheol(self):  # don't remove eols with the separators
        self.process(
            PromptPair(
                """{      (d:0.9) ,, (l:1.1)  | (l:1.1)         (d:0.9),,, }
                        (l:1.1)  
                        (d:0.9)""",
                "",
            ),
            PromptPair(
                """ (l:1.1)         (d:0.9), 
                        (l:1.1)  
                        (d:0.9)""",
                "",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "cleanup_empty_constructs": False,
                    "cleanup_extra_separators": True,
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
            ),
        )

    def test_cl_mergeattention(self):  # merge attention
        self.process(
            PromptPair(
                "this is (a test:0.9) of (attention (merging:1.2)) where ((this)) ((is joined:1.2)) and ([this too]:1.3)",
                "",
            ),
            PromptPair(
                "this is [a test] of (attention (merging:1.2)) where (this:1.21) (is joined:1.32) and (this too:1.17)",
                "",
            ),
        )

    def test_cl_not_mergeattention(self):  # not merge attention
        self.process(
            PromptPair(
                "this is (a test:0.9) of not (attention (merging:1.2)) where ((this)) ((is not joined:1.2)) and neither is ([this]:1.3)",
                "",
            ),
            PromptPair(
                "this is (a test:0.9) of not (attention (merging:1.2)) where ((this)) ((is not joined:1.2)) and neither is ([this]:1.3)",
                "",
            ),
            ppp="nocup",
        )

    # Command tests

    def test_cmd_stn_complex_features(self):  # complex stn command with AND, BREAK and other features
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loratrigger <lora:xxx:1> AND AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality, <ppp:stn i0/>",
            ),
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]:0.5 AND loratrigger <lora:xxx:1> AND hypernettrigger <hypernet:yyy>:0.3",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
        )

    def test_cmd_if_complex_features(self):  # complex if command
        self.process(
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK, BREAK <ppp:if _is_sd1>with [abc<ppp:stn>neg4<ppp:/stn>:def:5]<ppp:/if>:0.5 AND <ppp:if _is_sd1>loratrigger <lora:xxx:1><ppp:elif _is_sdxl>hypernettrigger <hypernet:yyy><ppp:else>nothing<ppp:/if>:0.3",
                "normal quality",
            ),
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2):1.5)\nBREAK :0.5 AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality",
            ),
        )

    def test_cmd_if_nested(self):  # nested if command
        self.process(
            PromptPair(
                "this is <ppp:if _sd eq 'sd1'>SD1<ppp:else><ppp:if _is_pony>PONY<ppp:else>SD2<ppp:/if><ppp:/if><ppp:if _is_sdxl_no_pony>NOPONY<ppp:/if><ppp:if _is_pure_sdxl>NOPONY<ppp:/if>",
                "",
            ),
            PromptPair("this is PONY", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_set_if(self):  # set and if commands
        self.process(
            PromptPair("<ppp:set v>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_empty(self):  # set to empty
        self.process(
            PromptPair("<ppp:set v><ppp:/set>${v2=}this test is <ppp:if v or v2>not OK<ppp:else>OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_eval_if(self):  # set and if commands
        self.process(
            PromptPair("<ppp:set v evaluate>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_echo_nested(self):  # nested set, if and echo commands
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:if v1 gt 0><ppp:set v2>OK<ppp:/set><ppp:/if><ppp:if v2 eq 'OK'><ppp:echo v2/><ppp:else>not OK<ppp:/if> <ppp:echo v2>NOK<ppp:/echo> <ppp:echo v3>OK<ppp:/echo>",
                "",
            ),
            PromptPair("OK OK OK", ""),
        )

    def test_cmd_set_if_complex_conditions_1(self):  # complex conditions (or)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if v1 or v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_2(self):  # complex conditions (and)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>true<ppp:/set>this test is <ppp:if v1 and v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_3(self):  # complex conditions (not)
        self.process(
            PromptPair("<ppp:set v1>false<ppp:/set>this test is <ppp:if not v1>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_4(self):  # complex conditions (not, precedence)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not (v1 and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_5(self):  # complex conditions (not, precedence, comparison)
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not(v1 eq '1' and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_6(self):  # complex conditions
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq '1' and v2 eq '2' and v3 eq '3'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_7(self):  # complex conditions
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq '1' and v2 not eq '2' or v3 eq '3'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if2(self):  # set and more complex if commands
        self.process(
            PromptPair(
                "First: <ppp:set v>value1<ppp:/set>this test is <ppp:if v in ('value1','value2')>OK<ppp:elif v in ('value3')>OK2<ppp:else>not OK<ppp:/if>\nSecond: <ppp:set v2>value3<ppp:/set>this test is <ppp:if not v2 in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("First: this test is OK\nSecond: this test is OK", ""),
        )

    def test_cmd_set_add_if(self):  # set, add and if commands
        self.process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v add>2<ppp:/set>this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_add_DP_if(self):  # set, add (DP format) and if commands
        self.process(
            PromptPair(
                "${v=value}${v+=2}this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_immediateeval(self):  # set (DP format) with mixed evaluation
        self.process(
            PromptPair(
                "${var=!__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var2:default}, ${var3=__yaml/wildcard1__}${var3}, ${var3}",
                "",
            ),
            PromptPair("the choices are: choice2, choice2, default, choice3, choice1", ""),
            ppp="nocup",
        )

    def test_cmd_set_mixeval(self):  # set and add (DP format) with mixed evaluation
        self.process(
            PromptPair(
                "${var=__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var+=, __yaml/wildcard2__}${var}, ${var}, ${var+=!, __yaml/wildcard3__}${var}, ${var}",
                "",
            ),
            PromptPair(
                "the choices are: choice2, choice3, choice1, choice1- choice2 -choice3, choice2,  choice2 -choice1-choice3, choice2, choice3-choice1- choice2 , choice1, choice2 , choice2, choice3-choice1- choice2 , choice1, choice2 ",
                "",
            ),
            ppp="nocup",
        )

    def test_cmd_set_ifundefined_if(self):  # set, ifundefined and if commands
        self.process(
            PromptPair(
                "<ppp:set v ifundefined>value<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_if_2(self):  # set, ifundefined and if commands
        self.process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v ifundefined>value2<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if(self):  # set, ifundefined (DP format) and if commands
        self.process(
            PromptPair(
                "${v?=value}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if_2(self):  # set, ifundefined (DP format) and if commands
        self.process(
            PromptPair(
                "${v=!value}${v?=!value2}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_ext(self):  # ext
        self.process(
            PromptPair(
                "<ppp:ext lora lora1name if not _is_pony>trigger1<ppp:/ext><ppp:ext lora 'lora2 name' -0.8 if not _is_pony>trigger2<ppp:/ext><ppp:ext lora lora3__name '0.5:0.8' if not _is_pony><ppp:ext lora lora4name>trigger4<ppp:/ext>",
                "",
            ),
            PromptPair(
                "<lora:lora1name:1>trigger1,<lora:lora2 name:-0.8>trigger2,<lora:lora3__name:0.5:0.8><lora:lora4name:1>trigger4",
                "",
            ),
        )

    def test_cmd_ext_map_notrigger(self):  # ext mapping, no trigger
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1/><ppp:ext $lora lora1>",
                "",
            ),
            PromptPair("triggergeneric1, triggergeneric2, two, triggergeneric1, triggergeneric2, two", ""),
        )

    def test_cmd_ext_map1(self):  # ext mapping, no lora
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("inlinetrigger, triggergeneric1, triggergeneric2, two", ""),
        )

    def test_cmd_ext_map2(self):  # ext mapping, lora with weight
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.8>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map3(self):  # ext mapping, lora with weight adjusted
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1 0.5>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.4>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map4(self):  # ext mapping, lora with parameters
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1 '0.6:0.8'>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.6:0.8>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map5(self):  # ext mapping, lora with no parameters
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:loraillustrious:0.9:0.8>inlinetrigger, triggerillustrious1, triggerillustrious2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ilxlmodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    # Choices tests

    def test_ch_choices(self):  # simple choices with weights
        self.process(
            PromptPair("the choices are: {3::choice1|2::choice2|choice3}", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_ch_unsupportedsampler(self):  # unsupported sampler
        self.process(
            PromptPair("the choices are: {@choice1|choice2|choice3}", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_ch_choices_withcomments(self):  # choices with comments and multiline
        self.process(
            PromptPair(
                "the choices are: {\n3::choice1 # this is option 1\n|2::choice2\n# this was option 2\n|choice3 # this is option 3\n}",
                "",
            ),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_ch_choices_multiple(self):  # choices with multiple selection
        self.process(
            PromptPair("the choices are: {~2$$, $$3::choice1|2:: choice2 |choice3}", ""),
            PromptPair("the choices are:  choice2 , choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_if_multiple(self):  # choices with if and multiple selection
        self.process(
            PromptPair("the choices are: {2$$, $$3::choice1|2 if _is_sd1::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_set_if_multiple(self):  # choices with if user variable and multiple selection
        self.process(
            PromptPair("${var=test}the choices are: {2$$, $$3::choice1|2 if not var eq 'test'::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_set_if_nested(self):  # nested choices with if user variable and multiple selection
        self.process(
            PromptPair(
                "${var=test}the choices are: {2$$, $$3::choice1${var2=test2} {if var2 eq 'test2'::choice11|choice12}|2 if not var eq 'test'::choice2|choice3}",
                "",
            ),
            PromptPair("the choices are: choice1 choice11, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choicesinsidelora(self):  # simple choices inside a lora
        self.process(
            PromptPair("<lora:test1:1><lora:test__other__name:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            PromptPair("<lora:test1:1><lora:test__other__name:1><lora:test2:0.7>", ""),
            ppp="nocup",
        )

    def test_ch_removelorawithchoices(self):
        self.process(
            PromptPair("<lora:test1:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {**self.defopts, "remove_extranetwork_tags": True},
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_ch_cmd_includewildcard(self):
        self.process(
            PromptPair("{ch_one|ch_two|%0.5::include yaml/wildcard1}", ""),
            PromptPair("ch_two", ""),
            ppp="nocup",
        )

    # Wildcards tests

    def test_wc_ignore(self):  # wildcards with ignore option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
                "normal quality, <ppp:stn i0/> {option1|option2}",
            ),
            PromptPair(
                "this is: a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]<lora:xxx:1>",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.remove.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_warn(self):  # wildcards with warn option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_stop(self):  # wildcards with stop option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(
                PromptPostProcessor.WILDCARD_STOP.format("__bad_wildcard__") + "__bad_wildcard__",
                "{option1|option2}",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_wcinvar_warn(self):  # wildcards in var with warn option
        self.process(
            PromptPair("${v=__bad_wildcard__}${v}", ""),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_invalid_name(self):
        self.process(
            PromptPair("the choices are: ___invalid__", ""),
            PromptPair("the choices are: ___invalid__", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_text(self):  # simple text wildcard
        self.process(
            PromptPair("the choices are: __text/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_json(self):  # simple json wildcard
        self.process(
            PromptPair("the choices are: __json/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choices are: __yaml/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_text(self):  # simple text wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$text/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_json(self):  # simple json wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$json/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_yaml(self):  # simple yaml wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$yaml/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_text(self):  # simple text wildcard with default options
        self.process(
            PromptPair("the choices are: __text/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_json(self):  # simple json wildcard with default options
        self.process(
            PromptPair("the choices are: __json/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_yaml(self):  # simple yaml wildcard with default options
        self.process(
            PromptPair("the choices are: __yaml/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_test2_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test2__", ""),
            PromptPair("the choice is: 2", ""),
            ppp="nocup",
        )

    def test_wc_test3_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test3__", ""),
            PromptPair("the choice is: one choice", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_index(self):  # wildcard with positional index filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label(self):  # wildcard with label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label2(self):  # wildcard with label filter in multiple choices
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label2'__", ""),
            PromptPair("the choice is: choice1-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label3(self):  # wildcard with multiple label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_indexlabel(self):  # wildcard with mixed index and label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound(self):  # wildcard with compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1+label3'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound2(self):  # wildcard with inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound3(self):  # wildcard with doubly inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bisbis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bisbis", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_text(self):  # nested text wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$text/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_json(self):  # nested json wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$json/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_yaml(self):  # nested yaml wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$yaml/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_optional(self):  # empty wildcard with no error
        self.process(
            PromptPair("the choices are: __yaml/empty_wildcard__", ""),
            PromptPair("the choices are: ", ""),
            ppp="nocup",
        )

    def test_wc_wildcard4_yaml(self):  # simple yaml wildcard with one option
        self.process(
            PromptPair("the choices are: __yaml/wildcard4__", ""),
            PromptPair("the choices are: inline text", ""),
            ppp="nocup",
        )

    def test_wc_wildcard6_yaml(self):  # simple yaml wildcard with object formatted choices
        self.process(
            PromptPair("the choices are: __yaml/wildcard6__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_choice_wildcard_mix(self):  # choices with wildcard mix
        self.process(
            PromptPair("the choices are: {__~2$$yaml/wildcard2__|choice0}", ""),
            [
                PromptPair("the choices are: choice0", ""),
                PromptPair("the choices are: choice1, choice3", ""),
                PromptPair("the choices are: choice1, choice3", ""),
            ],
            ppp="nocup",
        )

    def test_wc_unsupportedsampler(self):  # unsupported sampler
        self.process(
            PromptPair("the choices are: __@yaml/wildcard2__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_wildcard_globbing(self):  # wildcard with globbing
        self.process(
            PromptPair("the choices are: __yaml/wildcard[12]__, __yaml/wildcard?__", ""),
            PromptPair("the choices are: choice3-choice2, <lora:test2:1>- choice2 -choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcardwithvar(self):  # wildcard with inline variable
        self.process(
            PromptPair("the choices are: __yaml/wildcard5(var=test)__, __yaml/wildcard5__", ""),
            PromptPair("the choices are: inline test, inline default", ""),
            ppp="nocup",
        )

    def test_wc_wildcardPS_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.process(
            PromptPair("the choices are: __yaml/wildcardPS__", ""),
            PromptPair("the choices are: prefix-choice2/choice3-suffix", ""),
            ppp="nocup",
        )

    def test_wc_anonymouswildcard_yaml(self):  # yaml anonymous wildcard
        self.process(
            PromptPair("the choices are: __yaml/anonwildcards__", ""),
            PromptPair("the choices are: six", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_input(self):  # simple yaml wildcard input
        self.process(
            PromptPair("the choices are: __yaml_input/wildcardI__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_circular(self):  # wildcard circular reference
        self.process(
            PromptPair("the choices are: __yaml/circular1__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_including(self):  # wildcard including another wildcard
        self.process(
            PromptPair("the choices are: __yaml/including__", ""),
            PromptPair("the choices are: choice4", ""),
            ppp="nocup",
        )

    def test_wc_circular_including(self):  # wildcard including another wildcard in a circular reference
        self.process(
            PromptPair("the choices are: __yaml/including1__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_dynamicwildcard(self):  # wildcard built from variables
        self.process(
            PromptPair(
                "the choices are: ${x={1|2|3}}${w=yaml/wildcard${x}}__yaml/wildcard${x}__ __${w}__ __<ppp:echo w/>__",
                "",
            ),
            PromptPair("the choices are: choice1-choice3-choice1 choice3- choice2 - choice2  choice3", ""),
            ppp="nocup",
        )

    # Hosts tests

    def test_host_attention_parentheses(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("(test1:0.9) (test2) (test3:1.5)", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "parentheses"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_disable(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("test1 test2 test3", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "disable"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_remove(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_error(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_scheduling_before(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("test1", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "before"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_after(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "after"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_first(self):
        self.process(
            PromptPair(
                "[test1::0.5] [:test2:0.5] [test3:test4:0.5]",
                "",
            ),
            PromptPair("test1 test3", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "first"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_remove(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_error(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_alternation_first(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("test1", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "first"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_alternation_remove(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_alternation_error(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_and_eol(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("test1\ntest2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "eol"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_and_remove(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("test1 test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_and_error(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_break_eol(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("test1\ntest2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "eol"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_break_remove(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("test1 test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_break_error(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    # Model variants tests

    def test_variants(self):
        self.process(
            PromptPair(
                "<ppp:if _is_test1>test1<ppp:/if><ppp:if _is_test2>test2<ppp:/if><ppp:if _is_test3>test3<ppp:/if><ppp:if _is_test4>test4<ppp:/if>",
                "",
            ),
            PromptPair("test1test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/testmodel.safetensors",
                    "ppp_config": {
                        "models": {
                            "sd1": {
                                "variants": {
                                    "test3": {"find_in_filename": "testmodel"},
                                    "sdxl": {"find_in_filename": "testmodel"},
                                }
                            },
                            "sdxl": {
                                "variants": {
                                    "test1": {"find_in_filename": "testmodel"},
                                    "test2": {"find_in_filename": "testmodel"},
                                }
                            },
                            "invalid": {
                                "variants": {
                                    "test4": {"find_in_filename": "testmodel"},
                                }
                            },
                        }
                    },
                },
                {
                    **self.defopts,
                    "on_warning": PromptPostProcessor.ONWARNING_CHOICES.warn.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    # ComfyUI tests

    def test_comfyui_attention(self):  # attention conversion
        self.process(
            PromptPair("(test1) (test2:1.5) [test3] [(test4)]", ""),
            PromptPair("(test1) (test2:1.5) (test3:0.9) (test4:0.99)", ""),
            ppp="comfyui",
        )

    # Performance tests

    def test_parser_performance_simple_simpleparser(
        self,
    ):  # performance test with a large prompt without new constructs
        large_prompt = ", ".join(
            ["(this:1.2) is a [test] using a [simple|low complexity] prompt with <lora:test:1>"] * 15
        )
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    def test_parser_performance_simple_fullparser(
        self,
    ):  # performance test with a large prompt without new constructs but using full parser
        # we trick it to use the full parser by including some characters
        large_prompt = "{__${x:}}" + ", ".join(
            ["(this:1.2) is a [test] using a [simple|low complexity] prompt with <lora:test:1>"] * 15
        )
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    def test_parser_performance_complex_fullparser(
        self,
    ):  # performance test with a large prompt with new constructs (full parser)
        large_prompt = ", ".join(["__yaml/wildcard1__, (__yaml/wildcard2__), __yaml/wildcard3__, {one|two|three}"] * 15)
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    # the following tests are performance tests with only one kind of the old constructs
    # same number of constructs and approximately the same full length

    def test_parser_performance_simple_attention(self):  # performance test with only attention
        large_prompt = ", ".join(["(one:1.2) two (three) four [five] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    def test_parser_performance_simple_schedules(self):  # performance test with only schedules
        large_prompt = ", ".join(["[one:1:0.5] two [three:0.8] four [five:5:0.2] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    def test_parser_performance_simple_alternation(self):  # performance test with only alternation
        large_prompt = ", ".join(["[one|1] two [three|3] four [five|5] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    def test_parser_performance_simple_extranetwork(self):  # performance test with only extra networks
        large_prompt = ", ".join(["<lora:one:1> two <lora:three:1> four <lora:five:1> six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp="nocup",
        )

    # Variable-vs-variable comparison tests

    def test_cmd_if_var_vs_var_eq(self):  # var eq var: both set to same value, if-branch taken
        self.process(
            PromptPair(
                "<ppp:set v1>hello<ppp:/set><ppp:set v2>hello<ppp:/set><ppp:if v1 eq v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_ne(self):  # var ne var: different values, ne condition true
        self.process(
            PromptPair(
                "<ppp:set v1>apple<ppp:/set><ppp:set v2>orange<ppp:/set><ppp:if v1 ne v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_contains(self):  # var contains var: var1 contains var2's value
        self.process(
            PromptPair(
                "<ppp:set v1>hello world<ppp:/set><ppp:set v2>hello<ppp:/set><ppp:if v1 contains v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_not_contains(self):  # var not contains var: var1 does not contain var2's value
        self.process(
            PromptPair(
                "<ppp:set v1>hello world<ppp:/set><ppp:set v2>goodbye<ppp:/set><ppp:if v1 not contains v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )
    
    # NaN/undefined variable integer comparison tests

    def test_cmd_if_undefined_var_int_compare_warn(self):  # undefined var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:if undefined_var gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {**self.defopts, "on_warning": PromptPostProcessor.ONWARNING_CHOICES.warn.value},
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_if_undefined_var_int_compare_stop(self):  # undefined var integer compare with on_warning=stop
        self.process(
            PromptPair(
                "<ppp:if undefined_var gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_nonnumeric_var_int_compare_warn(self):  # non-numeric var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {**self.defopts, "on_warning": PromptPostProcessor.ONWARNING_CHOICES.warn.value},
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_if_nonnumeric_var_int_compare_stop(self):  # non-numeric var integer compare with on_warning=stop
        self.process(
            PromptPair(
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_empty_var_int_compare(self):  # empty string var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar><ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {**self.defopts, "on_warning": PromptPostProcessor.ONWARNING_CHOICES.warn.value},
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )


if __name__ == "__main__":
    unittest.main()
