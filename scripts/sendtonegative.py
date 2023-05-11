import logging
from modules.processing import StableDiffusionProcessing
import modules.scripts as scripts
import re

VERSION = "0.2"

# TODO : support marking in the negative prompt to move to the positive
# TODO : add separator and ignoreRepeats to ui
# TODO : add tests
# TODO : replace regex with proper parsing to detect recursion

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

strStart = "<!"
strEnd = "!>"
strParamStart = "!"
strParamEnd = "!"
"""
Default format: <!content!> or <!!x!content!>
    with x = s (start position) e (end position) p (specified position) i (insertion point)
    both p and i have to be followed by a number 0-9
    the insertion point does not accept content
"""
escapeSequence = r"(?<!\\)"
ignoreRepeats = True
separator = ", "
insertionPointTags = [
    (strStart + strParamStart + "i" + str(x) + strParamEnd + strEnd) for x in range(10)
]
find = (
    "("
    + escapeSequence
    + re.escape(strStart)
    + "(?:"
    + re.escape(strParamStart)
    + "([se]|(?:[pi][0-9]))"
    + re.escape(strParamEnd)
    + ")?(.*?)"
    + escapeSequence
    + re.escape(strEnd)
    + ")"
)
regex = re.compile(find, re.S)


def processPrompts(original_prompt, original_negative_prompt):
    """
    Extract from the prompt the marked parts and add them to the negative prompt
    """
    try:
        prompt = original_prompt
        negative_prompt = original_negative_prompt
        insertionPointPositions = [negative_prompt.find(x) for x in insertionPointTags]
        alreadyProcessed = []
        addAtStart = []
        addAtEnd = []
        addAtInsertionPoint = [[] for x in range(10)]
        matches = regex.findall(prompt)
        for match in matches:
            position = match[1] or "s"
            content = match[2]
            if len(content) > 0:
                if content not in alreadyProcessed:
                    if ignoreRepeats:
                        alreadyProcessed.append(content)
                    logger.debug("Processing content: %s", content)
                    if position is "e":
                        addAtEnd.append(content)
                    elif position.startswith("p"):
                        n = int(position[1])
                        addAtInsertionPoint[n].append(content)
                    else:  # position is "s" or invalid
                        addAtStart.append(content)
                else:
                    logger.warn("Ignoring repeated content: %s", content)
            prompt = prompt.replace(match[0], "")

        # Add content to insertion points
        for n in range(10):
            if insertionPointPositions[n] >= 0:
                ipp = insertionPointPositions[n]
                ipl = len(insertionPointTags[n])
                if negative_prompt[ipp - len(separator) : ipp] == separator:
                    ipp -= len(separator)  # adjust for existing start separator
                    ipl += len(separator)
                addAtInsertionPoint[n].insert(0, negative_prompt[:ipp])
                if negative_prompt[ipp + ipl : ipp + ipl + len(separator)] == separator:
                    ipl += len(separator)  # adjust for existing end separator
                endPart = negative_prompt[ipp + ipl :]
                if len(endPart) > 0:
                    addAtInsertionPoint[n].append(endPart)
                negative_prompt = separator.join(addAtInsertionPoint[n])
            else:
                ipp = 0
                if negative_prompt.startswith(separator):
                    ipp = len(separator)
                addAtInsertionPoint[n].append(negative_prompt[ipp:])
                negative_prompt = separator.join(addAtInsertionPoint[n])

        # Add content to start
        if len(addAtStart) > 0:
            if len(negative_prompt) > 0:
                ipp = 0
                if negative_prompt.startswith(separator):
                    ipp = len(separator) # adjust for existing end separator
                addAtStart.append(negative_prompt[ipp:])
            negative_prompt = separator.join(addAtStart)

        # Add content to end
        if len(addAtEnd) > 0:
            if len(negative_prompt) > 0:
                ipl = len(negative_prompt)
                if negative_prompt.endswith(separator):
                    ipl -= len(separator) # adjust for existing start separator
                addAtEnd.insert(0, negative_prompt[:ipl])
            negative_prompt = separator.join(addAtEnd)

        return prompt, negative_prompt
    except Exception as e:
        logger.exception(e)
        return original_prompt, original_negative_prompt


class Script(scripts.Script):
    def __init__(self):
        pass

    def title(self):
        return f"SendToNegative v{VERSION}"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):
        for i in range(len(p.all_prompts)):
            p.all_prompts[i], p.all_negative_prompts[i] = processPrompts(
                p.all_prompts[i], p.all_negative_prompts[i]
            )
