if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))


# pylint: disable=import-error

from modules import scripts, shared, script_callbacks
from modules.processing import StableDiffusionProcessing
from modules.shared import opts
from ppp import PromptPostProcessor
from ppp_logging import PromptPostProcessorLogFactory


class PromptPostProcessorScript(scripts.Script):
    def __init__(self):
        if not hasattr(self, "callbacks_added"):
            lf = PromptPostProcessorLogFactory()
            self.__logppp = lf.log
            script_callbacks.on_ui_settings(self.__on_ui_settings)
            self.callbacks_added = True

    def title(self):
        return PromptPostProcessor.NAME

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):
        ppp = PromptPostProcessor(self.__logppp, opts=opts)
        for i in range(len(p.all_prompts)):  # pylint: disable=consider-using-enumerate
            p.all_prompts[i], p.all_negative_prompts[i] = ppp.process_prompt(
                p.all_prompts[i], p.all_negative_prompts[i]
            )
        # make it compatible with A1111 hires fix
        if (
            hasattr(p, "all_hr_prompts")
            and p.all_hr_prompts is not None
            and hasattr(p, "all_hr_negative_prompts")
            and p.all_hr_negative_prompts is not None
        ):
            for i in range(len(p.all_hr_prompts)):  # pylint: disable=consider-using-enumerate
                p.all_hr_prompts[i], p.all_hr_negative_prompts[i] = ppp.process_prompt(
                    p.all_hr_prompts[i], p.all_hr_negative_prompts[i]
                )

    def __on_ui_settings(self):
        section = ("prompt-post-processor", PromptPostProcessor.NAME)
        shared.opts.add_option(
            key="ppp_separator",
            info=shared.OptionInfo(
                PromptPostProcessor.DEFAULT_SEPARATOR,
                label="Separator used when adding to the negative prompt",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_stn_ignorerepeats",
            info=shared.OptionInfo(
                True,
                label="Ignore tags with repeated content",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_stn_joinattention",
            info=shared.OptionInfo(
                True,
                label="Join attention modifiers (weights) when possible",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cleanup",
            info=shared.OptionInfo(
                True,
                label="Try to clean-up the prompt after processing (removes extra spaces, empty attention, or the configured separator)",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_debug",
            info=shared.OptionInfo(
                False,
                label="Debug",
                section=section,
            ),
        )
