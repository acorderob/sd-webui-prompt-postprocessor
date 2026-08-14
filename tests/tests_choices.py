from ppp_classes import DEFAULT_SAMPLER, NEXT_SEED, RUN_MODE  # type: ignore
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
        self.process(
            InputTuple("the choices are: {@choice1|choice2|choice3}", ""),
            [
                OutputTuple("the choices are: choice1", ""),
                OutputTuple("the choices are: choice2", ""),
                OutputTuple("the choices are: choice3", ""),
                OutputTuple("the choices are: choice1", ""),  # cycles back
            ],
            ppp="nocup",
        )

    def test_ch_cyclical_multiple_constructs(self):  # two independent @ constructs cycle together
        self.process(
            InputTuple("{@a|b} {@c|d}", ""),
            [
                OutputTuple("a c", ""),
                OutputTuple("a d", ""),
                OutputTuple("b c", ""),
                OutputTuple("b d", ""),
                OutputTuple("a c", ""),  # cycles back
            ],
            ppp="nocup",
        )

    def test_ch_cyclical_resets_on_prompt_change(self):  # state resets when the prompt pair changes
        ppp_instance = self.init_ppp("nocup")
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
        self.process(
            InputTuple("{@a|b|c} {x|y}", ""),
            [
                OutputTuple("a y", ""),
                OutputTuple("b x", ""),
                OutputTuple("c x", ""),
                OutputTuple("a y", ""),  # @ cycles back
            ],
            ppp="nocup",
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

    def test_ch_choices_if_default(self):  # choices with if and a default
        self.process(
            InputTuple("the choice is: {if false::choice1|if _is_sd1::choice2|else::choice3}", ""),
            OutputTuple("the choice is: choice3", ""),
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
            ppp=self.init_ppp(None, cup_remove_extranetwork_tags=True),
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
            InputTuple("{choice1|choice2|choice3}, ${v:{option1|option2}}, {~a|b}", ""),
            [
                OutputTuple("choice1, option1, a", ""),
                OutputTuple("choice1, option2, b", ""),
                OutputTuple("choice2, option1, a", ""),
                OutputTuple("choice2, option2, b", ""),
                OutputTuple("choice3, option1, b", ""),
                OutputTuple("choice3, option2, a", "", {"v": "option2"}),
            ],
            ppp=self.init_ppp(
                None,
                run_mode=RUN_MODE.combinatorial,
                comb_random_fixed=False,  # allow different random choices across combinations
            ),
        )

    def test_ch_comb_random_consistent(self):  # ~ sampler picks one value shared across all combinations
        ppp_instance = self.init_ppp("nocup", run_mode=RUN_MODE.combinatorial)
        ppp_instance.process_prompts_group_start()
        result = ppp_instance.process_prompt("{~a|b|c} {x|y}", "", starting_seed=1)
        ppp_instance.process_prompts_group_end()
        self.assertEqual(len(result), 2, "Expected exactly 2 combinations ({x|y} expands to 2)")
        rnd_choices = {r_prompt.split()[0] for r_prompt, _, _ in result}
        self.assertEqual(
            len(rnd_choices),
            1,
            f"The ~ sampler must yield the same value across all combinations, got: {rnd_choices}",
        )

    # Multiple

    def test_ch_multiple(self):
        self.process(
            InputTuple("{choice1|choice2|choice3}, ${v:{option1|option2}}, {~a|b}", ""),
            [
                OutputTuple("choice2, option2, a", ""),
                OutputTuple("choice1, option1, b", ""),
                OutputTuple("choice1, option2, b", ""),
                OutputTuple("choice3, option1, b", ""),
                OutputTuple("choice1, option1, a", ""),
                OutputTuple("choice2, option1, a", "", {"v": "option1"}),
            ],
            ppp=self.init_ppp(
                None,
                run_mode=RUN_MODE.multiple,
                results_limit=6,
            ),
        )

    # Default sampler

    def test_ch_default_sampler_cyclical_single(self):
        self.process(
            InputTuple("{choice1|choice2|choice3}", ""),
            [
                OutputTuple("choice1", ""),
                OutputTuple("choice2", ""),
                OutputTuple("choice3", ""),
                OutputTuple("choice1", ""),
            ],
            ppp=self.init_ppp("nocup", default_sampler=DEFAULT_SAMPLER.cyclical),
        )

    def test_ch_default_sampler_cyclical_multiple(self):
        self.process(
            InputTuple("{choice1|choice2|choice3}", ""),
            [
                OutputTuple("choice1", ""),
                OutputTuple("choice2", ""),
                OutputTuple("choice3", ""),
                OutputTuple("choice1", ""),
            ],
            ppp=self.init_ppp(
                "nocup",
                default_sampler=DEFAULT_SAMPLER.cyclical,
                run_mode=RUN_MODE.multiple,
                results_limit=4,
            ),
        )

    # next_seed / _output_seed

    def test_ch_next_seed_input(self):  # input mode keeps the same seed for every result
        self.process(
            InputTuple("{@a|b|c}", ""),
            [
                OutputTuple("a", "", {"_output_seed": 1}),
                OutputTuple("b", "", {"_output_seed": 1}),
                OutputTuple("c", "", {"_output_seed": 1}),
            ],
            seed=1,
            ppp=self.init_ppp("nocup", run_mode=RUN_MODE.multiple, results_limit=3, next_seed=NEXT_SEED.input),
        )

    def test_ch_next_seed_increment(self):  # increment mode increases the seed by 1 for each result
        self.process(
            InputTuple("{@a|b|c}", ""),
            [
                OutputTuple("a", "", {"_output_seed": 1}),
                OutputTuple("b", "", {"_output_seed": 2}),
                OutputTuple("c", "", {"_output_seed": 3}),
            ],
            seed=1,
            ppp=self.init_ppp("nocup", run_mode=RUN_MODE.multiple, results_limit=3, next_seed=NEXT_SEED.increment),
        )

    def test_ch_next_seed_decrement(self):  # decrement mode decreases the seed by 1 for each result
        self.process(
            InputTuple("{@a|b|c}", ""),
            [
                OutputTuple("a", "", {"_output_seed": 3}),
                OutputTuple("b", "", {"_output_seed": 2}),
                OutputTuple("c", "", {"_output_seed": 1}),
            ],
            seed=3,
            ppp=self.init_ppp("nocup", run_mode=RUN_MODE.multiple, results_limit=3, next_seed=NEXT_SEED.decrement),
        )

    def test_ch_next_seed_randomize(self):  # randomize mode produces a distinct seed for every result
        ppp_instance = self.init_ppp("nocup", run_mode=RUN_MODE.multiple, results_limit=3, next_seed=NEXT_SEED.randomize)
        ppp_instance.process_prompts_group_start()
        results = ppp_instance.process_prompt("{@a|b|c}", "", starting_seed=1)
        ppp_instance.process_prompts_group_end()
        seeds = [r_vars.get("_output_seed") for _, _, r_vars in results]
        self.assertEqual(len(seeds), 3, f"Expected 3 results, got {len(seeds)}")
        self.assertEqual(len(set(seeds)), 3, f"Expected 3 distinct seeds, got: {seeds}")
