from dataclasses import replace

from ppp import PromptPostProcessor  # pylint: disable=import-error
from .base_tests import PromptPair, TestPromptPostProcessorBase


if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestCleanup(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Cleanup tests

    def test_cl_simple(self):  # simple cleanup
        self.process(
            PromptPair("  this is a ((test ), , ,  (), ,   [] ( , test ,:2.0):1.5), (red:1.5)  ", "  normal quality  "),
            PromptPair("this is a ((test), (test,:2):1.5), (red:1.5)", "normal quality"),
        )

    def test_cl_complex(self):  # complex cleanup
        self.process(
            PromptPair(
                "  this is BREAKABLE a ((test)), ,AND AND(() [] <lora:test> ANDERSON (test:2.0):1.5) :o BREAK \n BREAK (red:1.5)  ",
                "  [:hands, feet, :0.15]normal quality  ",
            ),
            PromptPair(
                "this is BREAKABLE a (test:1.21) AND(<lora:test> ANDERSON (test:2):1.5) :o BREAK (red:1.5)",
                "[:hands, feet, :0.15]normal quality",
            ),
        )

    def test_cl_removenetworktags(self):  # remove network tags
        self.process(
            PromptPair("this is a <lora:test:1> test__yaml/wildcard7__", ""),
            PromptPair("this is a test", ""),
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

    def test_cl_dontremoveseparatorsoneol(self):  # don't remove separators on eol
        self.process(
            PromptPair("this is a test,\nsecond line", ""),
            PromptPair("this is a test,\nsecond line", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    cup_extra_separators2=False,
                    cup_extra_separators_include_eol=False,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cl_separatorswitheol(self):  # don't remove eols with the separators
        self.process(
            PromptPair(
                """{      (d:0.9) ,, (l:1.1)  | (l:1.1)         (d:0.9),,, }
                        (l:1.1)  
                        (d:0.9)""",
                "",
            ),
            PromptPair(
                """ (l:1.1)         (d:0.9), 
                        (l:1.1)  
                        (d:0.9)""",
                "",
            ),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                self.def_env_info,
                replace(
                    self.defopts,
                    cup_empty_constructs=False,
                    cup_extra_separators=True,
                    cup_extra_separators2=False,
                    cup_extra_separators_include_eol=False,
                    cup_extra_spaces=False,
                    cup_breaks=False,
                    cup_breaks_eol=False,
                    cup_ands=False,
                    cup_ands_eol=False,
                    cup_extranetwork_tags=False,
                    cup_merge_attention=False,
                ),
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_cl_mergeattention(self):  # merge attention
        self.process(
            PromptPair(
                "this is (a test:0.9) of (attention (merging:1.2)) where ((this)) ((is joined:1.2)) and ([this too]:1.3)",
                "",
            ),
            PromptPair(
                "this is [a test] of (attention (merging:1.2)) where (this:1.21) (is joined:1.32) and (this too:1.17)",
                "",
            ),
        )

    def test_cl_not_mergeattention(self):  # not merge attention
        self.process(
            PromptPair(
                "this is (a test:0.9) of not (attention (merging:1.2)) where ((this)) ((is not joined:1.2)) and neither is ([this]:1.3)",
                "",
            ),
            PromptPair(
                "this is (a test:0.9) of not (attention (merging:1.2)) where ((this)) ((is not joined:1.2)) and neither is ([this]:1.3)",
                "",
            ),
            ppp="nocup",
        )
