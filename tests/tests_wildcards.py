import unittest

from ppp import PromptPostProcessor
from .base_tests import PromptPair, TestPromptPostProcessorBase


class TestWildcards(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Wildcards tests

    def test_wc_ignore(self):  # wildcards with ignore option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_remove(self):  # wildcards with remove option
        self.process(
            PromptPair(
                "[<ppp:stn>neg5<ppp:/stn>] this is: __bad_wildcard__ a (([complex|simple<ppp:stn>neg6<ppp:/stn>|regular] test<ppp:stn>neg1<ppp:/stn>)(test:2.0):1.5) \nBREAK, BREAK with [abc<ppp:stn>neg4<ppp:/stn>:def<ppp:stn p0>neg2(neg3:1.6)<ppp:/stn>:5] <lora:xxx:1>",
                "normal quality, <ppp:stn i0/> {option1|option2}",
            ),
            PromptPair(
                "this is: a (([complex|simple|regular] test)(test:2):1.5)\nBREAK with [abc:def:5]<lora:xxx:1>",
                "[neg5], ([|neg6|]:1.65), (neg1:1.65), [neg4::5], normal quality, [neg2(neg3:1.6):5]",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.remove.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_warn(self):  # wildcards with warn option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", "{option1|option2}"),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_stop(self):  # wildcards with stop option
        self.process(
            PromptPair("__bad_wildcard__", "{option1|option2}"),
            PromptPair(
                PromptPostProcessor.WILDCARD_STOP.format("__bad_wildcard__") + "__bad_wildcard__",
                "{option1|option2}",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_wcinvar_warn(self):  # wildcards in var with warn option
        self.process(
            PromptPair("${v=__bad_wildcard__}${v}", ""),
            PromptPair(PromptPostProcessor.WILDCARD_WARNING + "__bad_wildcard__", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.interrupt,
                self.def_env_info,
                {
                    **self.defopts,
                    "process_wildcards": False,
                    "if_wildcards": PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value,
                },
                self.grammar_content,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_wc_invalid_name(self):
        self.process(
            PromptPair("the choices are: ___invalid__", ""),
            PromptPair("the choices are: ___invalid__", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_text(self):  # simple text wildcard
        self.process(
            PromptPair("the choices are: __text/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_json(self):  # simple json wildcard
        self.process(
            PromptPair("the choices are: __json/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1a_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choices are: __yaml/wildcard1__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_text(self):  # simple text wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$text/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_json(self):  # simple json wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$json/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard1b_yaml(self):  # simple yaml wildcard with multiple choices
        self.process(
            PromptPair("the choices are: __2-$$yaml/wildcard1__", ""),
            PromptPair("the choices are: choice3, choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_text(self):  # simple text wildcard with default options
        self.process(
            PromptPair("the choices are: __text/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_json(self):  # simple json wildcard with default options
        self.process(
            PromptPair("the choices are: __json/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard2_yaml(self):  # simple yaml wildcard with default options
        self.process(
            PromptPair("the choices are: __yaml/wildcard2__", ""),
            PromptPair("the choices are: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_test2_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test2__", ""),
            PromptPair("the choice is: 2", ""),
            ppp="nocup",
        )

    def test_wc_test3_yaml(self):  # simple yaml wildcard
        self.process(
            PromptPair("the choice is: __testwc/test3__", ""),
            PromptPair("the choice is: one choice", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_index(self):  # wildcard with positional index filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2'__", ""),
            PromptPair("the choice is: choice3-choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label(self):  # wildcard with label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label2(self):  # wildcard with label filter in multiple choices
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label2'__", ""),
            PromptPair("the choice is: choice1-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_label3(self):  # wildcard with multiple label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_indexlabel(self):  # wildcard with mixed index and label filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'2,label2'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound(self):  # wildcard with compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2'label1+label3'__", ""),
            PromptPair("the choice is: choice3-choice1", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound2(self):  # wildcard with inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bis'#label1+label3'__", ""),
            PromptPair("the choice is: choice3bis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound3(self):  # wildcard with doubly inherited compound filter
        self.process(
            PromptPair("the choice is: __yaml/wildcard2bisbis'#label1+label3'__", ""),
            PromptPair("the choice is: choice1bisbis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_filter_compound4(self):  # wildcard with doubly inherited compound filter with variable
        self.process(
            PromptPair("${v=label1}the choice is: __yaml/wildcard2bisbis'#${v}+label3'__", ""),
            PromptPair("the choice is: choice1bisbis", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_default_filter(self):  # wildcard with default filter
        self.process(
            PromptPair(
                "<ppp:setwcdeffilter 'yaml/wildcard2' 'label1+label3' />the choice is: __yaml/wildcard2__, <ppp:setwcdeffilter 'yaml/wildcard2' />__yaml/wildcard2__",
                "",
            ),
            PromptPair("the choice is: choice3-choice1, choice3-choice1- choice2 ", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_default_filter2(self):  # wildcard with default filter with variable
        self.process(
            PromptPair(
                "${v=label1}<ppp:setwcdeffilter 'yaml/wildcard2' '${v}+label3' />the choice is: __yaml/wildcard2__, <ppp:setwcdeffilter 'yaml/wildcard2' />__yaml/wildcard2__",
                "",
            ),
            PromptPair("the choice is: choice3-choice1, choice3-choice1- choice2 ", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_text(self):  # nested text wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$text/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_json(self):  # nested json wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$json/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_nested_wildcard_yaml(self):  # nested yaml wildcard with repeating multiple choices
        self.process(
            PromptPair("the choices are: __r3$$-$$yaml/wildcard3__", ""),
            PromptPair("the choices are: choice3,choice1- choice2 ,choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_optional(self):  # empty wildcard with no error
        self.process(
            PromptPair("the choices are: __yaml/empty_wildcard__", ""),
            PromptPair("the choices are: ", ""),
            ppp="nocup",
        )

    def test_wc_wildcard4_yaml(self):  # simple yaml wildcard with one option
        self.process(
            PromptPair("the choices are: __yaml/wildcard4__", ""),
            PromptPair("the choices are: inline text", ""),
            ppp="nocup",
        )

    def test_wc_wildcard6_yaml(self):  # simple yaml wildcard with object formatted choices
        self.process(
            PromptPair("the choices are: __yaml/wildcard6__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_choice_wildcard_mix(self):  # choices with wildcard mix
        self.process(
            PromptPair("the choices are: {__~2$$yaml/wildcard2__|choice0}", ""),
            [
                PromptPair("the choices are: choice0", ""),
                PromptPair("the choices are: choice1, choice3", ""),
                PromptPair("the choices are: choice1, choice3", ""),
            ],
            ppp="nocup",
        )

    def test_wc_unsupportedsampler(self):  # unsupported sampler
        self.process(
            PromptPair("the choices are: __@yaml/wildcard2__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_wildcard_globbing(self):  # wildcard with globbing
        self.process(
            PromptPair("the choices are: __yaml/wildcard[12]__, __yaml/wildcard?__", ""),
            PromptPair("the choices are: choice3-choice2, <lora:test2:1>- choice2 -choice3", ""),
            ppp="nocup",
        )

    def test_wc_wildcardwithvar(self):  # wildcard with inline variable
        self.process(
            PromptPair("the choices are: __yaml/wildcard5(var=test)__, __yaml/wildcard5__", ""),
            PromptPair("the choices are: inline test, inline default", ""),
            ppp="nocup",
        )

    def test_wc_wildcardPS_yaml(self):  # yaml wildcard with object formatted choices and options and prefix and suffix
        self.process(
            PromptPair("the choices are: __yaml/wildcardPS__", ""),
            PromptPair("the choices are: prefix-choice2/choice3-suffix", ""),
            ppp="nocup",
        )

    def test_wc_anonymouswildcard_yaml(self):  # yaml anonymous wildcard
        self.process(
            PromptPair("the choices are: __yaml/anonwildcards__", ""),
            PromptPair("the choices are: six", ""),
            ppp="nocup",
        )

    def test_wc_wildcard_input(self):  # simple yaml wildcard input
        self.process(
            PromptPair("the choices are: __yaml_input/wildcardI__", ""),
            PromptPair("the choices are: choice2", ""),
            ppp="nocup",
        )

    def test_wc_circular(self):  # wildcard circular reference
        self.process(
            PromptPair("the choices are: __yaml/circular1__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_including(self):  # wildcard including another wildcard
        self.process(
            PromptPair("the choices are: __yaml/including__", ""),
            PromptPair("the choices are: choice4", ""),
            ppp="nocup",
        )

    def test_wc_circular_including(self):  # wildcard including another wildcard in a circular reference
        self.process(
            PromptPair("the choices are: __yaml/including1__", ""),
            PromptPair("", ""),
            ppp="nocup",
            interrupted=True,
        )

    def test_wc_dynamicwildcard(self):  # wildcard built from variables
        self.process(
            PromptPair(
                "the choices are: ${x={1|2|3}}${w=yaml/wildcard${x}}__yaml/wildcard${x}__ __${w}__ __<ppp:echo w/>__",
                "",
            ),
            PromptPair("the choices are: choice1-choice3-choice1 choice3- choice2 - choice2  choice3", ""),
            ppp="nocup",
        )


if __name__ == "__main__":
    unittest.main()
