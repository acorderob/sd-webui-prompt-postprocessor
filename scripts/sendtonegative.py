import logging
from modules.processing import StableDiffusionProcessing
import modules.scripts as scripts
import re

VERSION = '0.1'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Script(scripts.Script):
    def __init__(self):
        pass

    def title(self):
        return f"SendToNegative v{VERSION}"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):
        try:
            find = r"(((?<!\\)\([^():]+:)-(\d+(?:\.\d+)?(?<!\\)\)))" # format (xxxx:-nnn) TODO : support [] ? accumulate recursive weights?
            regex = re.compile(find, re.S)
            for i in range(len(p.all_prompts)):
                # Extract from the prompt the terms with negative weights and add them to the negative prompt
                current_prompt = p.all_prompts[i]
                current_negative_prompt = p.all_negative_prompts[i]
                already_applied = []
                while True:
                    matches = regex.findall(current_prompt)
                    if len(matches) == 0:
                        break
                    for match in matches:
                        if match[0] not in already_applied:
                            logger.debug("Found negative term: %s", match[0])
                            current_negative_prompt = match[1] + match[2] + " " + current_negative_prompt
                            current_prompt = current_prompt.replace(match[0], "")
                            already_applied.append(match[0])
                        else:
                            logger.debug("Found repeated negative term: %s", match[0])
                p.all_prompts[i] = current_prompt
                p.all_negative_prompts[i] = current_negative_prompt
        except Exception as e:
            logger.exception(e)
