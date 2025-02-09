"""
@author: ACB
@title: Prompt Post Processor
@nickname: ACB PPP
@description: Node for processing prompts. Includes the following options: send to negative prompt, set variables, if/elif/else command for conditional content, wildcards and choices.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from .ppp_comfyui import PromptPostProcessorComfyUINode, PromptPostProcessorSelectVariableComfyUINode

NODE_CLASS_MAPPINGS = {
    "ACBPromptPostProcessor": PromptPostProcessorComfyUINode,
    "ACBPPPSelectVariable": PromptPostProcessorSelectVariableComfyUINode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ACBPromptPostProcessor": "ACB Prompt Post Processor",
    "ACBPPPSelectVariable": "ACB PPP Select Variable",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
