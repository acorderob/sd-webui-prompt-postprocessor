import unittest
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))

from sendtonegative import SendToNegative  # pylint: disable=import-error


class TestSendToNegative(unittest.TestCase):
    def setUp(self):
        self.defstn = SendToNegative(
            tag_start="<!",
            tag_end="!>",
            tag_param_start="!",
            tag_param_end="!",
            separator=", ",
            ignore_repeats=True,
            cleanup=True,
        )

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
            "<!red!> <!!s!pink!>, flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            "flowers",
            "red, pink, normal quality, yellow, bad quality, green, worse quality, purple, blue",
        )

    def test_complex_no_cleanup(self):
        self.process(
            "<!red!> <!!s!pink!>, flowers <!!e!purple!>, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            " , flowers , ,  ",
            "red, pink, normal quality, yellow, bad quality, green, worse quality, purple, blue",
            SendToNegative(
                tag_start="<!",
                tag_end="!>",
                tag_param_start="!",
                tag_param_end="!",
                separator=", ",
                ignore_repeats=True,
                cleanup=False,
            ),
        )


if __name__ == "__main__":
    unittest.main()
