import logging
import unittest
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))

from ppp import PromptPostProcessor
from ppp_logging import PromptPostProcessorLogFactory


class DictToObj:  # pylint: disable=too-few-public-methods
    """
    Converts a dictionary to an object with attribute access.
    from https://joelmccune.com/python-dictionary-as-object/
    """

    def __init__(self, in_dict: dict):
        assert isinstance(in_dict, dict)
        for key, val in in_dict.items():
            if isinstance(val, (list, tuple)):
                setattr(self, key, [DictToObj(x) if isinstance(x, dict) else x for x in val])
            else:
                setattr(self, key, DictToObj(val) if isinstance(val, dict) else val)


class TestPromptPostProcessor(unittest.TestCase):
    """
    A test case class for testing the PromptPostProcessor class.
    """

    def setUp(self):
        """
        Set up the test case by initializing the necessary objects and configurations.
        """
        lf = PromptPostProcessorLogFactory()
        self.ppp_logger = lf.log
        self.ppp_logger.setLevel(logging.DEBUG)
        self.__defopts = DictToObj(
            {
                "ppp_gen_debug": True,
                "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["ignore"],
                "ppp_stn_doi2i": False,
                "ppp_stn_separator": ", ",
                "ppp_stn_ignore_repeats": True,
                "ppp_stn_join_attention": True,
                "ppp_cup_doi2i": False,
                "ppp_cup_emptyconstructs": True,
                "ppp_cup_extraseparators": True,
                "ppp_cup_extraseparators2": True,
                "ppp_cup_extraspaces": True,
                "ppp_cup_breaks": True,
                "ppp_cup_breaks_eol": False,
                "ppp_cup_ands": True,
                "ppp_cup_ands_eol": False,
                "ppp_cup_extranetworktags": True,
                "ppp_rem_removeextranetworktags": False,
            }
        )
        self.__nocupopts = DictToObj(
            {
                "ppp_gen_debug": True,
                "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["ignore"],
                "ppp_stn_doi2i": False,
                "ppp_stn_separator": ", ",
                "ppp_stn_ignore_repeats": True,
                "ppp_stn_join_attention": True,
                "ppp_cup_doi2i": False,
                "ppp_cup_emptyconstructs": False,
                "ppp_cup_extraseparators": False,
                "ppp_cup_extraseparators2": False,
                "ppp_cup_extraspaces": False,
                "ppp_cup_breaks": False,
                "ppp_cup_breaks_eol": False,
                "ppp_cup_ands": False,
                "ppp_cup_ands_eol": False,
                "ppp_cup_extranetworktags": False,
                "ppp_rem_removeextranetworktags": False,
            }
        )
        self.__defprocessing = DictToObj({"sd_model": DictToObj({"is_sd1": False, "is_sd2": False, "is_sdxl": True})})
        self.__defstate = None
        self.defppp = PromptPostProcessor(self, self.__defprocessing, self.__defstate, self.__defopts)
        self.nocupppp = PromptPostProcessor(self, self.__defprocessing, self.__defstate, self.__nocupopts)

    def process(
        self,
        prompt,
        negative_prompt,
        expected_prompt,
        expected_negative_prompt,
        ppp=None,
    ):
        """
        Process the prompt and compare the results with the expected prompts.

        Args:
            prompt (str): The input prompt.
            negative_prompt (str): The input negative prompt.
            expected_prompt (str): The expected output prompt.
            expected_negative_prompt (str): The expected output negative prompt.
            ppp (object, optional): The post-processor object. Defaults to None.

        Returns:
            None
        """
        the_obj = self.defppp if ppp is None else ppp
        result_prompt, result_negative_prompt = the_obj.process_prompt(prompt, negative_prompt)
        self.assertEqual(result_prompt, expected_prompt, f"Prompt should be '{expected_prompt}'")
        self.assertEqual(
            result_negative_prompt,
            expected_negative_prompt,
            f"Negative Prompt should be '{expected_negative_prompt}'",
        )

    # Send To Negative tests

    def test_nt_simple_oldformat(self):  # negtags with different parameters and separations
        self.process(
            "flowers<!red!>, <!!s!green!>, <!!e!blue!><!!p0!yellow!>, <!!p1!purple!><!!p2!black!>",
            "<!!i0!!>normal quality<!!i1!!>, worse quality<!!i2!!>",
            "flowers",
            "red, green, yellow, normal quality, purple, worse quality, black, blue",
        )

    def test_nt_simple(self):  # negtags with different parameters and separations
        self.process(
            "flowers<ppp:stn>red<ppp:/stn>, <ppp:stn s>green<ppp:/stn>, <ppp:stn e>blue<ppp:/stn><ppp:stn p0>yellow<ppp:/stn>, <ppp:stn p1>purple<ppp:/stn><ppp:stn p2>black<ppp:/stn>",
            "<ppp:stn i0>normal quality<ppp:stn i1>, worse quality<ppp:stn i2>",
            "flowers",
            "red, green, yellow, normal quality, purple, worse quality, black, blue",
        )

    def test_nt_complex(self):  # complex negtags
        self.process(
            "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
            "normal quality, <ppp:stn i0>, bad quality<ppp:stn i1>, worse quality",
            "flowers",
            "red, (pink:1.21), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
        )

    def test_nt_complex_nocleanup(self):  # complex negtags with no cleanup
        self.process(
            "<ppp:stn>red<ppp:/stn> ((<ppp:stn s>pink<ppp:/stn>)), flowers <ppp:stn e>purple<ppp:/stn>, <ppp:stn p0>mauve<ppp:/stn><ppp:stn e>blue<ppp:/stn>, <ppp:stn p0>yellow<ppp:/stn> <ppp:stn p1>green<ppp:/stn>",
            "normal quality, <ppp:stn i0>, bad quality<ppp:stn i1>, worse quality",
            " (()), flowers , ,  ",
            "red, (pink:1.21), normal quality, mauve, yellow, bad quality, green, worse quality, purple, blue",
            self.nocupppp,
        )

    def test_nt_inside_attention(self):  # negtag inside attention
        self.process(
            "[<ppp:stn>neg1<ppp:/stn>] this is a ((test<ppp:stn e>neg2<ppp:/stn>) (test:2.0): 1.5 ) (red<ppp:stn>[square]<ppp:/stn>:1.5)",
            "normal quality",
            "this is a ((test) (test:2.0):1.5) (red:1.5)",
            "[neg1], ([square]:1.5), normal quality, (neg2:1.65)",
        )

    def test_nt_inside_alternation(self):  # negtag inside alternation
        self.process(
            "this is a (([complex<ppp:stn>neg1<ppp:/stn>|simple<ppp:stn>neg2<ppp:/stn>|regular<ppp:stn>neg3<ppp:/stn>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_nt_inside_alternation_recursive(self):  # negtag inside alternation (recursive alternation)
        self.process(
            "this is a (([complex<ppp:stn>neg1<ppp:/stn>[one|two<ppp:stn>neg12<ppp:/stn>||three|four(<ppp:stn>neg14<ppp:/stn>)]|simple<ppp:stn>neg2<ppp:/stn>|regular<ppp:stn>neg3<ppp:/stn>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex[one|two||three|four]|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([[|neg12|||]||]:1.65), ([[||||(neg14)]||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_nt_inside_scheduling(self):  # negtag inside scheduling
        self.process(
            "this is [abc<ppp:stn>neg1<ppp:/stn>:def<ppp:stn e>neg2<ppp:/stn>: 5 ]",
            "normal quality",
            "this is [abc:def:5]",
            "[neg1::5], normal quality, [neg2:5]",
        )

    def test_nt_complex_features(self):  # complex negtags with AND, BREAK and other features
        self.process(
            "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loraword <lora:xxx:1> AND AND hypernetword <hypernet:yyy>:0.3",
            "normal quality, <ppp:stn i0>",
            "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5]:0.5 AND loraword <lora:xxx:1> AND hypernetword <hypernet:yyy>:0.3",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
        )

    def test_nt_complex_features_newformat(self):  # complex negtags with AND, BREAK and other features (new format)
        self.process(
            "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loraword <lora:xxx:1> AND AND hypernetword <hypernet:yyy>:0.3",
            "normal quality, <ppp:stn i0>",
            "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5]:0.5 AND loraword <lora:xxx:1> AND hypernetword <hypernet:yyy>:0.3",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
        )

    # Wildcard tests

    def test_wc_ignore(self):  # wildcards with ignore option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["ignore"],
                    }
                ),
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.process(
            "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
            "normal quality, <ppp:stn i0> {option1|option2}",
            "this is: a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5]<lora:xxx:1>",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["remove"],
                    }
                ),
            ),
        )

    def test_wc_warn(self):  # wildcards with warn option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["warn"],
                    }
                ),
            ),
        )

    def test_wc_stop(self):  # wildcards with stop option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor.WILDCARD_STOP + "__bad_wildcard__",
            PromptPostProcessor.WILDCARD_STOP + "{option1|option2}",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["stop"],
                    }
                ),
            ),
        )

    # Cleanup tests

    def test_cl_simple(self):  # simple cleanup
        self.process(
            "  this is a ((test ), ,  () [] ( , test ,:2.0):1.5) (red:1.5)  ",
            "  normal quality  ",
            "this is a ((test), (test,:2.0):1.5) (red:1.5)",
            "normal quality",
        )

    def test_cl_complex(self):  # complex cleanup
        self.process(
            "  this is BREAKABLE a ((test), ,AND AND() [] <lora:test> ANDERSON (test:2.0):1.5) :o BREAK \n BREAK (red:1.5)  ",
            "  [:hands, feet, :0.15]normal quality  ",
            "this is BREAKABLE a ((test) AND <lora:test> ANDERSON (test:2.0):1.5) :o BREAK (red:1.5)",
            "[:hands, feet, :0.15]normal quality",
        )

    def test_cl_removenetworktags(self):  # remove network tags
        self.process(
            "this is a <lora:test> test",
            "",
            "this is a test",
            "",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj({**self.__defopts.__dict__, "ppp_rem_removeextranetworktags": True}),
            ),
        )

    def test_cl_dontremoveseparatorsoneol(self):  # dont remove separators on eol
        self.process(
            "this is a test,\nsecond line",
            "",
            "this is a test,\nsecond line",
            "",
            PromptPostProcessor(
                self,
                self.__defprocessing,
                self.__defstate,
                DictToObj({**self.__defopts.__dict__, "ppp_cup_extraseparators2": False}),
            ),
        )

    # Command tests

    def test_cmd_stn_complex_features(self):  # complex stn command with AND, BREAK and other features
        self.process(
            "[<ppp:stn>neg5<ppp:/stn>] this \\(is\\): a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5]:0.5 AND loraword <lora:xxx:1> AND AND hypernetword <hypernet:yyy>:0.3",
            "normal quality, <ppp:stn i0>",
            "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5]:0.5 AND loraword <lora:xxx:1> AND hypernetword <hypernet:yyy>:0.3",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
        )

    def test_cmd_if_complex_features(self):  # complex if command
        self.process(
            "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK, BREAK <ppp:if _sd eq 'sd1'>with [abc<ppp:stn>neg4<ppp:/stn>:def:5]<ppp:/if>:0.5 AND <ppp:if _sd eq 'sd1'>loraword <lora:xxx:1><ppp:elif _sd eq 'sdxl'>hypernetword <hypernet:yyy><ppp:else>nothing<ppp:/if>:0.3",
            "normal quality",
            "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK :0.5 AND hypernetword <hypernet:yyy>:0.3",
            "normal quality",
        )

    def test_cmd_if_nested(self):  # nested if command
        self.process(
            "this is <ppp:if _sd eq 'sd1'>SD1<ppp:else><ppp:if _sd eq 'sdxl'>SDXL<ppp:else>SD2<ppp:/if><ppp:/if>",
            "",
            "this is SDXL",
            "",
        )

    def test_cmd_set_if(self):  # set and if commands
        self.process(
            "<ppp:set v>value<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
            "",
            "this test is OK",
            "",
        )

    def test_cmd_set_if_echo_nested(self):  # nested set, if and echo commands
        self.process(
            "<ppp:set v1>1<ppp:/set><ppp:if v1 gt 0><ppp:set v2>OK<ppp:/set><ppp:/if><ppp:if v2 eq 'OK'><ppp:echo v2><ppp:else>not OK<ppp:/if>",
            "",
            "OK",
            "",
        )


if __name__ == "__main__":
    unittest.main()
