from ppp import PromptPostProcessor  # pylint: disable=import-error
from .base_tests import PromptPair, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestHosts(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Hosts tests

    def test_host_attention_parentheses(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5) [(test4)]",
                "",
            ),
            PromptPair("(test1:0.9) (test2) (test3:1.5) (test4:0.99)", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "parentheses"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_disable(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("test1 test2 test3", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "disable"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_remove(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_attention_error(self):
        self.process(
            PromptPair(
                "[test1] (test2) (test3:1.5)",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"attention": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_scheduling_before(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("test1", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "before"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_after(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "after"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_first(self):
        self.process(
            PromptPair(
                "[test1::0.5] [:test2:0.5] [test3:test4:0.5]",
                "",
            ),
            PromptPair("test1 test3", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "first"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_remove(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_scheduling_error(self):
        self.process(
            PromptPair(
                "[test1:test2:0.5]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"scheduling": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_alternation_first(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("test1", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "first"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_alternation_remove(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_alternation_error(self):
        self.process(
            PromptPair(
                "[test1|test2|test3]",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"alternation": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_and_eol(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("test1\ntest2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "eol"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_and_comma(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("test1, test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "comma"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_and_remove(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("test1 test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_and_error(self):
        self.process(
            PromptPair(
                "test1 AND test2:2",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"and": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )

    def test_host_break_eol(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("test1\ntest2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "eol"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_break_comma(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("test1, test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "comma"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_break_remove(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("test1 test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "remove"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
        )

    def test_host_break_error(self):
        self.process(
            PromptPair(
                "test1 BREAK test2",
                "",
            ),
            PromptPair("", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "ppp_config": {"hosts": {"tests": {"break": "error"}}},
                },
                self.defopts,
                self.grammar_content,
                self.interrupt,
                self.wildcards_obj,
                self.extranetwork_maps_obj,
            ),
            interrupted=True,
        )
