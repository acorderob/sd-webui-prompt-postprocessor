if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))

from sendtonegative import SendToNegative
import logging
from modules import scripts, shared, script_callbacks
from modules.processing import StableDiffusionProcessing
from modules.shared import opts


class SendToNegativeScript(scripts.Script):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if getattr(opts, "is_debug", False):
            self.logger.setLevel(logging.DEBUG)
        if not hasattr(self, "callbacks_added"):
            script_callbacks.on_ui_settings(_on_ui_settings)
            self.callbacks_added = True

    def title(self):
        return f"{SendToNegative.NAME} v{SendToNegative.VERSION}"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):
        stn = SendToNegative(opts=opts, logger=self.logger)
        for i in range(len(p.all_prompts)):
            p.all_prompts[i], p.all_negative_prompts[i] = stn.processPrompt(
                p.all_prompts[i], p.all_negative_prompts[i]
            )


def _on_ui_settings():
    section = ("send-to-negative", SendToNegative.NAME)
    shared.opts.add_option(
        key="stn_tagstart",
        info=shared.OptionInfo(
            SendToNegative.DEFAULT_tagStart,
            label="Tag start",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="stn_tagend",
        info=shared.OptionInfo(
            SendToNegative.DEFAULT_tagEnd,
            label="Tag end",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="stn_tagparamstart",
        info=shared.OptionInfo(
            SendToNegative.DEFAULT_tagParamStart,
            label="Tag parameter start",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="stn_tagparamend",
        info=shared.OptionInfo(
            SendToNegative.DEFAULT_tagParamEnd,
            label="Tag parameter end",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="stn_separator",
        info=shared.OptionInfo(
            SendToNegative.DEFAULT_separator,
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
        key="stn_cleanup",
        info=shared.OptionInfo(
            True,
            label="Try to clean-up the prompt after processing. Removes extra spaces or separators (the configured separator).",
            section=section,
        ),
    )
