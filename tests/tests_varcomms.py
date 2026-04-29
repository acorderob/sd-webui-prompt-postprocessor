from dataclasses import replace

from ppp import PromptPostProcessor  # pylint: disable=import-error
from ppp_classes import ONWARNING_CHOICES  # pylint: disable=import-error
from .base_tests import PromptPair, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestVarCommands(TestPromptPostProcessorBase):

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

    # Array variable tests

    def test_array_variable_1(self):  # array variable set with += and test of index value and full array with and without default separator
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]+=val2}${v1[]+=val3}${v1[1]:defval},${v1[]:defval2},${v1[&'.']:defval3}",
                "",
            ),
            PromptPair("val2,val1, val2, val3,val1.val2.val3", ""),
            variables={"v1[]": "val1, val2, val3", "v1[1]": "val2", "v1[&'.']": "val1.val2.val3"},
        )

    def test_array_variable_2(self):  # override of array variable value, test of default value when array variable is empty, test of default value when array variable is not set
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]=val2}${v1[]:defval},${v2[]:defval2},${v2[1]:defval3},${v3[]=}${v3[]:defval4}",
                "",
            ),
            PromptPair("val2,defval2,defval3", ""),
            variables={"v1[]": "val2", "v2[]": "defval2", "v2[1]": "defval3", "v3[]": ""},
        )

    def test_array_variable_3(self):  # access array index by variable, set array variable to expanded array variable and add expanded array
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]+=val2}${v2=1}${v1[v2]:defval1}${v3[]=${v1[]}}${v3[]+=${v1[]}}, ${v3[&'.']}",
                "",
            ),
            PromptPair("val2, val1, val2.val1, val2", ""),
            variables={"v1[]": "val1, val2", "v2": "1", "v1[v2]": "val2", "v3[]": "val1, val2, val1, val2", "v3[&'.']": "val1, val2.val1, val2"},
        )

    def test_array_variable_4(self):  # test list in array
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]+=val2}${v1[]+=val3}<ppp:if ('val1','val2') in v1[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
            variables={"v1[]": "val1, val2, val3"},
        )

    def test_array_variable_5(self):  # test empty array
        self.process(
            PromptPair(
                "${v1[]=}<ppp:if v1[]>OK<ppp:else>not OK<ppp:/if>,<ppp:if not v1[0]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK,OK", ""),
            variables={"v1[]": ""},
        )

    def test_array_variable_6(self):  # array variable set and addition with expanded values from array variables
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]+=val2}${v2[]=val3}${v3[]=*v1[]}${v3[]+=*v2[]}",
                "",
            ),
            PromptPair("", ""),
            variables={"v1[]": "val1, val2", "v2[]": "val3", "v3[]": "val1, val2, val3"},
        )

    def test_array_variable_7(self):  # array variable set and addition with expanded values from wildcards
        self.process(
            PromptPair(
                "${v1[]=*__yaml/wildcard1__}${v1[]+=*__yaml/wildcard2__}${v1[2]:defval}",
                "",
            ),
            PromptPair("choice3", ""),
            variables={"v1[]": "choice2, choice1, choice3, choice1"},
        )

    def test_array_variable_8(self):  # array variable set and addition with expanded values from lists
        self.process(
            PromptPair(
                "${v1[]=*()}${v1[]+=*('one','two')}${v2=three}${v1[]+=*(v2,'four')}${v1[2]:defval}",
                "",
            ),
            PromptPair("three", ""),
            variables={"v1[]": "one, two, three, four", "v2": "three"},
        )

    def test_array_variable_9(self):  # array variable length
        self.process(
            PromptPair(
                "${v1[]=val1}${v1[]+=val2}${v1[]+=val3}${v1[#]:defval}, <ppp:if v1[#] eq 3>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("3, OK", ""),
            variables={"v1[]": "val1, val2, val3", "v1[#]": "3"},
        )


    # Operator tests

    ## R vs R

    def test_operator_ReqR(self):
        self.process(
            PromptPair(
                "${r1=hello}${r2=hello}<ppp:if r1 eq r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RnoteqR(self):  # test for the not before the operator
        self.process(
            PromptPair(
                "${r1=hello}${r2=bye}<ppp:if r1 not eq r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RneR(self):
        self.process(
            PromptPair(
                "${r1=hello}${r2=bye}<ppp:if r1 ne r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RltR(self):
        self.process(
            PromptPair(
                "${r1=1}${r2=2}<ppp:if r1 lt r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RgtR(self):
        self.process(
            PromptPair(
                "${r1=2}${r2=1}<ppp:if r1 gt r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RleR(self):
        self.process(
            PromptPair(
                "${r1=1}${r2=1}<ppp:if r1 le r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RgeR(self):
        self.process(
            PromptPair(
                "${r1=1}${r2=1}<ppp:if r1 ge r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RinR(self):
        self.process(
            PromptPair(
                "${r1=hello}${r2=hello world}<ppp:if r1 in r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RcontainsR(self):
        self.process(
            PromptPair(
                "${r1=hello world}${r2=hello}<ppp:if r1 contains r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    ## A vs A

    def test_operator_AeqA(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${a2[]=*('hello','world')}<ppp:if a1[] eq a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AneA_1(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello')}${a2[]=*('bye')}<ppp:if a1[] ne a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AneA_2(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${a2[]=*('hello')}<ppp:if a1[] ne a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AneA_3(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${a2[]=*('world','hello')}<ppp:if a1[] ne a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AltA_1(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,2,3)}${a2[]=*(2,3,4)}<ppp:if a1[] lt a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AltA_2(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,2)}${a2[]=*(2,3,4)}<ppp:if a1[] lt a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
        )

    def test_operator_AgtA(self):
        self.process(
            PromptPair(
                "${a1[]=*(2,3,4)}${a2[]=*(1,2,3)}<ppp:if a1[] gt a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AleA(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,2)}${a2[]=*(1,3)}<ppp:if a1[] le a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AgeA(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,3)}${a2[]=*(1,2)}<ppp:if a1[] ge a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AinA(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello')}${a2[]=*('hello', 'world')}<ppp:if a1[] in a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AcontainsA(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${a2[]=*('hello')}<ppp:if a1[] contains a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    ## A vs R

    def test_operator_AeqR(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${r2=hello}<ppp:if a1[] eq r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_AneR(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello')}${r2=bye}<ppp:if a1[] ne r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
            ppp="nostrict",
        )

    def test_operator_AltR(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,2,3)}${r2=2}<ppp:if a1[] lt r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_AgtR(self):
        self.process(
            PromptPair(
                "${a1[]=*(2,3,4)}${r2=2}<ppp:if a1[] gt r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_AleR(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,2)}${r2=2}<ppp:if a1[] le r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
            ppp="nostrict",
        )

    def test_operator_AgeR(self):
        self.process(
            PromptPair(
                "${a1[]=*(1,3)}${r2=2}<ppp:if a1[] ge r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_AinR(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello', 'world')}${r2=hello world)}<ppp:if a1[] in r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_AcontainsR(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}${r2=hello}<ppp:if a1[] contains r2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    ## R vs A

    def test_operator_ReqA(self):
        self.process(
            PromptPair(
                "${r1=hello}${a2[]=*('hello','world')}<ppp:if r1 eq a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_RneA(self):
        self.process(
            PromptPair(
                "${r1=bye}${a2[]=*('hello')}<ppp:if r1 ne a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
            ppp="nostrict",
        )

    def test_operator_RltA(self):
        self.process(
            PromptPair(
                "${r1=2}${a2[]=*(1,2,3)}<ppp:if r1 lt a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_RgtA(self):
        self.process(
            PromptPair(
                "${r1=2}${a2[]=*(2,3,4)}<ppp:if r1 gt a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_RleA(self):
        self.process(
            PromptPair(
                "${r1=2}${a2[]=*(1,2)}<ppp:if r1 le a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_RgeA(self):
        self.process(
            PromptPair(
                "${r1=2}${a2[]=*(1,3)}<ppp:if r1 ge a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            ppp="nostrict",
        )

    def test_operator_RinA(self):
        self.process(
            PromptPair(
                "${r1=hello}${a2[]=*('hello', 'world')}<ppp:if r1 in a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_RcontainsA(self):
        self.process(
            PromptPair(
                "${r1=hello world}${a2[]=*('hello','world')}<ppp:if r1 contains a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    ## R vs V

    def test_operator_ReqV_str(self):
        self.process(
            PromptPair(
                "${r1=hello}<ppp:if r1 eq 'hello'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_ReqV_str_fail(self):
        self.process(
            PromptPair(
                "${r1=hello}<ppp:if r1 eq 42>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            interrupted=True,
        )

    def test_operator_ReqV_num(self):
        self.process(
            PromptPair(
                "${r1=42}<ppp:if r1 eq 42>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_ReqV_num_fail(self):
        self.process(
            PromptPair(
                "${r1=42}<ppp:if r1 eq '42'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            interrupted=True,
        )

    def test_operator_ReqV_bool(self):
        self.process(
            PromptPair(
                "${r1=true}<ppp:if r1 eq true>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_operator_ReqV_bool_fail(self):
        self.process(
            PromptPair(
                "${r1=true}<ppp:if r1 eq 'true'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
            interrupted=True,
        )

    # List operands

    def test_listoperand_AinL(self):
        self.process(
            PromptPair(
                "${a1[]=*('hello','world')}<ppp:if a1[] in ('hello','world')>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    def test_listoperand_LinA(self):
        self.process(
            PromptPair(
                "${a2[]=*('hello','world')}<ppp:if ('hello','world') in a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    # Indexed operands

    def test_indexedoperand_RinA(self):
        self.process(
            PromptPair(
                "${a2[]=*('hello','world')}<ppp:if a2[0] in a2[]>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("OK", ""),
        )

    # NaN/undefined variable integer comparison tests

    def test_cmd_if_undefined_var_int_compare_warn(self):  # undefined var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:if undefined_var gt 0>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
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
                "<ppp:if undefined_var gt 0>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_nonnumeric_var_int_compare_warn(self):  # non-numeric var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
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
                "<ppp:set myvar>abc<ppp:/set><ppp:if myvar gt 0>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("", ""),
            interrupted=True,
        )

    def test_cmd_if_empty_var_int_compare(self):  # empty string var integer compare with on_warning=warn
        self.process(
            PromptPair(
                "<ppp:set myvar><ppp:/set><ppp:if myvar gt 0>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("not OK", ""),
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

    # Command tests

    def test_cmd_stn_complex_features(self):  # complex stn command with AND, BREAK and other features
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

    def test_cmd_if_complex_features(self):  # complex if command
        self.process(
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2.0):1.5) \nBREAK, BREAK <ppp:if _is_sd1>with [abc<ppp:stn>neg4<ppp:/stn>:def:5]<ppp:/if>:0.5 AND <ppp:if _is_sd1>loratrigger <lora:xxx:1><ppp:elif _is_sdxl>hypernettrigger <hypernet:yyy><ppp:else>nothing<ppp:/if>:0.3",
                "normal quality",
            ),
            PromptPair(
                "this \\(is\\): a (([complex|simple|regular] test)(test:2):1.5)\nBREAK :0.5 AND hypernettrigger <hypernet:yyy>:0.3",
                "normal quality",
            ),
        )

    def test_cmd_if_nested(self):  # nested if command
        self.process(
            PromptPair(
                "this is <ppp:if _sd eq 'sd1'>SD1<ppp:else><ppp:if _is_pony>PONY<ppp:else>SD2<ppp:/if><ppp:/if><ppp:if _is_sdxl_no_pony>NOPONY<ppp:/if><ppp:if _is_pure_sdxl>NOPONY<ppp:/if>",
                "",
            ),
            PromptPair("this is PONY", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_set_if(self):  # set and if commands
        self.process(
            PromptPair("<ppp:set v>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_empty(self):  # set to empty
        self.process(
            PromptPair("<ppp:set v><ppp:/set>${v2=}this test is <ppp:if v or v2>not OK<ppp:else>OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_eval_if(self):  # set and if commands
        self.process(
            PromptPair("<ppp:set v evaluate>value<ppp:/set>this test is <ppp:if v>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_echo_nested(self):  # nested set, if and echo commands
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:if v1 gt 0><ppp:set v2>OK<ppp:/set><ppp:/if><ppp:if v2 eq 'OK'><ppp:echo v2/><ppp:else>not OK<ppp:/if> <ppp:echo v2>NOK<ppp:/echo> <ppp:echo v3>OK<ppp:/echo>",
                "",
            ),
            PromptPair("OK OK OK", ""),
        )

    def test_cmd_set_if_complex_conditions_1(self):  # complex conditions (or)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if v1 or v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_2(self):  # complex conditions (and)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>true<ppp:/set>this test is <ppp:if v1 and v2>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_3(self):  # complex conditions (not)
        self.process(
            PromptPair("<ppp:set v1>false<ppp:/set>this test is <ppp:if not v1>OK<ppp:else>not OK<ppp:/if>", ""),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_4(self):  # complex conditions (not, precedence)
        self.process(
            PromptPair(
                "<ppp:set v1>true<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not (v1 and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_5(self):  # complex conditions (not, precedence, comparison)
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>false<ppp:/set>this test is <ppp:if not(v1 eq 1 and v2)>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_6(self):  # complex conditions
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq 1 and v2 eq 2 and v3 eq 3>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if_complex_conditions_7(self):  # complex conditions
        self.process(
            PromptPair(
                "<ppp:set v1>1<ppp:/set><ppp:set v2>2<ppp:/set><ppp:set v3>3<ppp:/set>this test is <ppp:if v1 eq 1 and v2 not eq 2 or v3 eq 3>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_if2(self):  # set and more complex if commands
        self.process(
            PromptPair(
                "First: <ppp:set v>value1<ppp:/set>this test is <ppp:if v in ('value1','value2')>OK<ppp:elif v in ('value3')>OK2<ppp:else>not OK<ppp:/if>\nSecond: <ppp:set v2>value3<ppp:/set>this test is <ppp:if not v2 in ('value1','value2')>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("First: this test is OK\nSecond: this test is OK", ""),
        )

    def test_cmd_set_add_if(self):  # set, add and if commands
        self.process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v add>2<ppp:/set>this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_add_DP_if(self):  # set, add (DP format) and if commands
        self.process(
            PromptPair(
                "${v=value}${v+=2}this test is <ppp:if v eq 'value2'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_immediateeval(self):  # set (DP format) with mixed evaluation
        self.process(
            PromptPair(
                "${var=!__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var2:default}, ${var3=__yaml/wildcard1__}${var3}, ${var3}",
                "",
            ),
            PromptPair("the choices are: choice2, choice2, default, choice3, choice1", ""),
            ppp="nocup",
        )

    def test_cmd_set_mixeval(self):  # set and add (DP format) with mixed evaluation
        self.process(
            PromptPair(
                "${var=__yaml/wildcard1__}the choices are: ${var}, ${var}, ${var+=, __yaml/wildcard2__}${var}, ${var}, ${var+=!, __yaml/wildcard3__}${var}, ${var}",
                "",
            ),
            PromptPair(
                "the choices are: choice2, choice3, choice1, choice1- choice2 -choice3, choice2,  choice2 -choice1-choice3, choice2, choice3-choice1- choice2 , choice1, choice2 , choice2, choice3-choice1- choice2 , choice1, choice2 ",
                "",
            ),
            ppp="nocup",
        )

    def test_cmd_set_ifundefined_if(self):  # set, ifundefined and if commands
        self.process(
            PromptPair(
                "<ppp:set v ifundefined>value<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_if_2(self):  # set, ifundefined and if commands
        self.process(
            PromptPair(
                "<ppp:set v>value<ppp:/set><ppp:set v ifundefined>value2<ppp:/set>this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if(self):  # set, ifundefined (DP format) and if commands
        self.process(
            PromptPair(
                "${v?=value}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_set_ifundefined_DP_if_2(self):  # set, ifundefined (DP format) and if commands
        self.process(
            PromptPair(
                "${v=!value}${v?=!value2}this test is <ppp:if v eq 'value'>OK<ppp:else>not OK<ppp:/if>",
                "",
            ),
            PromptPair("this test is OK", ""),
        )

    def test_cmd_echo_sysvar(self):
        self.process(
            PromptPair(
                "${_model:defval}",
                "",
            ),
            PromptPair("sdxl", ""),
        )

    def test_cmd_ext(self):  # ext
        self.process(
            PromptPair(
                "<ppp:ext lora lora1name if not _is_pony>trigger1<ppp:/ext><ppp:ext lora 'lora2 name' -0.8 if not _is_pony>trigger2<ppp:/ext><ppp:ext lora lora3__name '0.5:0.8' if not _is_pony><ppp:ext lora lora4name>trigger4<ppp:/ext><ppp:ext lora \"lora5 (name)\" 1/>trigger5",
                "",
            ),
            PromptPair(
                "<lora:lora1name:1>trigger1,<lora:lora2 name:-0.8>trigger2,<lora:lora3__name:0.5:0.8><lora:lora4name:1>trigger4,<lora:lora5 (name):1>trigger5",
                "",
            ),
        )

    def test_cmd_ext_map_notrigger(self):  # ext mapping, no trigger
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1/><ppp:ext $lora lora1>",
                "",
            ),
            PromptPair("triggergeneric1, triggergeneric2, two, triggergeneric1, triggergeneric2, two", ""),
        )

    def test_cmd_ext_map1(self):  # ext mapping, no lora
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("inlinetrigger, triggergeneric1, triggergeneric2, two", ""),
        )

    def test_cmd_ext_map2(self):  # ext mapping, lora with weight
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.8>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map3(self):  # ext mapping, lora with weight adjusted
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1 0.5>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.4>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map4(self):  # ext mapping, lora with parameters
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1 '0.6:0.8'>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:lorapony:0.6:0.8>inlinetrigger, triggerpony1, triggerpony2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ponymodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cmd_ext_map5(self):  # ext mapping, lora with no parameters
        self.process(
            PromptPair(
                "<ppp:ext $lora lora1>inlinetrigger<ppp:/ext>",
                "",
            ),
            PromptPair("<lora:loraillustrious:0.9:0.8>inlinetrigger, triggerillustrious1, triggerillustrious2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/ilxlmodel.safetensors",
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )
