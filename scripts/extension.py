if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))


# pylint: disable=import-error

from modules import scripts, shared, script_callbacks
from modules.processing import StableDiffusionProcessing
from modules.shared import opts
from sendtonegative import SendToNegative


class SendToNegativeScript(scripts.Script):
    def __init__(self):
        if not hasattr(self, "callbacks_added"):
            script_callbacks.on_ui_settings(self.__on_ui_settings)
            self.callbacks_added = True

    def title(self):
        return f"{SendToNegative.NAME} v{SendToNegative.VERSION}"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):
        stn = SendToNegative(opts=opts)
        for i in range(len(p.all_prompts)):  # pylint: disable=consider-using-enumerate
            p.all_prompts[i], p.all_negative_prompts[i] = stn.process_prompt(
                p.all_prompts[i], p.all_negative_prompts[i]
            )

    def __on_ui_settings(self):
        section = ("send-to-negative", SendToNegative.NAME)
        shared.opts.add_option(
            key="stn_separator",
            info=shared.OptionInfo(
                SendToNegative.DEFAULT_SEPARATOR,
                label="Separator used when adding to the negative prompt",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="stn_ignorerepeats",
            info=shared.OptionInfo(
                True,
                label="Ignore tags with repeated content",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="stn_joinattention",
            info=shared.OptionInfo(
                True,
                label="Join attention modifiers (weights) when possible",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="stn_cleanup",
            info=shared.OptionInfo(
                True,
                label="Try to clean-up the prompt after processing (removes extra spaces or the configured separator)",
                section=section,
            ),
        )
