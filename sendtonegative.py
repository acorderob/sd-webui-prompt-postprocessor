import logging
import re


class SendToNegative:
    NAME = "Send to Negative"
    VERSION = "0.3"

    DEFAULT_tagStart = "<!"
    DEFAULT_tagEnd = "!>"
    DEFAULT_tagParamStart = "!"
    DEFAULT_tagParamEnd = "!"
    DEFAULT_separator = ", "

    def __init__(
        self,
        tagStart=None,
        tagEnd=None,
        tagParamStart=None,
        tagParamEnd=None,
        separator=None,
        ignoreRepeats=None,
        cleanup=None,
        opts=None,
        logger=None,
    ):
        """
        Default format for the tag:
            <!content!>

            <!!x!content!>

        with x being:
            s - content is added at the start of the negative prompt. This is the default if no parameter exists.

            e - content is added at the end of the negative prompt.

            pN - content is added where the insertion point N is in the negative prompt or at the start if it does not exist. N can be 0 to 9.

            iN - tags the position of insertion point N. Used only in the negative prompt and does not accept content. N can be 0 to 9.
        """
        if logger is None:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
        else:
            self.logger = logger

        strStart = (
            tagStart
            if tagStart is not None
            else getattr(opts, "stn_tagstart", self.DEFAULT_tagStart)
            if opts is not None
            else self.DEFAULT_tagStart
        )
        strEnd = (
            tagEnd
            if tagEnd is not None
            else getattr(opts, "stn_tagend", self.DEFAULT_tagEnd)
            if opts is not None
            else self.DEFAULT_tagEnd
        )
        strParamStart = (
            tagParamStart
            if tagParamStart is not None
            else getattr(opts, "stn_tagparamstart", self.DEFAULT_tagParamStart)
            if opts is not None
            else self.DEFAULT_tagParamStart
        )
        strParamEnd = (
            tagParamEnd
            if tagParamEnd is not None
            else getattr(opts, "stn_tagparamend", self.DEFAULT_tagParamEnd)
            if opts is not None
            else self.DEFAULT_tagParamEnd
        )
        escapeSequence = r"(?<!\\)"
        self.ignoreRepeats = (
            ignoreRepeats
            if ignoreRepeats is not None
            else getattr(opts, "stn_ignorerepeats", True)
        )
        self.cleanup = (
            cleanup
            if cleanup is not None
            else getattr(opts, "stn_cleanup", True)
            if opts is not None
            else True
        )
        self.separator = (
            separator
            if separator is not None
            else getattr(opts, "stn_separator", self.DEFAULT_separator)
            if opts is not None
            else self.DEFAULT_separator
        )
        self.insertionPointTags = [
            (strStart + strParamStart + "i" + str(x) + strParamEnd + strEnd)
            for x in range(10)
        ]
        self.regex = re.compile(
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
            + ")",
            re.S,
        )

    def processPrompt(self, original_prompt, original_negative_prompt):
        """
        Extract from the prompt the tagged parts and add them to the negative prompt
        """
        try:
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            alreadyProcessed = []
            addAtStart = []
            addAtEnd = []
            addAtInsertionPoint = [[] for x in range(10)]
            # process tags in prompt
            matches = self.regex.findall(prompt)
            for match in matches:
                position = match[1] or "s"
                content = match[2]
                if len(content) > 0:
                    if content not in alreadyProcessed:
                        if self.ignoreRepeats:
                            alreadyProcessed.append(content)
                        self.logger.debug("Processing content: %s", content)
                        if position == "e":
                            addAtEnd.append(content)
                        elif position.startswith("p"):
                            n = int(position[1])
                            addAtInsertionPoint[n].append(content)
                        else:  # position == "s" or invalid
                            addAtStart.append(content)
                    else:
                        self.logger.warn("Ignoring repeated content: %s", content)
                # clean-up
                prompt = prompt.replace(match[0], "")
                if self.cleanup:
                    prompt = (
                        prompt.replace("  ", " ")
                        .replace(self.separator + self.separator, self.separator)
                        .removeprefix(self.separator)
                        .removesuffix(self.separator)
                        .strip()
                    )

            # Add content to insertion points
            for n in range(10):
                ipp = negative_prompt.find(self.insertionPointTags[n])
                if ipp >= 0:
                    ipl = len(self.insertionPointTags[n])
                    if (
                        negative_prompt[ipp - len(self.separator) : ipp]
                        == self.separator
                    ):
                        ipp -= len(
                            self.separator
                        )  # adjust for existing start separator
                        ipl += len(self.separator)
                    addAtInsertionPoint[n].insert(0, negative_prompt[:ipp])
                    if (
                        negative_prompt[ipp + ipl : ipp + ipl + len(self.separator)]
                        == self.separator
                    ):
                        ipl += len(self.separator)  # adjust for existing end separator
                    endPart = negative_prompt[ipp + ipl :]
                    if len(endPart) > 0:
                        addAtInsertionPoint[n].append(endPart)
                    negative_prompt = self.separator.join(addAtInsertionPoint[n])
                else:
                    ipp = 0
                    if negative_prompt.startswith(self.separator):
                        ipp = len(self.separator)
                    addAtInsertionPoint[n].append(negative_prompt[ipp:])
                    negative_prompt = self.separator.join(addAtInsertionPoint[n])

            # Add content to start
            if len(addAtStart) > 0:
                if len(negative_prompt) > 0:
                    ipp = 0
                    if negative_prompt.startswith(self.separator):
                        ipp = len(self.separator)  # adjust for existing end separator
                    addAtStart.append(negative_prompt[ipp:])
                negative_prompt = self.separator.join(addAtStart)

            # Add content to end
            if len(addAtEnd) > 0:
                if len(negative_prompt) > 0:
                    ipl = len(negative_prompt)
                    if negative_prompt.endswith(self.separator):
                        ipl -= len(
                            self.separator
                        )  # adjust for existing start separator
                    addAtEnd.insert(0, negative_prompt[:ipl])
                negative_prompt = self.separator.join(addAtEnd)

            return prompt, negative_prompt
        except Exception as e:
            self.logger.exception(e)
            return original_prompt, original_negative_prompt
