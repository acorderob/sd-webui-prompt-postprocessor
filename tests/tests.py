import unittest
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], '..'))

from sendtonegative import SendToNegative


class TestSendToNegative(unittest.TestCase):
    def setUp(self):
        self.defstn = SendToNegative(
            tagStart="<!",
            tagEnd="!>",
            tagParamStart="!",
            tagParamEnd="!",
            separator=", ",
            ignoreRepeats=True,
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
        result_prompt, result_negative_prompt = (self.defstn if stn is None else stn).processPrompts(
            prompt, negative_prompt
        )
        self.assertEqual(
            result_prompt, expected_prompt, f"Prompt should be '{expected_prompt}'"
        )
        self.assertEqual(
            result_negative_prompt,
            expected_negative_prompt,
            f"Negative Prompt should be '{expected_negative_prompt}'",
        )

    def test_tagDefault(self):
        self.process(
            "flowers<!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tagStart(self):
        self.process(
            "flowers<!!s!red!>",
            "normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tagEnd(self):
        self.process(
            "flowers<!!e!red!>",
            "normal quality, worse quality",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tagInsertion_midSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, <!!i0!!>, worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tagInsertion_midNoSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality<!!i0!!>worse quality",
            "flowers",
            "normal quality, red, worse quality",
        )

    def test_tagInsertion_startSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>, normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tagInsertion_startNoSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "<!!i0!!>normal quality, worse quality",
            "flowers",
            "red, normal quality, worse quality",
        )

    def test_tagInsertion_endSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality, <!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_tagInsertion_endNoSep(self):
        self.process(
            "flowers<!!p0!red!>",
            "normal quality, worse quality<!!i0!!>",
            "flowers",
            "normal quality, worse quality, red",
        )

    def test_complex(self):
        self.process(
            "<!red!> <!!s!pink!>, flowers, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            "flowers",
            "red, pink, normal quality, yellow, bad quality, green, worse quality, blue",
        )

    def test_complexNoCleanUp(self):
        self.process(
            "<!red!> <!!s!pink!>, flowers, <!!e!blue!>, <!!p0!yellow!> <!!p1!green!>",
            "normal quality, <!!i0!!>, bad quality<!!i1!!>, worse quality",
            " , flowers, ,  ",
            "red, pink, normal quality, yellow, bad quality, green, worse quality, blue",
            SendToNegative(
                tagStart="<!",
                tagEnd="!>",
                tagParamStart="!",
                tagParamEnd="!",
                separator=", ",
                ignoreRepeats=True,
                cleanup=False,
            ),
        )


if __name__ == "__main__":
    unittest.main()
