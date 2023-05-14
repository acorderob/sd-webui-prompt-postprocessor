import logging
import re


class SendToNegative:  # pylint: disable=too-few-public-methods
    NAME = "Send to Negative"
    VERSION = "1.1"

    DEFAULT_TAG_START = "<!"
    DEFAULT_TAG_END = "!>"
    DEFAULT_TAG_PARAM_START = "!"
    DEFAULT_TAG_PARAM_END = "!"
    DEFAULT_SEPARATOR = ", "

    def __init__(
        self,
        tag_start=None,
        tag_end=None,
        tag_param_start=None,
        tag_param_end=None,
        separator=None,
        ignore_repeats=None,
        cleanup=None,
        opts=None,
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
        self.__logger = logging.getLogger(__name__)

        str_start = (
            tag_start
            if tag_start is not None
            else getattr(opts, "stn_tagstart", self.DEFAULT_TAG_START)
            if opts is not None
            else self.DEFAULT_TAG_START
        )
        str_end = (
            tag_end
            if tag_end is not None
            else getattr(opts, "stn_tagend", self.DEFAULT_TAG_END)
            if opts is not None
            else self.DEFAULT_TAG_END
        )
        str_param_start = (
            tag_param_start
            if tag_param_start is not None
            else getattr(opts, "stn_tagparamstart", self.DEFAULT_TAG_PARAM_START)
            if opts is not None
            else self.DEFAULT_TAG_PARAM_START
        )
        str_param_end = (
            tag_param_end
            if tag_param_end is not None
            else getattr(opts, "stn_tagparamend", self.DEFAULT_TAG_PARAM_END)
            if opts is not None
            else self.DEFAULT_TAG_PARAM_END
        )
        escape_sequence = r"(?<!\\)"
        self.__ignore_repeats = (
            ignore_repeats if ignore_repeats is not None else getattr(opts, "stn_ignorerepeats", True)
        )
        self.__cleanup = (
            cleanup if cleanup is not None else getattr(opts, "stn_cleanup", True) if opts is not None else True
        )
        self.__separator = (
            separator
            if separator is not None
            else getattr(opts, "stn_separator", self.DEFAULT_SEPARATOR)
            if opts is not None
            else self.DEFAULT_SEPARATOR
        )
        self.__insertion_point_tags = [
            (str_start + str_param_start + "i" + str(x) + str_param_end + str_end) for x in range(10)
        ]
        self.__regex = re.compile(
            "("
            + escape_sequence
            + re.escape(str_start)
            + "(?:"
            + re.escape(str_param_start)
            + "([se]|(?:[pi][0-9]))"
            + re.escape(str_param_end)
            + ")?(.*?)"
            + escape_sequence
            + re.escape(str_end)
            + ")",
            re.S,
        )

    def process_prompt(self, original_prompt, original_negative_prompt):
        """
        Extract from the prompt the tagged parts and add them to the negative prompt
        """
        try:
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.__logger.debug(f"Input prompt: {prompt}")
            self.__logger.debug(f"Input negative_prompt: {negative_prompt}")
            prompt, add_at = self.__find_tags(prompt)
            negative_prompt = self.__add_to_insertion_points(negative_prompt, add_at["insertion_point"])
            if len(add_at["start"]) > 0:
                negative_prompt = self.__add_to_start(negative_prompt, add_at["start"])
            if len(add_at["end"]) > 0:
                negative_prompt = self.__add_to_end(negative_prompt, add_at["end"])
            self.__logger.debug(f"Output prompt: {prompt}")
            self.__logger.debug(f"Output negative_prompt: {negative_prompt}")
            return prompt, negative_prompt
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.__logger.exception(e)
            return original_prompt, original_negative_prompt

    def __find_tags(self, prompt):
        already_processed = []
        add_at = {"start": [], "insertion_point": [[] for x in range(10)], "end": []}
        # process tags in prompt
        matches = self.__regex.findall(prompt)
        for match in matches:
            position = match[1] or "s"
            content = match[2]
            if len(content) > 0:
                if content not in already_processed:
                    if self.__ignore_repeats:
                        already_processed.append(content)
                    self.__logger.debug(f"Processing content at position {position}: {content}")
                    if position == "e":
                        add_at["end"].append(content)
                    elif position.startswith("p"):
                        n = int(position[1])
                        add_at["insertion_point"][n].append(content)
                    else:  # position == "s" or invalid
                        add_at["start"].append(content)
                else:
                    self.__logger.warning(f"Ignoring repeated content: {content}")
                # clean-up
            prompt = prompt.replace(match[0], "")
            if self.__cleanup:
                prompt = (
                    prompt.replace("  ", " ")
                    .replace(self.__separator + self.__separator, self.__separator)
                    .replace(" " + self.__separator, self.__separator)
                    .removeprefix(self.__separator)
                    .removesuffix(self.__separator)
                    .strip()
                )
        return prompt, add_at

    def __add_to_insertion_points(self, negative_prompt, add_at_insertion_point):
        for n in range(10):
            ipp = negative_prompt.find(self.__insertion_point_tags[n])
            if ipp >= 0:
                ipl = len(self.__insertion_point_tags[n])
                if negative_prompt[ipp - len(self.__separator) : ipp] == self.__separator:
                    ipp -= len(self.__separator)  # adjust for existing start separator
                    ipl += len(self.__separator)
                add_at_insertion_point[n].insert(0, negative_prompt[:ipp])
                if negative_prompt[ipp + ipl : ipp + ipl + len(self.__separator)] == self.__separator:
                    ipl += len(self.__separator)  # adjust for existing end separator
                endPart = negative_prompt[ipp + ipl :]
                if len(endPart) > 0:
                    add_at_insertion_point[n].append(endPart)
                negative_prompt = self.__separator.join(add_at_insertion_point[n])
            else:
                ipp = 0
                if negative_prompt.startswith(self.__separator):
                    ipp = len(self.__separator)
                add_at_insertion_point[n].append(negative_prompt[ipp:])
                negative_prompt = self.__separator.join(add_at_insertion_point[n])
        return negative_prompt

    def __add_to_start(self, negative_prompt, add_at_start):
        if len(negative_prompt) > 0:
            ipp = 0
            if negative_prompt.startswith(self.__separator):
                ipp = len(self.__separator)  # adjust for existing end separator
            add_at_start.append(negative_prompt[ipp:])
        negative_prompt = self.__separator.join(add_at_start)
        return negative_prompt

    def __add_to_end(self, negative_prompt, add_at_end):
        if len(negative_prompt) > 0:
            ipl = len(negative_prompt)
            if negative_prompt.endswith(self.__separator):
                ipl -= len(self.__separator)  # adjust for existing start separator
            add_at_end.insert(0, negative_prompt[:ipl])
        negative_prompt = self.__separator.join(add_at_end)
        return negative_prompt
