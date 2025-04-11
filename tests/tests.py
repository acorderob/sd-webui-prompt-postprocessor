from collections import namedtuple
import logging
import unittest
import sys
import os

sys.path.append(os.path.join(os.path.realpath(__file__), ".."))  # base path for the extension

from ppp_wildcards import PPPWildcards  # pylint: disable=import-error
from ppp import PromptPostProcessor  # pylint: disable=import-error
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory  # pylint: disable=import-error


PromptPair = namedtuple("PromptPair", ["prompt", "negative_prompt"], defaults=["", ""])


class TestPromptPostProcessor(unittest.TestCase):
    """
    A test case class for testing the PromptPostProcessor class.
    """

    def setUp(self):
        """
        Set up the test case by initializing the necessary objects and configurations.
        """
        lf = PromptPostProcessorLogFactory()
        self.__ppp_logger = lf.log
        self.__ppp_logger.setLevel(logging.DEBUG)
        self.__defopts = {
            "debug_level": DEBUG_LEVEL.full.value,
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
            "cleanup_extra_spaces": True,
            "cleanup_breaks": True,
            "cleanup_breaks_eol": False,
            "cleanup_ands": True,
            "cleanup_ands_eol": False,
            "cleanup_extranetwork_tags": True,
            "cleanup_merge_attention": True,
            "remove_extranetwork_tags": False,
        }
        self.__def_env_info = {
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
        self.__interrupted = False
        self.__wildcards_obj = PPPWildcards(lf.log)
        self.__wildcards_obj.refresh_wildcards(
            DEBUG_LEVEL.full,
            [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "wildcards")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "wildcards2")),
            ],
        )
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.__grammar_content = file.read()
        self.__defppp = PromptPostProcessor(
            self.__ppp_logger,
            self.__interrupt,
            self.__def_env_info,
            self.__defopts,
            self.__grammar_content,
            self.__wildcards_obj,
        )
        self.__nocupppp = PromptPostProcessor(
            self.__ppp_logger,
            self.__interrupt,
            self.__def_env_info,
            {
                **self.__defopts,
                "cleanup_empty_constructs": False,
                "cleanup_extra_separators": False,
                "cleanup_extra_separators2": False,
                "cleanup_extra_spaces": False,
                "cleanup_breaks": False,
                "cleanup_breaks_eol": False,
                "cleanup_ands": False,
                "cleanup_ands_eol": False,
                "cleanup_extranetwork_tags": False,
                "cleanup_merge_attention": False,
            },
            self.__grammar_content,
            self.__wildcards_obj,
        )
        self.__comfyuippp = PromptPostProcessor(
            self.__ppp_logger,
            self.__interrupt,
            {
                **self.__def_env_info,
                "app": "comfyui",
                "model_class": "SDXL",
            },
            self.__defopts,
            self.__grammar_content,
            self.__wildcards_obj,
        )

    def __interrupt(self):
        self.__interrupted = True

    def __process(
        self,
        input_prompts: PromptPair,
        expected_output_prompts: PromptPair | list[PromptPair],
        seed: int = 1,
        ppp=None,
        interrupted=False,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            input_prompts (PromptPair): The input prompts.
            expected_output_prompts (PromptPair | list[PromptPair]): The expected prompts.
            seed (int, optional): The seed value. Defaults to 1.
            ppp (object, optional): The post-processor object. Defaults to None.
            interrupted (bool, optional): The interrupted flag. Defaults to False.

        Returns:
            None
        """
        the_obj = ppp or self.__defppp
        out = expected_output_prompts if isinstance(expected_output_prompts, list) else [expected_output_prompts]
        for eo in out:
            result_prompt, result_negative_prompt, _ = the_obj.process_prompt(
                input_prompts.prompt,
                input_prompts.negative_prompt,
                seed,
            )
            self.assertEqual(self.__interrupted, interrupted, "Interrupted flag is incorrect")
            if not self.__interrupted:
                self.assertEqual(result_prompt, eo.prompt, "Incorrect prompt")
                self.assertEqual(result_negative_prompt, eo.negative_prompt, "Incorrect negative prompt")
            seed += 1

    # Send To Negative tests

    def test_stn_simple(self):  # negtags with different parameters and separations
        self.__process(
            PromptPair(
                "flowers<ppp:stn>red<ppp:/stn>, <ppp:stn s>green<ppp:/stn>, <ppp:stn e>blue<ppp:/stn><ppp:stn p0>yellow<ppp:/stn>, <ppp:stn p1>purple<ppp:/stn><ppp:stn p2>black<ppp:/stn>",
                "<ppp:stn i0>normal quality<ppp:stn i1>, worse quality<ppp:stn i2>",
            ),
            PromptPair("flowers", "red, green, yellow, normal quality, purple, worse quality, black, blue"),
        )

    def test_stn_complex(self):  # complex negtags
        self.__process(
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
        self.__process(
            PromptPair(
                "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
                "normal quality, <ppp:stn i0>, bad quality<ppp:stn i1>, worse quality",
            ),
            PromptPair(
                " (()), flowers , ,  ",
                "red, ((pink)), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
            ),
            ppp=self.__nocupppp,
        )

    def test_stn_inside_attention(self):  # negtag inside attention
        self.__process(
            PromptPair(
                "[<ppp:stn>neg1<ppp:/stn>] this is a ((test<ppp:stn e>neg2<ppp:/stn>) (test:2.0): 1.5 ) (red<ppp:stn>[square]<ppp:/stn>:1.5)",
                "normal quality",
            ),
            PromptPair(
                "this is a ((test) (test:2):1.5) (red:1.5)", "[neg1], ([square]:1.5), normal quality, (neg2:1.65)"
            ),
        )

    def test_stn_inside_alternation(self):  # negtag inside alternation
        self.__process(
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
        self.__process(
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
        self.__process(
            PromptPair("this is [abc<ppp:stn>neg1<ppp:/stn>:def<ppp:stn e>neg2<ppp:/stn>: 5 ]", "normal quality"),
            [PromptPair("this is [abc:def:5]", "[neg1::5], normal quality, [neg2:5]")],
        )

    def test_stn_complex_features(self):  # complex negtags with AND, BREAK and other features
        self.__process(
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
        self.__process(
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
        self.__process(
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
        self.__process(
            PromptPair("  this is a ((test ), , ,  (), ,   [] ( , test ,:2.0):1.5) (red:1.5)  ", "  normal quality  "),
            PromptPair("this is a ((test), (test,:2):1.5) (red:1.5)", "normal quality"),
        )

    def test_cl_complex(self):  # complex cleanup
        self.__process(
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
        self.__process(
            PromptPair("this is a <lora:test:1> test__yaml/wildcard7__", ""),
            PromptPair("this is a test", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {**self.__defopts, "remove_extranetwork_tags": True},
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_cl_dontremoveseparatorsoneol(self):  # don't remove separators on eol
        self.__process(
            PromptPair("this is a test,\nsecond line", ""),
            PromptPair("this is a test,\nsecond line", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {**self.__defopts, "cleanup_extra_separators2": False},
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_cl_mergeattention(self):  # merge attention
        self.__process(
            PromptPair(
                "this is (a test:1.5) of (attention (merging:1.2)) where ((this)) ((is joined:1.2)) and ([this too]:1.3)",
                "",
            ),
            PromptPair(
                "this is (a test:1.5) of (attention (merging:1.2)) where (this:1.21) (is joined:1.32) and (this too:1.17)",
                "",
            ),
        )

    # Command tests

    def test_cmd_stn_complex_features(self):  # complex stn command with AND, BREAK and other features
        self.__process(
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
        self.__process(
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
        self.__process(
            PromptPair(
                "this is <ppp:if _sd eq 'sd1'>SD1<ppp:else><ppp:if _is_pony>PONY<ppp:else>SD2<ppp:/if><ppp:/if><ppp:if _is_sdxl_no_pony>NOPONY<ppp:/if><ppp:if _is_pure_sdxl>NOPONY<ppp:/if>",
                "",
            ),
            PromptPair("this is PONY", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                {
                    **self.__def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.__defopts,
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_cmd_set_if(self):  # set and if commands
        self.__process(
            PromptPair("<ppp:set v>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_eval_if(self):  # set and if commands
        self.__process(
            PromptPair("<ppp:set v evaluate>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_echo_nested(self):  # nested set, if and echo commands
        self.__process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:if v1 gt 0><ppp:set v2>OK<ppp:/set><ppp:/if><ppp:if v2 eq 'OK'><ppp:echo v2><ppp:else>not OK<ppp:/if> <ppp:echo v2>NOK<ppp:/echo> <ppp:echo v3>OK<ppp:/echo>",
                "",
            ),
            PromptPair("OK OK OK", ""),
        )

    def test_cmd_set_if_complex_conditions_1(self):  # complex conditions (or)
        self.__process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if v1 or v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_2(self):  # complex conditions (and)
        self.__process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>true<ppp:/set>this test is <ppp:if v1 and v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_3(self):  # complex conditions (not)
        self.__process(
            PromptPair("<ppp:set v1>false<ppp:/set>this test is <ppp:if not v1>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_4(self):  # complex conditions (not, precedence)
        self.__process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not (v1 and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_5(self):  # complex conditions (not, precedence, comparison)
        self.__process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not(v1 eq '1' and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_6(self):  # complex conditions
        self.__process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq '1' and v2 eq '2' and v3 eq '3'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_7(self):  # complex conditions
        self.__process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq '1' and v2 not eq '2' or v3 eq '3'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if2(self):  # set and more complex if commands
        self.__process(
            PromptPair(
                "First: <ppp:set v>value1<ppp:/set>this test is <ppp:if v in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>\nSecond: <ppp:set v2>value3<ppp:/set>this test is <ppp:if not v2 in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("First: this test is OK\nSecond: this test is OK", ""),
        )

    def test_cmd_set_add_if(self):  # set, add and if commands
        self.__process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v add>2<ppp:/set>this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_add_DP_if(self):  # set, add (DP format) and if commands
        self.__process(
            PromptPair(
                "${v=value}${v+=2}this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_immediateeval(self):  # set (DP format) with mixed evaluation
        self.__process(
            PromptPair(
                "${var=!__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var2:default}, ${var3=__yaml/wildcard1__}${var3}, ${var3}",
                "",
            ),
            PromptPair("the choices are: choice2, choice2, default, choice3, choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_cmd_set_mixeval(self):  # set and add (DP format) with mixed evaluation
        self.__process(
            PromptPair(
                "${var=__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var+=, __yaml/wildcard2__}${var}, ${var}, ${var+=!, __yaml/wildcard3__}${var}, ${var}",
                "",
            ),
            PromptPair(
                "the choices are: choice2, choice3, choice1, choice1- choice2 -choice3, choice2,  choice2 -choice1-choice3, choice2, choice3-choice1- choice2 , choice1, choice2 , choice2, choice3-choice1- choice2 , choice1, choice2 ",
                "",
            ),
            ppp=self.__nocupppp,
        )

    def test_cmd_set_ifundefined_if(self):  # set, ifundefined and if commands
        self.__process(
            PromptPair(
                "<ppp:set v ifundefined>value<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_if_2(self):  # set, ifundefined and if commands
        self.__process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v ifundefined>value2<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if(self):  # set, ifundefined (DP format) and if commands
        self.__process(
            PromptPair(
                "${v?=value}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if_2(self):  # set, ifundefined (DP format) and if commands
        self.__process(
            PromptPair(
                "${v=!value}${v?=!value2}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    # Choices tests

    def test_ch_choices(self):  # simple choices with weights
        self.__process(
            PromptPair("the choices are: {3::choice1|2::choice2|choice3}", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_unsupportedsampler(self):  # unsupported sampler
        self.__process(
            PromptPair("the choices are: {@choice1|choice2|choice3}", ""),
            PromptPair("", ""),
            ppp=self.__nocupppp,
            interrupted=True,
        )

    def test_ch_choices_withcomments(self):  # choices with comments and multiline
        self.__process(
            PromptPair(
                "the choices are: {\n3::choice1 # this is option 1\n|2::choice2\n# this was option 2\n|choice3 # this is option 3\n}",
                "",
            ),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_choices_multiple(self):  # choices with multiple selection
        self.__process(
            PromptPair("the choices are: {~2$$, $$3::choice1|2:: choice2 |choice3}", ""),
            PromptPair("the choices are:  choice2 , choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_choices_if_multiple(self):  # choices with if and multiple selection
        self.__process(
            PromptPair("the choices are: {2$$, $$3::choice1|2 if _is_sd1::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_choices_set_if_multiple(self):  # choices with if user variable and multiple selection
        self.__process(
            PromptPair("${var=test}the choices are: {2$$, $$3::choice1|2 if not var eq 'test'::choice2|choice3}", ""),
            PromptPair("the choices are: choice1, choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_choices_set_if_nested(self):  # nested choices with if user variable and multiple selection
        self.__process(
            PromptPair(
                "${var=test}the choices are: {2$$, $$3::choice1${var2=test2} {if var2 eq 'test2'::choice11|choice12}|2 if not var eq 'test'::choice2|choice3}",
                "",
            ),
            PromptPair("the choices are: choice1 choice11, choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_choicesinsidelora(self):  # simple choices inside a lora
        self.__process(
            PromptPair("<lora:test1:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            PromptPair("<lora:test1:1><lora:test2:0.7>", ""),
            ppp=self.__nocupppp,
        )

    def test_ch_removelorawithchoices(self):  # remove lora with choices inside
        self.__process(
            PromptPair("<lora:test1:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {**self.__defopts, "remove_extranetwork_tags": True},
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    # Wildcards tests

    def test_wc_ignore(self):  # wildcards with ignore option
        self.__process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {
                    **self.__defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.__process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
                "normal quality, <ppp:stn i0> {option1|option2}",
            ),
            PromptPair(
                "this is: a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]<lora:xxx:1>",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {
                    **self.__defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.remove.value,
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_wc_warn(self):  # wildcards with warn option
        self.__process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {
                    **self.__defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_wc_stop(self):  # wildcards with stop option
        self.__process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(
                PromptPostProcessor.WILDCARD_STOP.format("__bad_wildcard__") + "__bad_wildcard__",
                "{option1|option2}",
            ),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {
                    **self.__defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value,
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
            interrupted=True,
        )

    def test_wcinvar_warn(self):  # wildcards in var with warn option
        self.__process(
            PromptPair("${v=__bad_wildcard__}${v}", ""),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                self.__def_env_info,
                {
                    **self.__defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    def test_wc_wildcard1a_text(self):  # simple text wildcard
        self.__process(
            PromptPair("the choices are: __text/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard1a_json(self):  # simple json wildcard
        self.__process(
            PromptPair("the choices are: __json/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard1a_yaml(self):  # simple yaml wildcard
        self.__process(
            PromptPair("the choices are: __yaml/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard1b_text(self):  # simple text wildcard with multiple choices
        self.__process(
            PromptPair("the choices are: __2-$$text/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard1b_json(self):  # simple json wildcard with multiple choices
        self.__process(
            PromptPair("the choices are: __2-$$json/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard1b_yaml(self):  # simple yaml wildcard with multiple choices
        self.__process(
            PromptPair("the choices are: __2-$$yaml/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard2_text(self):  # simple text wildcard with default options
        self.__process(
            PromptPair("the choices are: __text/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard2_json(self):  # simple json wildcard with default options
        self.__process(
            PromptPair("the choices are: __json/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard2_yaml(self):  # simple yaml wildcard with default options
        self.__process(
            PromptPair("the choices are: __yaml/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_test2_yaml(self):  # simple yaml wildcard
        self.__process(
            PromptPair("the choice is: __testwc/test2__", ""),
            PromptPair("the choice is: 2", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_test3_yaml(self):  # simple yaml wildcard
        self.__process(
            PromptPair("the choice is: __testwc/test3__", ""),
            PromptPair("the choice is: one choice", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_index(self):  # wildcard with positional index filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'2'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_label(self):  # wildcard with label filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'label1'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_label2(self):  # wildcard with label filter in multiple choices
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'label2'__", ""),
            PromptPair("the choice is: choice1-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_label3(self):  # wildcard with multiple label filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'label1,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_indexlabel(self):  # wildcard with mixed index and label filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'2,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_compound(self):  # wildcard with compound filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2'label1+label3'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_compound2(self):  # wildcard with inherited compound filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2bis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bis", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard_filter_compound3(self):  # wildcard with doubly inherited compound filter
        self.__process(
            PromptPair("the choice is: __yaml/wildcard2bisbis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bisbis", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_nested_wildcard_text(self):  # nested text wildcard with repeating multiple choices
        self.__process(
            PromptPair("the choices are: __r3$$-$$text/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_nested_wildcard_json(self):  # nested json wildcard with repeating multiple choices
        self.__process(
            PromptPair("the choices are: __r3$$-$$json/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_nested_wildcard_yaml(self):  # nested yaml wildcard with repeating multiple choices
        self.__process(
            PromptPair("the choices are: __r3$$-$$yaml/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard4_yaml(self):  # simple yaml wildcard with one option
        self.__process(
            PromptPair("the choices are: __yaml/wildcard4__", ""),
            PromptPair("the choices are: inline text", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcard6_yaml(self):  # simple yaml wildcard with object formatted choices
        self.__process(
            PromptPair("the choices are: __yaml/wildcard6__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_choice_wildcard_mix(self):  # choices with wildcard mix
        self.__process(
            PromptPair("the choices are: {__~2$$yaml/wildcard2__|choice0}", ""),
            [
                PromptPair("the choices are: choice0", ""),
                PromptPair("the choices are: choice1, choice3", ""),
                PromptPair("the choices are: choice1, choice3", ""),
            ],
            ppp=self.__nocupppp,
        )

    def test_wc_unsupportedsampler(self):  # unsupported sampler
        self.__process(
            PromptPair("the choices are: __@yaml/wildcard2__", ""),
            PromptPair("", ""),
            ppp=self.__nocupppp,
            interrupted=True,
        )

    def test_wc_wildcard_globbing(self):  # wildcard with globbing
        self.__process(
            PromptPair("the choices are: __yaml/wildcard[12]__, __yaml/wildcard?__", ""),
            PromptPair("the choices are: choice3-choice2, <lora:test2:1>- choice2 -choice3", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcardwithvar(self):  # wildcard with inline variable
        self.__process(
            PromptPair("the choices are: __yaml/wildcard5(var=test)__, __yaml/wildcard5__", ""),
            PromptPair("the choices are: inline test, inline default", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_wildcardPS_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.__process(
            PromptPair("the choices are: __yaml/wildcardPS__", ""),
            PromptPair("the choices are: prefix-choice2/choice3-suffix", ""),
            ppp=self.__nocupppp,
        )

    def test_wc_anonymouswildcard_yaml(self):  # yaml anonymous wildcard
        self.__process(
            PromptPair("the choices are: __yaml/anonwildcards__", ""),
            PromptPair("the choices are: six", ""),
            ppp=self.__nocupppp,
        )

    # Model variants tests

    def test_variants(self):
        self.__process(
            PromptPair(
                "<ppp:if _is_test1>test1<ppp:/if><ppp:if _is_test2>test2<ppp:/if><ppp:if _is_test3>test3<ppp:/if><ppp:if _is_test4>test4<ppp:/if>",
                "",
            ),
            PromptPair("test1test2", ""),
            ppp=PromptPostProcessor(
                self.__ppp_logger,
                self.__interrupt,
                {
                    **self.__def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/testmodel.safetensors",
                },
                {
                    **self.__defopts,
                    "variants_definitions": "test1(sdxl)=testmodel\ntest2=testmodel\ntest3(sd1)=testmodel\ntest4(invalid)=testmodel\nsdxl()=testmodel",
                },
                self.__grammar_content,
                self.__wildcards_obj,
            ),
        )

    # ComfyUI tests

    def test_comfyui_attention(self):  # attention conversion
        self.__process(
            PromptPair("(test1) (test2:1.5) [test3] [(test4)]", ""),
            PromptPair("(test1) (test2:1.5) (test3:0.9) (test4:0.99)", ""),
            ppp=self.__comfyuippp,
        )

    # def test_mix(self):
    #     self.__process(
    #         PromptPair(
    #             "__text/wildcard1__ (__text/wildcard2__) (__text/wildcard3__:1.5) [__text/wildcard1__] [__text/wildcard2__:__text/wildcard3__:0.5] [__text/wildcard1__|__text/wildcard2__] # <lora:__text/wildcard3__:1> {opt1_1|opt1_2} ({opt2_1|opt2_2}) ({opt3_1|opt3_2}:1.5) [{opt4_1|opt4_2}] [{opt5_1|opt5_2}:{opt6_1|opt6_2}:0.5] [{opt7_1|opt7_2}|{opt8_1|opt8_2}] # <lora:{opt9_1|opt9_2}:1> {opt1_1|__text/wildcard1__} ({opt2_1|__text/wildcard2__}) ({opt3_1|__text/wildcard3__}:1.5) [{opt4_1|__text/wildcard1__}] [{opt5_1|__text/wildcard2__}# :{opt6_1|__text/wildcard3__}:0.5] [{opt7_1|__text/wildcard1__}|{opt8_1|__text/wildcard2__}] {<lora:opt9_1:1>|<lora:__text/wildcard3__:1>}",
    #             "",
    #         ),
    #         PromptPair(
    #             "choice2 ( choice2 -choice1) (choice1, choice2 :1.5) [choice1] [choice1-choice1:choice3, choice2 :0.5] [choice2| choice2 - choice2 ] <lora: choice2 ,choice1:1> opt1_1 # (opt2_2) (opt3_1:1.5) [opt4_2] [opt5_1:opt6_2:0.5] [opt7_1|opt8_1] <lora:opt9_2:1> choice3 (opt2_1) (choice1,choice3:1.5) [choice1] [choice3-choice3:opt6_1:0.5] [opt7_1|# opt8_1] <lora:choice1, choice2 :1>",
    #             "",
    #         ),
    #         ppp=self.__nocupppp,
    #     )


if __name__ == "__main__":
    unittest.main()
