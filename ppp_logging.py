import sys
import copy
import logging


class PromptPostProcessorLogFactory:
    class ColoredFormatter(logging.Formatter):
        COLORS = {
            "DEBUG": "\033[0;36m",  # CYAN
            "INFO": "\033[0;32m",  # GREEN
            "WARNING": "\033[0;33m",  # YELLOW
            "ERROR": "\033[0;31m",  # RED
            "CRITICAL": "\033[0;37;41m",  # WHITE ON RED
            "RESET": "\033[0m",  # RESET COLOR
        }

        def format(self, record):
            colored_record = copy.copy(record)
            levelname = colored_record.levelname
            seq = self.COLORS.get(levelname, self.COLORS["RESET"])
            colored_record.levelname = f"{seq}{levelname}{self.COLORS['RESET']}"
            return super().format(colored_record)

    def __init__(self):
        ppplog = logging.getLogger("PromptPostProcessor")
        ppplog.propagate = False
        if not ppplog.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(self.ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            ppplog.addHandler(handler)
        ppplog.setLevel(logging.INFO)
        self.log = PromptPostProcessorLogCustomAdapter(ppplog)


class PromptPostProcessorLogCustomAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[PromptPostProcessor] {msg}", kwargs
