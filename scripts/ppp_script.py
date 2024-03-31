if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))


from modules import scripts, shared, script_callbacks
from modules.processing import StableDiffusionProcessing
from modules.shared import opts
import gradio as gr
from ppp import PromptPostProcessor
from ppp_logging import PromptPostProcessorLogFactory


class PromptPostProcessorScript(scripts.Script):
    """
    This class represents a script for prompt post-processing.
    It is responsible for processing prompts and applying various settings and cleanup operations.

    Attributes:
        callbacks_added (bool): Flag indicating whether the script callbacks have been added.

    Methods:
        __init__(): Initializes the PromptPostProcessorScript object.
        title(): Returns the title of the script.
        show(is_img2img): Determines whether the script should be shown based on the input type.
        process(p, *args, **kwargs): Processes the prompts and applies post-processing operations.
        __on_ui_settings(): Callback function for UI settings.
    """

    def __init__(self):
        """
        Initializes the PromptPostProcessor object.

        This method adds callbacks for UI settings and initializes the logger.

        Parameters:
            None

        Returns:
            None
        """
        if not hasattr(self, "ppp_callbacks_added"):
            lf = PromptPostProcessorLogFactory()
            self.ppp_logger = lf.log
            self.ppp_debug = getattr(opts, "ppp_gen_debug", False) if opts is not None else False
            script_callbacks.on_ui_settings(self.__on_ui_settings)
            self.ppp_callbacks_added = True

    def title(self):
        """
        Returns the title of the script.

        Returns:
            str: The title of the script.
        """
        return PromptPostProcessor.NAME

    def show(self, is_img2img):
        """
        Determines whether the script should be shown based on the kind of processing.

        Args:
            is_img2img (bool): Flag indicating whether the processing is image-to-image.

        Returns:
            scripts.Visibility: The visibility setting for the script.
        """
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Processes the prompts and applies post-processing operations.

        Args:
            p (StableDiffusionProcessing): The StableDiffusionProcessing object containing the prompts.

        Returns:
            None
        """
        is_i2i = getattr(p, "init_images", [None])[0] is not None
        self.ppp_debug = getattr(opts, "ppp_gen_debug", False) if opts is not None else False
        if self.ppp_debug:
            self.ppp_logger.info(f"Post-processing prompts ({'i2i' if is_i2i else 't2i'} mode)")
        ppp = PromptPostProcessor(self, p, shared.state, opts, is_i2i)
        # processes regular prompts
        if (
            hasattr(p, "all_prompts")
            and p.all_prompts is not None
            and hasattr(p, "all_negative_prompts")
            and p.all_negative_prompts is not None
        ):
            for i, (prompt, negative_prompt) in enumerate(zip(p.all_prompts, p.all_negative_prompts)):
                p.all_prompts[i], p.all_negative_prompts[i] = ppp.process_prompt(prompt, negative_prompt)
        # make it compatible with A1111 hires fix
        if (
            hasattr(p, "all_hr_prompts")
            and p.all_hr_prompts is not None
            and hasattr(p, "all_hr_negative_prompts")
            and p.all_hr_negative_prompts is not None
        ):
            for i, (hr_prompt, hr_negative_prompt) in enumerate(zip(p.all_hr_prompts, p.all_hr_negative_prompts)):
                p.all_hr_prompts[i], p.all_hr_negative_prompts[i] = ppp.process_prompt(hr_prompt, hr_negative_prompt)

    def ppp_interrupt(self):
        """
        Interrupts the generation.

        Returns:
            None
        """
        shared.state.interrupted = True

    def __on_ui_settings(self):
        """
        Callback function for UI settings.

        Returns:
            None
        """
        # general settings
        section = ("prompt-post-processor", PromptPostProcessor.NAME)
        shared.opts.add_option(
            key="ppp_gen_sep", info=shared.OptionInfo("<h2>General settings</h2>", "", gr.HTML, section=section)
        )
        shared.opts.add_option(
            key="ppp_gen_debug",
            info=shared.OptionInfo(
                False,
                label="Debug",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_gen_ifwildcards",
            info=shared.OptionInfo(
                default=PromptPostProcessor.IFWILDCARDS_CHOICES["ignore"],
                label="What to do with remaining wildcards?",
                component=gr.Radio,
                component_args={"choices": PromptPostProcessor.IFWILDCARDS_CHOICES.values()},
                section=section,
            ),
        )

        # content removal settings
        shared.opts.add_option(
            key="ppp_rem_sep", info=shared.OptionInfo("<br/><h2>Content removal settings</h2>", "", gr.HTML, section=section)
        )
        shared.opts.add_option(
            key="ppp_rem_removeextranetworktags",
            info=shared.OptionInfo(
                False,
                label="Remove extra network tags",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_rem_if", info=shared.OptionInfo("<p style=\"font-style:italic\">* Parsing of the 'if' commands cannot be disabled</p>", "", gr.HTML, section=section)
        )

        # send to negative settings
        shared.opts.add_option(
            key="ppp_stn_sep",
            info=shared.OptionInfo("<br/><h2>Send to Negative settings</h2>", "", gr.HTML, section=section),
        )
        shared.opts.add_option(
            key="ppp_stn_doi2i",
            info=shared.OptionInfo(
                False,
                label="Apply in img2img (this includes any pass that contains an initial image, like refiner, hires fix, adetailer)",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_stn_separator",
            info=shared.OptionInfo(
                PromptPostProcessor.DEFAULT_STN_SEPARATOR,
                label="Separator used when adding to the negative prompt",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_stn_ignorerepeats",
            info=shared.OptionInfo(
                True,
                label="Ignore repeated content",
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
        # clean-up settings
        shared.opts.add_option(
            key="ppp_cup_sep", info=shared.OptionInfo("<br/><h2>Clean-up settings</h2>", "", gr.HTML, section=section)
        )
        shared.opts.add_option(
            key="ppp_cup_doi2i",
            info=shared.OptionInfo(
                False,
                label="Apply in img2img (this includes any pass that contains an initial image, like refiner, hires fix, adetailer)",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_emptyconstructs",
            info=shared.OptionInfo(
                True,
                label="Remove empty constructs (attention, alternation, scheduling)",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_extraseparators",
            info=shared.OptionInfo(
                True,
                label="Remove extra separators",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_extraseparators2",
            info=shared.OptionInfo(
                True,
                label="Remove additional extra separators",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_breaks",
            info=shared.OptionInfo(
                True,
                label="Clean up around BREAKs",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_breaks_eol",
            info=shared.OptionInfo(
                False,
                label="Use EOL instead of Space before BREAKs",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_ands",
            info=shared.OptionInfo(
                True,
                label="Clean up around ANDs",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_ands_eol",
            info=shared.OptionInfo(
                False,
                label="Use EOL instead of Space before ANDs",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_extranetworktags",
            info=shared.OptionInfo(
                False,
                label="Clean up around extra network tags",
                section=section,
            ),
        )
        shared.opts.add_option(
            key="ppp_cup_extraspaces",
            info=shared.OptionInfo(
                True,
                label="Remove extra spaces",
                section=section,
            ),
        )
