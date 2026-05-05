from dataclasses import replace

from ppp import PromptPostProcessor
from ppp_classes import IFWILDCARDS_CHOICES
from .base_tests import OutputTuple, InputTuple, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestWildcards(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Wildcards tests

    def test_wc_ignore(self):  # wildcards with ignore option
        self.process(
            InputTuple("__bad_wildcard__", "{option1|option2}"),
            OutputTuple("__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    process_wildcards=False,
                    if_wildcards=IFWILDCARDS_CHOICES.ignore,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.process(
            InputTuple(
                "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
                "normal quality, <ppp:stn i0/> {option1|option2}",
            ),
            OutputTuple(
                "this is: a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]<lora:xxx:1>",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    process_wildcards=False,
                    if_wildcards=IFWILDCARDS_CHOICES.remove,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_warn(self):  # wildcards with warn option
        self.process(
            InputTuple("__bad_wildcard__", "{option1|option2}"),
            OutputTuple(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    process_wildcards=False,
                    if_wildcards=IFWILDCARDS_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_stop(self):  # wildcards with stop option
        self.process(
            InputTuple("__bad_wildcard__", "{option1|option2}"),
            OutputTuple(
                PromptPostProcessor.WILDCARD_STOP.format("__bad_wildcard__") + "__bad_wildcard__",
                "{option1|option2}",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    process_wildcards=False,
                    if_wildcards=IFWILDCARDS_CHOICES.stop,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_wcinvar_warn(self):  # wildcards in var with warn option
        self.process(
            InputTuple("${v=__bad_wildcard__}${v}", ""),
            OutputTuple(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    process_wildcards=False,
                    if_wildcards=IFWILDCARDS_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_invalid_name(self):
        self.process(
            InputTuple("the choices are: ___invalid__", ""),
            OutputTuple("the choices are: ___invalid__", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_wildcard1a_text(self):  # simple text wildcard
        self.process(
            InputTuple("the choices are: __text/wildcard1__", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_json(self):  # simple json wildcard
        self.process(
            InputTuple("the choices are: __json/wildcard1__", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_yaml(self):  # simple yaml wildcard
        self.process(
            InputTuple("the choices are: __yaml/wildcard1__", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_text(self):  # simple text wildcard with multiple choices
        self.process(
            InputTuple("the choices are: __2-$$text/wildcard1__", ""),
            OutputTuple("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_json(self):  # simple json wildcard with multiple choices
        self.process(
            InputTuple("the choices are: __2-$$json/wildcard1__", ""),
            OutputTuple("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_yaml(self):  # simple yaml wildcard with multiple choices
        self.process(
            InputTuple("the choices are: __2-$$yaml/wildcard1__", ""),
            OutputTuple("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_text(self):  # simple text wildcard with default options
        self.process(
            InputTuple("the choices are: __text/wildcard2__", ""),
            OutputTuple("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_json(self):  # simple json wildcard with default options
        self.process(
            InputTuple("the choices are: __json/wildcard2__", ""),
            OutputTuple("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_yaml(self):  # simple yaml wildcard with default options
        self.process(
            InputTuple("the choices are: __yaml/wildcard2__", ""),
            OutputTuple("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_test2_yaml(self):  # simple yaml wildcard
        self.process(
            InputTuple("the choice is: __testwc/test2__", ""),
            OutputTuple("the choice is: 2", ""),
            ppp="nocup",
        )

    def test_wc_test3_yaml(self):  # simple yaml wildcard
        self.process(
            InputTuple("the choice is: __testwc/test3__", ""),
            OutputTuple("the choice is: one choice", ""),
            ppp="nocup",
        )

    def test_wc_test3_yaml_2(self):  # simple yaml wildcard build from variable
        self.process(
            InputTuple("${v=3}the choice is: __testwc/test${v}__", ""),
            OutputTuple("the choice is: one choice", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_index(self):  # wildcard with positional index filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2'2'__", ""),
            OutputTuple("the choice is: choice3-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_index_range(self):  # wildcard with positional index range filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2'2-3'__", ""),
            OutputTuple("the choice is: choice3-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label(self):  # wildcard with label filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2'label1'__", ""),
            OutputTuple("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label2(self):  # wildcard with label filter in multiple choices
        self.process(
            InputTuple("the choice is: __yaml/wildcard2'label2'__", ""),
            OutputTuple("the choice is: choice1-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label3(self):  # wildcard with multiple label filter
        self.process(
            InputTuple("the choice is: __4$$-$$yaml/wildcard2'label1,label2'__", ""),
            OutputTuple("the choice is: choice1-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_indexlabel(self):  # wildcard with mixed index and label filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2'2,label2'__", ""),
            OutputTuple("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound(self):  # wildcard with compound filter
        self.process(
            InputTuple("the choice is: __4$$-$$yaml/wildcard2'label1+label3'__", ""),
            OutputTuple("the choice is: choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound_var(self):  # wildcard with compound filter in a variable
        self.process(
            InputTuple("${v[]=*('label1','label3')}the choice is: __4$$-$$yaml/wildcard2'${v[&'+']}'__", ""),
            OutputTuple("the choice is: choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound2(self):  # wildcard with inherited compound filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2bis'#label1+label3'__", ""),
            OutputTuple("the choice is: choice3bis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound3(self):  # wildcard with doubly inherited compound filter
        self.process(
            InputTuple("the choice is: __yaml/wildcard2bisbis'#label1+label3'__", ""),
            OutputTuple("the choice is: choice3bisbis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound4(self):  # wildcard with doubly inherited compound filter with variable
        self.process(
            InputTuple("${v=label1}the choice is: __yaml/wildcard2bisbis'#${v}+label3'__", ""),
            OutputTuple("the choice is: choice3bisbis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_default_filter(self):  # wildcard with default filter
        self.process(
            InputTuple(
                "<ppp:setwcdeffilter 'yaml/wildcard2' 'label1+label3' />the choice is: __yaml/wildcard2__, <ppp:setwcdeffilter 'yaml/wildcard2' />__yaml/wildcard2__",
                "",
            ),
            OutputTuple("the choice is: choice3-choice3, choice3-choice1- choice2 ", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_default_filter2(self):  # wildcard with default filter with variable
        self.process(
            InputTuple(
                "${v=label1}<ppp:setwcdeffilter 'yaml/wildcard2' '${v}+label3' />the choice is: __yaml/wildcard2__, <ppp:setwcdeffilter 'yaml/wildcard2' />__yaml/wildcard2__",
                "",
            ),
            OutputTuple("the choice is: choice3-choice3, choice3-choice1- choice2 ", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_text(self):  # nested text wildcard with repeating multiple choices
        self.process(
            InputTuple("the choices are: __r3$$-$$text/wildcard3__", ""),
            OutputTuple("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_json(self):  # nested json wildcard with repeating multiple choices
        self.process(
            InputTuple("the choices are: __r3$$-$$json/wildcard3__", ""),
            OutputTuple("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_yaml(self):  # nested yaml wildcard with repeating multiple choices
        self.process(
            InputTuple("the choices are: __r3$$-$$yaml/wildcard3__", ""),
            OutputTuple("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_optional(self):  # empty wildcard with no error
        self.process(
            InputTuple("the choices are: __yaml/empty_wildcard__", ""),
            OutputTuple("the choices are: ", ""),
            ppp="nocup",
        )

    def test_wc_wildcard4_yaml(self):  # simple yaml wildcard with one option
        self.process(
            InputTuple("the choices are: __yaml/wildcard4__", ""),
            OutputTuple("the choices are: inline text", ""),
            ppp="nocup",
        )

    def test_wc_wildcard6_yaml(self):  # simple yaml wildcard with object formatted choices
        self.process(
            InputTuple("the choices are: __yaml/wildcard6__", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_choice_wildcard_mix(self):  # choices with wildcard mix
        self.process(
            InputTuple("the choices are: {__~2$$yaml/wildcard2__|choice0}", ""),
            [
                OutputTuple("the choices are: choice0", ""),
                OutputTuple("the choices are: choice1, choice3", ""),
                OutputTuple("the choices are: choice1, choice3", ""),
            ],
            ppp="nocup",
        )

    def test_wc_wildcard_globbing(self):  # wildcard with globbing
        self.process(
            InputTuple("the choices are: __yaml/wildcard[12]__, __yaml/wildcard?__", ""),
            OutputTuple("the choices are: choice3-choice2, <lora:test2:1>- choice2 -choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcardwithvar(self):  # wildcard with inline variable
        self.process(
            InputTuple("the choices are: __yaml/wildcard5(var=test)__, __yaml/wildcard5__", ""),
            OutputTuple("the choices are: inline test, inline default", ""),
            ppp="nocup",
        )

    def test_wc_wildcardPS_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.process(
            InputTuple("the choices are: __yaml/wildcardPS__", ""),
            OutputTuple("the choices are: prefix1-choice2/choice3-suffix", ""),
            ppp="nocup",
        )

    def test_wc_wildcardPS2_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.process(
            InputTuple("the choices are: [__yaml/wildcardPS2__]", ""),
            OutputTuple("the choices are: (prefix2-choice2-suffix:1.35)", ""),
        )

    def test_wc_wildcardContainer_yaml(self):  # yaml wildcard with object formatted choices and options and container
        self.process(
            InputTuple("the choices are: [__yaml/wildcardContainer__]", ""),
            OutputTuple("the choices are: (prefix1-choice2/choice3-suffix:1.35)", ""),
        )

    def test_wc_wildcardAt_yaml(self):  # yaml wildcard with attention in choices
        self.process(
            InputTuple("the choices are: [__yaml/wildcardAt__]", ""),
            OutputTuple("the choices are: (choice2:1.35)", ""),
        )

    def test_wc_merge_attention_bracket(self):  # bracket attention from wildcard merges with outer attention
        self.process(
            InputTuple("(__yaml/wildcardAtBracket__:1.5)", ""),
            OutputTuple("(the content:1.35)", ""),
        )

    def test_wc_no_merge_attention_alternation(self):  # alternation from wildcard is not merged as attention
        self.process(
            InputTuple("(__yaml/wildcardAlt__:1.5)", ""),
            OutputTuple("([cat|dog]:1.5)", ""),
        )

    def test_wc_no_merge_attention_scheduling(self):  # scheduling from wildcard is not merged as attention
        self.process(
            InputTuple("(__yaml/wildcardSched__:1.5)", ""),
            OutputTuple("([cat:dog:0.5]:1.5)", ""),
        )

    def test_wc_anonymouswildcard_yaml(self):  # yaml anonymous wildcard
        self.process(
            InputTuple("the choices are: __yaml/anonwildcards__", ""),
            OutputTuple("the choices are: six", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_input(self):  # simple yaml wildcard input
        self.process(
            InputTuple("the choices are: __yaml_input/wildcardI__", ""),
            OutputTuple("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_circular(self):  # wildcard circular reference
        self.process(
            InputTuple("the choices are: __yaml/circular1__", ""),
            OutputTuple("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_including(self):  # wildcard including another wildcard
        self.process(
            InputTuple("the choices are: __yaml/including__", ""),
            OutputTuple("the choices are: choice4", ""),
            ppp="nocup",
        )

    def test_wc_circular_including(self):  # wildcard including another wildcard in a circular reference
        self.process(
            InputTuple("the choices are: __yaml/including1__", ""),
            OutputTuple("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_dynamicwildcard(self):  # wildcard built from variables
        self.process(
            InputTuple(
                "the choices are: ${x={1|2|3}}${w=yaml/wildcard${x}}__yaml/wildcard${x}__ __${w}__ __<ppp:echo w/>__",
                "",
            ),
            OutputTuple("the choices are: choice1-choice3-choice1 choice3- choice2 - choice2  choice3", ""),
            ppp="nocup",
        )

    # Combinatorial

    def test_wc_combinatorial_1(self):  # combinatorial wildcard with variable
        self.process(
            InputTuple("the choices are: __2$$yaml/wildcard2__, ${v:{option1|option2}}", ""),
            [  # 12 combinations
                OutputTuple("the choices are: choice1, choice2, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice1, choice2, option2", "", {"v": "option2"}),
                OutputTuple("the choices are: choice1, choice3, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice1, choice3, option2", "", {"v": "option2"}),
                OutputTuple("the choices are: choice2, choice1, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice2, choice1, option2", "", {"v": "option2"}),
                OutputTuple("the choices are: choice2, choice3, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice2, choice3, option2", "", {"v": "option2"}),
                OutputTuple("the choices are: choice3, choice1, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice3, choice1, option2", "", {"v": "option2"}),
                OutputTuple("the choices are: choice3, choice2, option1", "", {"v": "option1"}),
                OutputTuple("the choices are: choice3, choice2, option2", "", {"v": "option2"}),
            ],
            combinatorial=True,
        )

    def test_wc_combinatorial_2(self):  # combinatorial wildcard
        self.process(
            InputTuple("__yaml/wildcard2__", ""),
            [  # 36 combinations
                # groups of 3
                ## same choice repeated 3 times
                OutputTuple("choice1-choice1-choice1", ""),
                OutputTuple(" choice2 - choice2 - choice2 ", ""),
                OutputTuple("choice3-choice3-choice3", ""),
                ## one choice repeated 2 times in all positions
                OutputTuple("choice1-choice1- choice2 ", ""),
                OutputTuple("choice1-choice1-choice3", ""),
                OutputTuple(" choice2 - choice2 -choice1", ""),
                OutputTuple(" choice2 - choice2 -choice3", ""),
                OutputTuple("choice3-choice3-choice1", ""),
                OutputTuple("choice3-choice3- choice2 ", ""),
                OutputTuple(" choice2 -choice1-choice1", ""),
                OutputTuple("choice3-choice1-choice1", ""),
                OutputTuple("choice1- choice2 - choice2 ", ""),
                OutputTuple("choice3- choice2 - choice2 ", ""),
                OutputTuple("choice1-choice3-choice3", ""),
                OutputTuple(" choice2 -choice3-choice3", ""),
                OutputTuple("choice1- choice2 -choice1", ""),
                OutputTuple("choice1-choice3-choice1", ""),
                OutputTuple(" choice2 -choice1- choice2 ", ""),
                OutputTuple(" choice2 -choice3- choice2 ", ""),
                OutputTuple("choice3-choice1-choice3", ""),
                OutputTuple("choice3- choice2 -choice3", ""),
                ## choices 1, 2, 3 in all positions
                OutputTuple("choice1- choice2 -choice3", ""),
                OutputTuple("choice1-choice3- choice2 ", ""),
                OutputTuple(" choice2 -choice1-choice3", ""),
                OutputTuple(" choice2 -choice3-choice1", ""),
                OutputTuple("choice3-choice1- choice2 ", ""),
                OutputTuple("choice3- choice2 -choice1", ""),
                # groups of 2
                ## same choice repeated 2 times
                OutputTuple("choice1-choice1", ""),
                OutputTuple(" choice2 - choice2 ", ""),
                OutputTuple("choice3-choice3", ""),
                ## choices 1 and 2 in all positions
                OutputTuple("choice1- choice2 ", ""),
                OutputTuple(" choice2 -choice1", ""),
                ## choices 2 and 3 in all positions
                OutputTuple(" choice2 -choice3", ""),
                OutputTuple("choice3- choice2 ", ""),
                ## choices 1 and 3 in all positions
                OutputTuple("choice1-choice3", ""),
                OutputTuple("choice3-choice1", ""),
            ],
            ppp="nocup",
            combinatorial=True,
        )

    def test_wc_combinatorial_3(self):  # combinatorial wildcard (keep choice order)
        self.process(
            InputTuple("__2-3$$-$$yaml/wildcard2__", ""),
            [  # 4 combinations
                # groups of 3
                ## choices 1, 2, 3
                OutputTuple("choice1- choice2 -choice3", ""),
                # groups of 2
                ## choices 1 and 2
                OutputTuple("choice1- choice2 ", ""),
                ## choices 2 and 3
                OutputTuple(" choice2 -choice3", ""),
                ## choices 1 and 3
                OutputTuple("choice1-choice3", ""),
            ],
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    keep_choices_order=True,
                    cup_do_cleanup=False,
                    do_combinatorial=True,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_combinatorial_4(self):  # combinatorial wildcard (don't keep choice order)
        self.process(
            InputTuple("__2-3$$-$$yaml/wildcard2__", ""),
            [  # 12 combinations
                # groups of 3
                ## choices 1, 2, 3 in all positions
                OutputTuple("choice1- choice2 -choice3", ""),
                OutputTuple("choice1-choice3- choice2 ", ""),
                OutputTuple(" choice2 -choice1-choice3", ""),
                OutputTuple(" choice2 -choice3-choice1", ""),
                OutputTuple("choice3-choice1- choice2 ", ""),
                OutputTuple("choice3- choice2 -choice1", ""),
                # groups of 2
                ## choices 1 and 2 in all positions
                OutputTuple("choice1- choice2 ", ""),
                OutputTuple(" choice2 -choice1", ""),
                ## choices 2 and 3 in all positions
                OutputTuple(" choice2 -choice3", ""),
                OutputTuple("choice3- choice2 ", ""),
                ## choices 1 and 3 in all positions
                OutputTuple("choice1-choice3", ""),
                OutputTuple("choice3-choice1", ""),
            ],
            ppp="nocup",
            combinatorial=True,
        )

    def test_wc_combinatorial_5(self):  # combinatorial nested wildcards and multiselection enmappings
        self.process(
            InputTuple("{__yaml/wildcard1__|__yaml/wildcard3__|<ppp:ext $lora loraany/>}", ""),
            [  # 11 combinations
                # first wildcard
                OutputTuple("choice1", ""),
                OutputTuple("choice2", ""),
                OutputTuple("choice3", ""),
                # second wildcard (nested)
                OutputTuple("choice1, choice2 ", ""),
                OutputTuple(" choice2 ,choice1", ""),
                OutputTuple("choice1,choice3", ""),
                OutputTuple("choice3,choice1", ""),
                OutputTuple(" choice2 ,choice3", ""),
                OutputTuple("choice3, choice2 ", ""),
                # ppp:ext
                OutputTuple("<lora:loraany1:0.8> trigger1, trigger2, ", ""),
                OutputTuple("<lora:loraany2:1> trigger3, trigger4, ", ""),
            ],
            ppp="nocup",
            combinatorial=True,
        )
