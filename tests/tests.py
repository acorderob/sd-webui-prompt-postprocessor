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
                "ppp_cup_extraspaces": True,
                "ppp_cup_breaks": True,
            }
        )
        self.defppp = PromptPostProcessor(self, self.__defopts)

    def ppp_interrupt(self):
        pass # fake interrupt

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

    def test_tag_default(self):  # negtag with no parameters
        self.process(
            "flowers<!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_start(self):  # negtag with s parameter
        self.process(
            "flowers<!!s!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_end(self):  # negtag with e parameter
        self.process(
            "flowers<!!e!red!>",
            "normal quality, worse quality",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tag_insertion_mid_sep(self):  # negtag with p parameter and insertion in the middle
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, <!!i0!!>, worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tag_insertion_mid_no_sep(self):  # negtag with p parameter and insertion in the middle without separator
        self.process(
            "flowers<!!p0!red!>",
            "normal quality<!!i0!!>worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tag_insertion_start_sep(self):  # negtag with p parameter and insertion at the start
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>, normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_insertion_start_no_sep(self):  # negtag with p parameter and insertion at the start without separator
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_insertion_end_sep(self):  # negtag with p parameter and insertion at the end
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality, <!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tag_insertion_end_no_sep(self):  # negtag with p parameter and insertion at the end without separator
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality<!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_complex(self):  # complex negtags
        self.process(
            "<!red!> (<!!s!pink!>), flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            "flowers",
            "red, (pink), normal quality, yellow, bad quality, green, worse quality, purple, blue",
        )

    def test_complex_no_cleanup(self):  # complex negtags with no cleanup
        self.process(
            "<!red!> (<!!s!pink!>), flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            " (), flowers , ,  ",
            "red, (pink), normal quality, yellow, bad quality, green, worse quality, purple, blue",
            PromptPostProcessor(
                self,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_cup_emptyconstructs": False,
                        "ppp_cup_extraseparators": False,
                        "ppp_cup_extraspaces": False,
                        "ppp_cup_breaks": False,
                    }
                ),
            ),
        )

    def test_inside_attention1(self):  # negtag inside attention
        self.process(
            "[<!neg1!>] this is a ((test<!!e!neg2!>) (test:2.0): 1.5 )",
            "normal quality",
            "this is a ((test) (test:2.0):1.5)",
            "[neg1], normal quality, (neg2:1.65)",
        )

    def test_inside_attention2(self):  # negtag inside attention
        self.process(
            "(red<![square]!>:1.5)",
            "",
            "(red:1.5)",
            "([square]:1.5)",
        )

    def test_inside_alternation1(self):  # negtag inside alternation
        self.process(
            "this is a (([complex|simple<!neg1!>|regular] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex|simple|regular] test)(test:2.0):1.5)",
            "([|neg1|]:1.65), normal quality",
        )

    def test_inside_alternation2(self):  # negtag inside alternation
        self.process(
            "this is a (([complex<!neg1!>|simple<!neg2!>|regular<!neg3!>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_inside_alternation3(self):  # negtag inside alternation (recursive alternation)
        self.process(
            "this is a (([complex<!neg1!>[one|two<!neg12!>||three|four(<!neg14!>)]|simple<!neg2!>|regular<!neg3!>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex[one|two||three|four]|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([[|neg12|||]||]:1.65), ([[||||(neg14)]||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_inside_scheduling(self):  # negtag inside scheduling
        self.process(
            "this is [abc<!neg1!>:def<!!e!neg2!>: 5 ]",
            "normal quality",
            "this is [abc:def:5]",
            "[neg1::5], normal quality, [neg2:5]",
        )

    def test_complex_features(self):  # complex negtags with features
        self.process(
            "[<!neg5!>] this is: a (([complex|simple<!neg6!>|regular] test<!neg1!>)(test:2.0):1.5) \nBREAK, BREAK with [abc<!neg4!>:def<!!p0!neg2(neg3:1.6)!>:5] <lora:xxx:1>",
            "normal quality, <!!i0!!>",
            "this is: a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5] <lora:xxx:1>",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
        )

    # Wildcard tests

    def test_wildcards_ignore(self):  # wildcards with ignore option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor(
                self,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["ignore"],
                    }
                ),
            ),
        )

    def test_wildcards_remove(self):  # wildcards with remove option
        self.process(
            "[<!neg5!>] this is: __bad_wildcard__ a (([complex|simple<!neg6!>|regular] test<!neg1!>)(test:2.0):1.5) \nBREAK, BREAK with [abc<!neg4!>:def<!!p0!neg2(neg3:1.6)!>:5] <lora:xxx:1>",
            "normal quality, <!!i0!!> {option1|option2}",
            "this is: a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5] <lora:xxx:1>",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            PromptPostProcessor(
                self,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["remove"],
                    }
                ),
            ),
        )

    def test_wildcards_warn(self):  # wildcards with warn option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor(
                self,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["warn"],
                    }
                ),
            ),
        )

    def test_wildcards_stop(self):  # wildcards with stop option
        self.process(
            "__bad_wildcard__",
            "{option1|option2}",
            PromptPostProcessor.WILDCARD_STOP + "__bad_wildcard__",
            PromptPostProcessor.WILDCARD_STOP + "{option1|option2}",
            PromptPostProcessor(
                self,
                DictToObj(
                    {
                        **self.__defopts.__dict__,
                        "ppp_gen_ifwildcards": PromptPostProcessor.IFWILDCARDS_CHOICES["stop"],
                    }
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
