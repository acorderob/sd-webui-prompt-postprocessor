from dataclasses import replace

from ppp import PromptPostProcessor
from ppp_classes import ONWARNING_CHOICES  # type: ignore
from .base_tests import OutputTuple, PromptPair, TestPromptPostProcessorBase

if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")


class TestModelVariants(TestPromptPostProcessorBase):

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp(enable_file_logging=False)

    # Model variants tests

    def test_variants(self):
        self.process(
            PromptPair(
                "<ppp:if _is_test1>test1<ppp:/if><ppp:if _is_test2>test2<ppp:/if><ppp:if _is_test3>test3<ppp:/if><ppp:if _is_test4>test4<ppp:/if>",
                "",
            ),
            OutputTuple("test1test2", ""),
            ppp=PromptPostProcessor(
                self.ppp_logger,
                {
                    **self.def_env_info,
                    "model_filename": "./webui/models/Stable-diffusion/testmodel.safetensors",
                    "ppp_config": {
                        "models": {
                            "sd1": {
                                "detect": {"tests": {"class": ["SD15", "SD15_instructpix2pix"]}},
                                "variants": {
                                    "test3": {"find_in_filename": "testmodel"},
                                    "sdxl": {"find_in_filename": "testmodel"},
                                },
                            },
                            "sdxl": {
                                "detect": {
                                    "tests": {
                                        "class": [
                                            "SDXL",
                                            "SDXLRefiner",
                                            "SDXL_instructpix2pix",
                                            "Segmind_Vega",
                                            "KOALA_700M",
                                            "KOALA_1B",
                                        ]
                                    }
                                },
                                "variants": {
                                    "test1": {"find_in_filename": "testmodel"},
                                    "test2": {"find_in_filename": "testmodel"},
                                },
                            },
                            "something": {
                                "detect": {"tests": {"class": ["something"]}},
                                "variants": {
                                    "test4": {"find_in_filename": "testmodel"},
                                },
                            },
                        }
                    },
                },
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
