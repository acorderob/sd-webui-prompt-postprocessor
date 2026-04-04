import unittest

from .base_tests import PromptPair, TestPromptPostProcessorBase


class TestSendToNegative(TestPromptPostProcessorBase):

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


if __name__ == "__main__":
    unittest.main()
