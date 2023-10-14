from collections import namedtuple
import re
import math
import lark


class SendToNegative:  # pylint: disable=too-few-public-methods
    NAME = "Send to Negative"
    VERSION = "2.1.4"

    DEFAULT_SEPARATOR = ", "

    def __init__(
        self,
        log,
        separator=None,
        ignore_repeats=None,
        join_attention=None,
        cleanup=None,
        opts=None,
    ):
        """
        Format for the tag:
            <!content!>

            <!!x!content!>

        with x being:
            s - content is added at the start of the negative prompt. This is the default if no parameter exists.

            e - content is added at the end of the negative prompt.

            pN - content is added where the insertion point N is in the negative prompt or at the start if it does not exist. N can be 0 to 9.

            iN - tags the position of insertion point N. Used only in the negative prompt and does not accept content. N can be 0 to 9.
        """
        self.__logger = log
        if opts is not None and getattr(opts, "prompt_attention", "") == "Compel parser":
            self.__logger.warning("Compel parser is not supported!")
        self.__ignore_repeats = (
            ignore_repeats if ignore_repeats is not None else getattr(opts, "stn_ignorerepeats", True)
        )
        self.__join_attention = (
            join_attention
            if join_attention is not None
            else getattr(opts, "stn_joinattention", True)
            if opts is not None
            else True
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
        self.__insertion_point_tags = [f"<!!i{x}!!>" for x in range(10)]
        # Process with lark (debug with https://www.lark-parser.org/ide/)
        self.__schedule_parser = lark.Lark(
            r"""
                start: (prompt | /[\][():|<>!]/+)*
                ?prompt: (emphasized | deemphasized | scheduled | alternate | modeltag | negtag | plain)*
                ?nonegprompt: (emphasized | deemphasized | scheduled | alternate | modeltag | plain)*
                emphasized: "(" prompt [":" numpar] ")"
                deemphasized: "[" prompt "]"
                scheduled: "[" [prompt ":"] prompt ":" numpar "]"
                alternate: "[" alternateoption ("|" alternateoption)+ "]"
                alternateoption: prompt
                negtag: "<!" [negtagparameters] nonegprompt "!>"
                negtagparameters: "!" /s|e|[ip]\d/ "!"
                modeltag: "<" /(?!!)[^>]+/ ">"
                numpar: WHITESPACE* NUMBER WHITESPACE*
                WHITESPACE: /\s+/
                ?plain: /([^\\[\]():|<>!]|\\.)+/s
                %import common.SIGNED_NUMBER -> NUMBER
            """,
            propagate_positions=True,
        )

    class ReadTree(lark.visitors.Interpreter):
        def __init__(self, logger, ignorerepeats, joinattention, prompt, add_at):
            super().__init__()
            self.__logger = logger
            self.__ignore_repeats = ignorerepeats
            self.__join_attention = joinattention
            self.__prompt = prompt
            self.AccumulatedShell = namedtuple("AccumulatedShell", ["type", "info1", "info2"])
            AccumulatedShell = self.AccumulatedShell
            self.__shell: list[AccumulatedShell] = []
            self.NegTag = namedtuple("NegTag", ["start", "end", "content", "parameters", "shell"])
            NegTag = self.NegTag
            self.__negtags: list[NegTag] = []
            self.__already_processed = []
            self.add_at = add_at
            self.remove = []

        def __get_numpar_value(self, numpar):
            return float(next(x for x in numpar.children if x.type == "NUMBER").value)

        def scheduled(self, tree):
            if len(tree.children) > 2:  # before & after
                before = tree.children[0]
            else:
                before = None
            after = tree.children[-2]
            numpar = tree.children[-1]
            pos = self.__get_numpar_value(numpar)
            if pos >= 1:
                pos = int(pos)
            # self.__shell.append(self.AccumulatedShell("sc", tree.meta.start_pos, pos))
            if before is not None and hasattr(before, "data"):
                self.__logger.debug(
                    f"Shell scheduled before at {[before.meta.start_pos,before.meta.end_pos] if hasattr(before,'meta') and not before.meta.empty else '?'} : {pos}"
                )
                self.__shell.append(self.AccumulatedShell("scb", pos, None))
                self.visit(before)
                self.__shell.pop()
            if hasattr(after, "data"):
                self.__logger.debug(
                    f"Shell scheduled after at {[after.meta.start_pos,after.meta.end_pos] if hasattr(after,'meta') and not after.meta.empty else '?'} : {pos}"
                )
                self.__shell.append(self.AccumulatedShell("sca", pos, None))
                self.visit(after)
                self.__shell.pop()
            # self.__shell.pop()

        def alternate(self, tree):
            # self.__shell.append(self.AccumulatedShell("al", tree.meta.start_pos, len(tree.children)))
            for i, opt in enumerate(tree.children):
                self.__logger.debug(
                    f"Shell alternate at {[opt.meta.start_pos,opt.meta.end_pos] if hasattr(opt,'meta') and not opt.meta.empty else '?'} : {i+1}"
                )
                if hasattr(opt, "data"):
                    self.__shell.append(self.AccumulatedShell("alo", i + 1, len(tree.children)))
                    self.visit(opt)
                    self.__shell.pop()
            # self.__shell.pop()

        def emphasized(self, tree):
            numpar = tree.children[-1]
            weight = self.__get_numpar_value(numpar) if numpar is not None else 1.1
            self.__logger.debug(
                f"Shell attention at {[tree.meta.start_pos,tree.meta.end_pos] if hasattr(tree,'meta') and not tree.meta.empty else '?'}: {weight}"
            )
            self.__shell.append(self.AccumulatedShell("at", weight, None))
            self.visit_children(tree)
            self.__shell.pop()

        def deemphasized(self, tree):
            weight = 0.9
            self.__logger.debug(
                f"Shell attention at {[tree.meta.start_pos,tree.meta.end_pos] if hasattr(tree,'meta') and not tree.meta.empty else '?'}: {weight}"
            )
            self.__shell.append(self.AccumulatedShell("at", weight, None))
            self.visit_children(tree)
            self.__shell.pop()

        def negtag(self, tree):
            negtagparameters = tree.children[0]
            parameters = negtagparameters.children[0].value if negtagparameters is not None else ""
            rest = []
            for x in tree.children[1::]:
                rest.append(
                    self.__prompt[x.meta.start_pos : x.meta.end_pos]
                    if hasattr(x, "meta") and not x.meta.empty
                    else x.value
                )
            content = "".join(rest)
            self.__negtags.append(
                self.NegTag(tree.meta.start_pos, tree.meta.end_pos, content, parameters, self.__shell.copy())
            )
            self.__logger.debug(
                f"Negative tag at {[tree.meta.start_pos,tree.meta.end_pos] if hasattr(tree,'meta') and not tree.meta.empty else '?'}: {parameters}: {content.encode('unicode_escape').decode('utf-8')}"
            )

        def start(self, tree):
            self.visit_children(tree)
            # process the found negtags
            for nt in self.__negtags:
                if self.__join_attention:
                    # join consecutive attention elements
                    for i in range(len(nt.shell) - 1, 0, -1):
                        if nt.shell[i].type == "at" and nt.shell[i - 1].type == "at":
                            nt.shell[i - 1] = self.AccumulatedShell(
                                "at",
                                math.floor(100 * nt.shell[i - 1].info1 * nt.shell[i].info1)
                                / 100,  # we limit to two decimals
                                None,
                            )
                            nt.shell.pop(i)
                start = ""
                end = ""
                for s in nt.shell:
                    match s.type:
                        case "at":
                            if s.info1 == 0.9:
                                start += "["
                                end = "]" + end
                            elif s.info1 == 1.1:
                                start += "("
                                end = ")" + end
                            else:
                                start += "("
                                end = f":{s.info1})" + end
                        # case "sc":
                        case "scb":
                            start += "["
                            end = f"::{s.info1}]" + end
                        case "sca":
                            start += "["
                            end = f":{s.info1}]" + end
                        # case "al":
                        case "alo":
                            start += "[" + ("|" * int(s.info1 - 1))
                            end = ("|" * int(s.info2 - s.info1)) + "]" + end
                content = start + nt.content + end
                position = nt.parameters or "s"
                if len(content) > 0:
                    if content not in self.__already_processed:
                        if self.__ignore_repeats:
                            self.__already_processed.append(content)
                        self.__logger.debug(
                            f"Adding content at position {position}: {content.encode('unicode_escape').decode('utf-8')}"
                        )
                        if position == "e":
                            self.add_at["end"].append(content)
                        elif position.startswith("p"):
                            n = int(position[1])
                            self.add_at["insertion_point"][n].append(content)
                        else:  # position == "s" or invalid
                            self.add_at["start"].append(content)
                    else:
                        self.__logger.warning(
                            f"Ignoring repeated content: {content.encode('unicode_escape').decode('utf-8')}"
                        )
                # remove from prompt
                self.remove.append([nt.start, nt.end])

    def process_prompt(self, original_prompt, original_negative_prompt):
        """
        Extract from the prompt the tagged parts and add them to the negative prompt
        """
        try:
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.__logger.debug(f"Input prompt: {prompt.encode('unicode_escape').decode('utf-8')}")
            self.__logger.debug(f"Input negative_prompt: {negative_prompt.encode('unicode_escape').decode('utf-8')}")
            prompt, add_at = self.__find_tags(prompt)
            negative_prompt = self.__add_to_insertion_points(negative_prompt, add_at["insertion_point"])
            if len(add_at["start"]) > 0:
                negative_prompt = self.__add_to_start(negative_prompt, add_at["start"])
            if len(add_at["end"]) > 0:
                negative_prompt = self.__add_to_end(negative_prompt, add_at["end"])
            self.__logger.debug(f"Output prompt: {prompt.encode('unicode_escape').decode('utf-8')}")
            self.__logger.debug(f"Output negative_prompt: {negative_prompt.encode('unicode_escape').decode('utf-8')}")
            return prompt, negative_prompt
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.__logger.exception(e)
            return original_prompt, original_negative_prompt

    def __find_tags(self, prompt):
        add_at = {"start": [], "insertion_point": [[] for x in range(10)], "end": []}
        tree = self.__schedule_parser.parse(prompt)
        self.__logger.debug(f"Initial tree:\n{tree.pretty()}")

        readtree = self.ReadTree(self.__logger, self.__ignore_repeats, self.__join_attention, prompt, add_at)
        readtree.visit(tree)

        for r in readtree.remove[::-1]:
            prompt = prompt[: r[0]] + prompt[r[1] :]
        if self.__cleanup:
            prompt = re.sub(r"\((?::[+-]?[\d\.]+)?\)", "", prompt)  # clean up empty attention
            prompt = re.sub(r"\[\]", "", prompt)  # clean up empty attention
            prompt = re.sub(r"\[:?:[+-]?[\d\.]+\]", "", prompt)  # clean up empty scheduling
            prompt = re.sub(r"\[\|+\]", "", prompt)  # clean up empty alternation
            # clean up whitespace and extra separators
            prompt = (
                prompt.replace("  ", " ")
                .replace(self.__separator + self.__separator, self.__separator)
                .replace(" " + self.__separator, self.__separator)
                .removeprefix(self.__separator)
                .removesuffix(self.__separator)
                .strip()
            )
        add_at = readtree.add_at
        self.__logger.debug(f"New negative additions: {add_at}")

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
