import os
import logging
from typing import NamedTuple, Optional
import unittest

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

    def setUp(self):
        """
        Set up the test case by initializing the necessary objects and configurations.
        """
        self.lf = PromptPostProcessorLogFactory()
        self.ppp_logger = self.lf.log
        self.ppp_logger.setLevel(logging.DEBUG)
        self.grammar_content = None
        self.defppp = None
        self.nocupppp = None
        self.comfyuippp = None
        self.interrupted = False
        self.defopts = {
            "debug_level": DEBUG_LEVEL.full.value,
            "on_warning": PromptPostProcessor.ONWARNING_CHOICES.stop.value,
            "variants_definitions": PromptPostProcessor.DEFAULT_VARIANTS_DEFINITIONS,
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
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.defppp = PromptPostProcessor(
            self.ppp_logger,
            self.interrupt,
            self.def_env_info,
            self.defopts,
            self.grammar_content,
            self.wildcards_obj,
        )
        self.nocupppp = PromptPostProcessor(
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
        )
        self.comfyuippp = PromptPostProcessor(
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
        )

    def interrupt(self):
        self.interrupted = True

    def process(
        self,
        input_prompts: PromptPair,
        expected_output_prompts: Optional[PromptPair | list[PromptPair]] = None,
        seed: int = 1,
        ppp: Optional[PromptPostProcessor] = None,
        interrupted: bool = False,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (PromptPair): The input prompts.
            expected_output_prompts (PromptPair | list[PromptPair], optional): The expected prompts.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (object, optional): The post-processor object. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.

        Returns:
            None
        """
        the_obj = ppp or self.defppp
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

    # Send To Negative tests

    def test_stn_simple(self):  # negtags with different parameters and separations
        self.process(
            PromptPair(
                "flowers<ppp:stn>red<ppp:/stn>, <ppp:stn s>green<ppp:/stn>, <ppp:stn e>blue<ppp:/stn><ppp:stn p0>yellow<ppp:/stn>, <ppp:stn p1>purple<ppp:/stn><ppp:stn p2>black<ppp:/stn>",
                "<ppp:stn i0>normal quality<ppp:stn i1>, worse quality<ppp:stn i2>",
            ),
            PromptPair("flowers", "red, green, yellow, normal quality, purple, worse quality, black, blue"),
        )

    def test_stn_complex(self):  # complex negtags
        self.process(
            PromptPair(
                "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
                "normal quality, <ppp:stn i0>, bad quality<ppp:stn i1>, worse quality",
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
                "normal quality, <ppp:stn i0>, bad quality<ppp:stn i1>, worse quality",
            ),
            PromptPair(
                " (()), flowers , ,  ",
                "red, ((pink)), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
            ),
            ppp=self.nocupppp,
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
                "normal quality, <ppp:stn i0>",
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
                "normal quality, <ppp:stn i0>",
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
            PromptPair("  this is a ((test ), , ,  (), ,   [] ( , test ,:2.0):1.5) (red:1.5)  ", "  normal quality  "),
            PromptPair("this is a ((test), (test,:2):1.5) (red:1.5)", "normal quality"),
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
            ppp=self.nocupppp,
        )

    # Command tests

    def test_cmd_stn_complex_features(self):  # complex stn command with AND, BREAK and other features
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loratrigger <lora:xxx:1> AND AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality, <ppp:stn i0>",
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
            ),
        )

    def test_cmd_set_if(self):  # set and if commands
        self.process(
            PromptPair("<ppp:set v>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
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
                "<ppp:set v1>1<ppp:/set><ppp:if v1 gt 0><ppp:set v2>OK<ppp:/set><ppp:/if><ppp:if v2 eq 'OK'><ppp:echo v2><ppp:else>not OK<ppp:/if> <ppp:echo v2>NOK<ppp:/echo> <ppp:echo v3>OK<ppp:/echo>",
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
                "First: <ppp:set v>value1<ppp:/set>this test is <ppp:if v in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>\nSecond: <ppp:set v2>value3<ppp:/set>this test is <ppp:if not v2 in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>",
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
            ppp=self.nocupppp,
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
            ppp=self.nocupppp,
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

    # Choices tests

    def test_ch_choices(self):  # simple choices with weights
        self.process(
            PromptPair("the choices are: {3::choice1|2::choice2|choice3}", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_ch_unsupportedsampler(self):  # unsupported sampler
        self.process(
            PromptPair("the choices are: {@choice1|choice2|choice3}", ""),
            PromptPair("", ""),
            ppp=self.nocupppp,
            interrupted=True,
        )

    def test_ch_choices_withcomments(self):  # choices with comments and multiline
        self.process(
            PromptPair(
                "the choices are: {\n3::choice1 # this is option 1\n|2::choice2\n# this was option 2\n|choice3 # this is option 3\n}",
                "",
            ),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_ch_choices_multiple(self):  # choices with multiple selection
        self.process(
            PromptPair("the choices are: {~2$$, $$3::choice1|2:: choice2 |choice3}", ""),
            PromptPair("the choices are:  choice2 , choice3", ""),
            ppp=self.nocupppp,
        )

    def test_ch_choices_if_multiple(self):  # choices with if and multiple selection
        self.process(
            PromptPair("the choices are: {2$$, $$3::choice1|2 if _is_sd1::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp=self.nocupppp,
        )

    def test_ch_choices_set_if_multiple(self):  # choices with if user variable and multiple selection
        self.process(
            PromptPair("${var=test}the choices are: {2$$, $$3::choice1|2 if not var eq 'test'::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp=self.nocupppp,
        )

    def test_ch_choices_set_if_nested(self):  # nested choices with if user variable and multiple selection
        self.process(
            PromptPair(
                "${var=test}the choices are: {2$$, $$3::choice1${var2=test2} {if var2 eq 'test2'::choice11|choice12}|2 if not var eq 'test'::choice2|choice3}",
                "",
            ),
            PromptPair("the choices are: choice1 choice11, choice3", ""),
            ppp=self.nocupppp,
        )

    def test_ch_choicesinsidelora(self):  # simple choices inside a lora
        self.process(
            PromptPair("<lora:test1:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            PromptPair("<lora:test1:1><lora:test2:0.7>", ""),
            ppp=self.nocupppp,
        )

    def test_ch_removelorawithchoices(self):  # remove lora with choices inside
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
            ),
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
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
                "normal quality, <ppp:stn i0> {option1|option2}",
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
            ),
        )

    def test_wc_wildcard1a_text(self):  # simple text wildcard
        self.process(
            PromptPair("the choices are: __text/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard1a_json(self):  # simple json wildcard
        self.process(
            PromptPair("the choices are: __json/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard1a_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choices are: __yaml/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard1b_text(self):  # simple text wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$text/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard1b_json(self):  # simple json wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$json/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard1b_yaml(self):  # simple yaml wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$yaml/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard2_text(self):  # simple text wildcard with default options
        self.process(
            PromptPair("the choices are: __text/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard2_json(self):  # simple json wildcard with default options
        self.process(
            PromptPair("the choices are: __json/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard2_yaml(self):  # simple yaml wildcard with default options
        self.process(
            PromptPair("the choices are: __yaml/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_test2_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test2__", ""),
            PromptPair("the choice is: 2", ""),
            ppp=self.nocupppp,
        )

    def test_wc_test3_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test3__", ""),
            PromptPair("the choice is: one choice", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_index(self):  # wildcard with positional index filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_label(self):  # wildcard with label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_label2(self):  # wildcard with label filter in multiple choices
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label2'__", ""),
            PromptPair("the choice is: choice1-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_label3(self):  # wildcard with multiple label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_indexlabel(self):  # wildcard with mixed index and label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_compound(self):  # wildcard with compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1+label3'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_compound2(self):  # wildcard with inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bis", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_filter_compound3(self):  # wildcard with doubly inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bisbis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bisbis", ""),
            ppp=self.nocupppp,
        )

    def test_wc_nested_wildcard_text(self):  # nested text wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$text/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_nested_wildcard_json(self):  # nested json wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$json/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_nested_wildcard_yaml(self):  # nested yaml wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$yaml/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard4_yaml(self):  # simple yaml wildcard with one option
        self.process(
            PromptPair("the choices are: __yaml/wildcard4__", ""),
            PromptPair("the choices are: inline text", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard6_yaml(self):  # simple yaml wildcard with object formatted choices
        self.process(
            PromptPair("the choices are: __yaml/wildcard6__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
        )

    def test_wc_choice_wildcard_mix(self):  # choices with wildcard mix
        self.process(
            PromptPair("the choices are: {__~2$$yaml/wildcard2__|choice0}", ""),
            [
                PromptPair("the choices are: choice0", ""),
                PromptPair("the choices are: choice1, choice3", ""),
                PromptPair("the choices are: choice1, choice3", ""),
            ],
            ppp=self.nocupppp,
        )

    def test_wc_unsupportedsampler(self):  # unsupported sampler
        self.process(
            PromptPair("the choices are: __@yaml/wildcard2__", ""),
            PromptPair("", ""),
            ppp=self.nocupppp,
            interrupted=True,
        )

    def test_wc_wildcard_globbing(self):  # wildcard with globbing
        self.process(
            PromptPair("the choices are: __yaml/wildcard[12]__, __yaml/wildcard?__", ""),
            PromptPair("the choices are: choice3-choice2, <lora:test2:1>- choice2 -choice3", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcardwithvar(self):  # wildcard with inline variable
        self.process(
            PromptPair("the choices are: __yaml/wildcard5(var=test)__, __yaml/wildcard5__", ""),
            PromptPair("the choices are: inline test, inline default", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcardPS_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.process(
            PromptPair("the choices are: __yaml/wildcardPS__", ""),
            PromptPair("the choices are: prefix-choice2/choice3-suffix", ""),
            ppp=self.nocupppp,
        )

    def test_wc_anonymouswildcard_yaml(self):  # yaml anonymous wildcard
        self.process(
            PromptPair("the choices are: __yaml/anonwildcards__", ""),
            PromptPair("the choices are: six", ""),
            ppp=self.nocupppp,
        )

    def test_wc_wildcard_input(self):  # simple yaml wildcard input
        self.process(
            PromptPair("the choices are: __yaml_input/wildcardI__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.nocupppp,
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
                },
                {
                    **self.defopts,
                    "on_warning": PromptPostProcessor.ONWARNING_CHOICES.warn.value,
                    "variants_definitions": "test1(sdxl)=testmodel\ntest2=testmodel\ntest3(sd1)=testmodel\ntest4(invalid)=testmodel\nsdxl()=testmodel",
                },
                self.grammar_content,
                self.wildcards_obj,
            ),
        )

    # ComfyUI tests

    def test_comfyui_attention(self):  # attention conversion
        self.process(
            PromptPair("(test1) (test2:1.5) [test3] [(test4)]", ""),
            PromptPair("(test1) (test2:1.5) (test3:0.9) (test4:0.99)", ""),
            ppp=self.comfyuippp,
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
            ppp=self.nocupppp,
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
            ppp=self.nocupppp,
        )

    def test_parser_performance_complex_fullparser(
        self,
    ):  # performance test with a large prompt with new constructs (full parser)
        large_prompt = ", ".join(["__yaml/wildcard1__, (__yaml/wildcard2__), __yaml/wildcard3__, {one|two|three}"] * 15)
        self.process(
            PromptPair(large_prompt, ""),
            ppp=self.nocupppp,
        )

    # the following tests are performance tests with only one kind of the old constructs
    # same number of constructs and approximately the same full length

    def test_parser_performance_simple_attention(self):  # performance test with only attention
        large_prompt = ", ".join(["(one:1.2) two (three) four [five] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp=self.nocupppp,
        )

    def test_parser_performance_simple_schedules(self):  # performance test with only schedules
        large_prompt = ", ".join(["[one:1:0.5] two [three:0.8] four [five:5:0.2] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp=self.nocupppp,
        )

    def test_parser_performance_simple_alternation(self):  # performance test with only alternation
        large_prompt = ", ".join(["[one|1] two [three|3] four [five|5] six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp=self.nocupppp,
        )

    def test_parser_performance_simple_extranetwork(self):  # performance test with only extra networks
        large_prompt = ", ".join(["<lora:one:1> two <lora:three:1> four <lora:five:1> six"] * 20)
        self.process(
            PromptPair(large_prompt, ""),
            ppp=self.nocupppp,
        )


if __name__ == "__main__":
    unittest.main()
