"""
@author: ACB
@title: Prompt Post Processor
@nickname: ACB PPP
@description: Node for processing prompts. Includes the following options: send to negative prompt, set variables, if/elif/else command for conditional content, wildcards and choices.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from .ppp_comfyui import (
    PromptPostProcessorComfyUINode,
    PromptPostProcessorWildcardOptionsComfyUINode,
    PromptPostProcessorENMappingOptionsComfyUINode,
    PromptPostProcessorSTNOptionsComfyUINode,
    PromptPostProcessorCleanupOptionsComfyUINode,
    PromptPostProcessorSelectVariableComfyUINode,
    PromptPostProcessorWildcardConcatComfyUINode,
)

NODE_CLASS_MAPPINGS = {
    "ACBPromptPostProcessor": PromptPostProcessorComfyUINode,
    "ACBPPPWildcardOptions": PromptPostProcessorWildcardOptionsComfyUINode,
    "ACBPPPENMappingOptions": PromptPostProcessorENMappingOptionsComfyUINode,
    "ACBPPPSendToNegativeOptions": PromptPostProcessorSTNOptionsComfyUINode,
    "ACBPPPCleanupOptions": PromptPostProcessorCleanupOptionsComfyUINode,
    "ACBPPPSelectVariable": PromptPostProcessorSelectVariableComfyUINode,
    "ACBPPPWildcardConcat": PromptPostProcessorWildcardConcatComfyUINode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ACBPromptPostProcessor": "ACB Prompt Post Processor",
    "ACBPPPWildcardOptions": "ACB PPP Wildcard Options",
    "ACBPPPENMappingOptions": "ACB PPP ExtraNetwork Mapping Options",
    "ACBPPPSendToNegativeOptions": "ACB PPP Send-To-Negative Options",
    "ACBPPPCleanupOptions": "ACB PPP Cleanup Options",
    "ACBPPPSelectVariable": "ACB PPP Select Variable",
    "ACBPPPWildcardConcat": "ACB PPP Wildcard Concat",
}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
