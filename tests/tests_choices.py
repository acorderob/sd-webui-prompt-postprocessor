from dataclasses import replace

from ppp import PromptPostProcessor  # type: ignore
from .base_tests import OutputTuple, InputTuple, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestChoices(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Choices tests

    def test_ch_choices(self):  # simple choices with weights
        self.process(
            InputTuple("the choices are: {3::choice1|2::choice2|choice3}", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_ch_cyclical(self):  # cyclical sampler cycles through all choices
        ppp_instance = self.init_obj("nocup")
        self.process(
            InputTuple("the choices are: {@choice1|choice2|choice3}", ""),
            [
                OutputTuple("the choices are: choice1", ""),
                OutputTuple("the choices are: choice2", ""),
                OutputTuple("the choices are: choice3", ""),
                OutputTuple("the choices are: choice1", ""),  # cycles back
            ],
            ppp=ppp_instance,
        )

    def test_ch_cyclical_multiple_constructs(self):  # two independent @ constructs cycle together
        ppp_instance = self.init_obj("nocup")
        self.process(
            InputTuple("{@a|b} {@c|d}", ""),
            [
                OutputTuple("a c", ""),
                OutputTuple("a d", ""),
                OutputTuple("b c", ""),
                OutputTuple("b d", ""),
                OutputTuple("a c", ""),  # cycles back
            ],
            ppp=ppp_instance,
        )

    def test_ch_cyclical_resets_on_prompt_change(self):  # state resets when the prompt pair changes
        ppp_instance = self.init_obj("nocup")
        # Advance the cycle to position 1 (choice2).
        self.process(
            InputTuple("the choices are: {@choice1|choice2|choice3}", ""),
            [
                OutputTuple("the choices are: choice1", ""),
                OutputTuple("the choices are: choice2", ""),
            ],
            ppp=ppp_instance,
        )
        # A different prompt must restart from position 0 (choice1).
        self.process(
            InputTuple("the choices are: {@choice1|choice2|choice3} different", ""),
            OutputTuple("the choices are: choice1 different", ""),
            ppp=ppp_instance,
        )

    def test_ch_cyclical_mixed_samplers(self):  # @ construct cycles while a ~ construct alongside is unaffected
        ppp_instance = self.init_obj("nocup")
        self.process(
            InputTuple("{@a|b|c} {x|y}", ""),
            [
                OutputTuple("a y", ""),
                OutputTuple("b x", ""),
                OutputTuple("c x", ""),
                OutputTuple("a y", ""),  # @ cycles back
            ],
            ppp=ppp_instance,
        )

    def test_ch_choices_withcomments(self):  # choices with comments and multiline
        self.process(
            InputTuple(
                "the choices are: {\n3::choice1 # this is option 1\n|2::choice2\n# this was option 2\n|choice3 # this is option 3\n}",
                "",
            ),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_ch_choices_multiple(self):  # choices with multiple selection
        self.process(
            InputTuple("the choices are: {~2$$, $$3::choice1|2:: choice2 |choice3}", ""),
            OutputTuple("the choices are:  choice2 , choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_if_multiple(self):  # choices with if and multiple selection
        self.process(
            InputTuple("the choices are: {2$$, $$3::choice1|2 if _is_sd1::choice2|choice3}", ""),
            OutputTuple("the choices are: choice1, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_set_if_multiple(self):  # choices with if user variable and multiple selection
        self.process(
            InputTuple("${var=test}the choices are: {2$$, $$3::choice1|2 if not var eq 'test'::choice2|choice3}", ""),
            OutputTuple("the choices are: choice1, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choices_set_if_nested(self):  # nested choices with if user variable and multiple selection
        self.process(
            InputTuple(
                "${var=test}the choices are: {2$$, $$3::choice1${var2=test2} {if var2 eq 'test2'::choice11|choice12}|2 if not var eq 'test'::choice2|choice3}",
                "",
            ),
            OutputTuple("the choices are: choice1 choice11, choice3", ""),
            ppp="nocup",
        )

    def test_ch_choicesinsidelora(self):  # simple choices inside a lora
        self.process(
            InputTuple("<lora:test1:1><lora:test__other__name:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            OutputTuple("<lora:test1:1><lora:test__other__name:1><lora:test2:0.7>", ""),
            ppp="nocup",
        )

    def test_ch_removelorawithchoices(self):
        self.process(
            InputTuple("<lora:test1:1><lora:test2:{0.2|0.5|0.7|1}>", ""),
            OutputTuple("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    cup_remove_extranetwork_tags=True,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_ch_cmd_includewildcard(self):
        self.process(
            InputTuple("{ch_one|ch_two|%0.5::include yaml/wildcard1}", ""),
            OutputTuple("ch_two", ""),
            ppp="nocup",
        )

    # Combinatorial

    def test_ch_combinatorial(self):
        self.process(
            InputTuple("{choice1|choice2|choice3}, ${v:{option1|option2}}", ""),
            [
                OutputTuple("choice1, option1", ""),
                OutputTuple("choice1, option2", ""),
                OutputTuple("choice2, option1", ""),
                OutputTuple("choice2, option2", ""),
                OutputTuple("choice3, option1", ""),
                OutputTuple("choice3, option2", "", {"v": "option2"}),
            ],
            combinatorial=True,
        )
