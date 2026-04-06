from .base_tests import PromptPair, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestPerformance(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

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
