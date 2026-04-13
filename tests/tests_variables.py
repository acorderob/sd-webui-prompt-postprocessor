from dataclasses import replace

from ppp import PromptPostProcessor
from ppp_classes import ONWARNING_CHOICES  # pylint: disable=import-error
from .base_tests import PromptPair, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestVariables(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Empty variable test

    def test_empty_variable(self):
        self.process(
            PromptPair(
                "${v1=}<ppp:set v2><ppp:/set>${v3:}",
                "",
            ),
            PromptPair("", ""),
            variables={"v1": "", "v2": "", "v3": ""},
        )

    # Echoed variables tests

    def test_echoed_variable(self):
        self.process(
            PromptPair(
                "${v1=test1}<ppp:set v2>test2<ppp:/set>${v3:test3}${v3:test4}",
                "",
            ),
            # v3 is echoed withs two defaults, the output prompt has both but the variable value is the last default
            PromptPair("test3test4", ""),
            variables={"v1": "test1", "v2": "test2", "v3": "test4"},
        )

    def test_unknown_echoed_variable(self):
        self.process(
            PromptPair(
                "${v1}",
                "",
            ),
            # v3 is echoed withs two defaults, the output prompt has both but the variable value is the last default
            PromptPair("", ""),
            variables={"v1": ""},
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    on_warning=ONWARNING_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    # Variable in extranetworks

    def test_variable_in_extranetwork(self):
        self.process(
            PromptPair(
                "${f=filename}${w=0.5}<lora:${f}:${w}>",
                "",
            ),
            PromptPair("<lora:filename:0.5>", ""),
        )

    # Variable nesting tests

    def test_var_nested_1(self):  # variable default nested in variable set
        self.process(
            PromptPair(
                "${v1=test ${v2:OK}}${v1}",
                "",
            ),
            PromptPair("test OK", ""),
            variables={"v1": "test OK", "v2": "OK"},
        )

    def test_var_nested_2(self):  # variable set nested in variable default
        self.process(
            PromptPair(
                "${v1:test ${v2=OK}${v2}}",
                "",
            ),
            PromptPair("test OK", ""),
            variables={"v1": "test OK", "v2": "OK"},
        )

    def test_var_nested_3(self):  # variable default nested in variable default
        self.process(
            PromptPair(
                "${v1:test ${v2:OK}}",
                "",
            ),
            PromptPair("test OK", ""),
            variables={"v1": "test OK", "v2": "OK"},
        )

    # Variable-vs-variable comparison tests

    def test_cmd_if_var_vs_var_eq(self):  # var eq var: both set to same value, if-branch taken
        self.process(
            PromptPair(
                "<ppp:set v1>hello<ppp:/set><ppp:set v2>hello<ppp:/set><ppp:if v1 eq v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_ne(self):  # var ne var: different values, ne condition true
        self.process(
            PromptPair(
                "<ppp:set v1>apple<ppp:/set><ppp:set v2>orange<ppp:/set><ppp:if v1 ne v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_contains(self):  # var contains var: var1 contains var2's value
        self.process(
            PromptPair(
                "<ppp:set v1>hello world<ppp:/set><ppp:set v2>hello<ppp:/set><ppp:if v1 contains v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_not_contains(self):  # var not contains var: var1 does not contain var2's value
        self.process(
            PromptPair(
                "<ppp:set v1>hello world<ppp:/set><ppp:set v2>goodbye<ppp:/set><ppp:if v1 not contains v2>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    def test_cmd_if_var_vs_var_lt(self):  # var lt var: var1 less than var2
        self.process(
            PromptPair(
                "<ppp:set lesser>1<ppp:/set><ppp:set greater>2<ppp:/set><ppp:if lesser lt greater>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("YES", ""),
        )

    # NaN/undefined variable integer comparison tests

    def test_cmd_if_undefined_var_int_compare_warn(self):  # undefined var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:if undefined_var gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    on_warning=ONWARNING_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_if_undefined_var_int_compare_stop(self):  # undefined var integer compare with on_warning=stop
        self.process(
            PromptPair(
                "<ppp:if undefined_var gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_nonnumeric_var_int_compare_warn(self):  # non-numeric var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    on_warning=ONWARNING_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_if_nonnumeric_var_int_compare_stop(self):  # non-numeric var integer compare with on_warning=stop
        self.process(
            PromptPair(
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_empty_var_int_compare(self):  # empty string var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar><ppp:/set><ppp:if myvar gt 0>YES<ppp:else>NO<ppp:/if>",
                "",
            ),
            PromptPair("NO", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    on_warning=ONWARNING_CHOICES.warn,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )
