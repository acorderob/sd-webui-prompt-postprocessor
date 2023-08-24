import logging
import unittest
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))

from sendtonegative import SendToNegative  # pylint: disable=import-error
from stnlogging import SendToNegativeLogFactory


class TestSendToNegative(unittest.TestCase):
    def setUp(self):
        lf = SendToNegativeLogFactory()
        self.__log = lf.log
        self.__log.setLevel(logging.DEBUG)
        self.defstn = SendToNegative(self.__log, separator=", ", ignore_repeats=True, join_attention=True, cleanup=True)

    def process(
        self,
        prompt,
        negative_prompt,
        expected_prompt,
        expected_negative_prompt,
        stn=None,
    ):
        the_obj = self.defstn if stn is None else stn
        result_prompt, result_negative_prompt = the_obj.process_prompt(prompt, negative_prompt)
        self.assertEqual(result_prompt, expected_prompt, f"Prompt should be '{expected_prompt}'")
        self.assertEqual(
            result_negative_prompt,
            expected_negative_prompt,
            f"Negative Prompt should be '{expected_negative_prompt}'",
        )

    def test_tag_default(self):
        self.process(
            "flowers<!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_start(self):
        self.process(
            "flowers<!!s!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_end(self):
        self.process(
            "flowers<!!e!red!>",
            "normal quality, worse quality",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tag_insertion_mid_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, <!!i0!!>, worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tag_insertion_mid_no_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality<!!i0!!>worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tag_insertion_start_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>, normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_insertion_start_no_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tag_insertion_end_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality, <!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tag_insertion_end_no_sep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality<!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_complex(self):
        self.process(
            "<!red!> (<!!s!pink!>), flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            "flowers",
            "red, (pink), normal quality, yellow, bad quality, green, worse quality, purple, blue",
        )

    def test_complex_no_cleanup(self):
        self.process(
            "<!red!> (<!!s!pink!>), flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            " (), flowers , ,  ",
            "red, (pink), normal quality, yellow, bad quality, green, worse quality, purple, blue",
            SendToNegative(self.__log, separator=", ", ignore_repeats=True, join_attention=True, cleanup=False),
        )

    def test_inside_attention1(self):
        self.process(
            "[<!neg1!>] this is a ((test<!!e!neg2!>) (test:2.0): 1.5 )",
            "normal quality",
            "this is a ((test) (test:2.0): 1.5 )",
            "[neg1], normal quality, (neg2:1.65)",
        )

    def test_inside_attention2(self):
        self.process(
            "(red<![square]!>:1.5)",
            "",
            "(red:1.5)",
            "([square]:1.5)",
        )

    def test_inside_alternation1(self):
        self.process(
            "this is a (([complex|simple<!neg1!>|regular] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex|simple|regular] test)(test:2.0):1.5)",
            "([|neg1|]:1.65), normal quality",
        )

    def test_inside_alternation2(self):
        self.process(
            "this is a (([complex<!neg1!>|simple<!neg2!>|regular<!neg3!>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_inside_alternation3(self):
        self.process(
            "this is a (([complex<!neg1!>[one|two<!neg12!>||three|four(<!neg14!>)]|simple<!neg2!>|regular<!neg3!>] test)(test:2.0):1.5)",
            "normal quality",
            "this is a (([complex[one|two||three|four]|simple|regular] test)(test:2.0):1.5)",
            "([neg1||]:1.65), ([[|neg12|||]||]:1.65), ([[||||(neg14)]||]:1.65), ([|neg2|]:1.65), ([||neg3]:1.65), normal quality",
        )

    def test_inside_scheduling(self):
        self.process(
            "this is [abc<!neg1!>:def<!!e!neg2!>: 5 ]",
            "normal quality",
            "this is [abc:def: 5 ]",
            "[neg1::5], normal quality, [neg2:5]",
        )

    def test_complex_features(self):
        self.process(
            "[<!neg5!>] this is: a (([complex|simple<!neg6!>|regular] test<!neg1!>)(test:2.0):1.5) \nBREAK with [abc<!neg4!>:def<!!p0!neg2(neg3:1.6)!>:5] <lora:xxx:1>",
            "normal quality, <!!i0!!>",
            "this is: a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK with [abc:def:5] <lora:xxx:1>",
            "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
        )


if __name__ == "__main__":
    unittest.main()
