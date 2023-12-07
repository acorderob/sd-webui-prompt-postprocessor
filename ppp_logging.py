import logging
import sys
import copy


class PromptPostProcessorLogFactory:  # pylint: disable=too-few-public-methods
    """
    Factory class for creating loggers for the PromptPostProcessor module.
    """

    class ColoredFormatter(logging.Formatter):
        """
        A custom logging formatter that adds color to log records based on their level.

        Attributes:
            COLORS (dict): A dictionary mapping log levels to ANSI escape codes for colors.

        Methods:
            format(record): Formats the log record with color based on its level.

        """

        COLORS = {
            "DEBUG": "\033[0;36m",  # CYAN
            "INFO": "\033[0;32m",  # GREEN
            "WARNING": "\033[0;33m",  # YELLOW
            "ERROR": "\033[0;31m",  # RED
            "CRITICAL": "\033[0;37;41m",  # WHITE ON RED
            "RESET": "\033[0m",  # RESET COLOR
        }

        def format(self, record):
            """
            Formats the log record with color based on the log level.

            Args:
                record (LogRecord): The log record to be formatted.

            Returns:
                str: The formatted log record.
            """
            colored_record = copy.copy(record)
            levelname = colored_record.levelname
            seq = self.COLORS.get(levelname, self.COLORS["RESET"])
            colored_record.levelname = f"{seq}{levelname}{self.COLORS['RESET']}"
            return super().format(colored_record)

    def __init__(self):
        """
        Initializes the PromptPostProcessor class.

        This method sets up the logger for the PromptPostProcessor class and configures its log level and handlers.

        Args:
            None

        Returns:
            None
        """
        ppplog = logging.getLogger("PromptPostProcessor")
        ppplog.propagate = False
        if not ppplog.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(self.ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            ppplog.addHandler(handler)
        ppplog.setLevel(logging.INFO)
        self.log = PromptPostProcessorLogCustomAdapter(ppplog)


class PromptPostProcessorLogCustomAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter for the PromptPostProcessor.
    This adapter adds a prefix to log messages to indicate that they are related to the PromptPostProcessor.
    """

    def process(self, msg, kwargs):
        """
        Process the log message and keyword arguments.

        Args:
            msg (str): The log message.
            kwargs (dict): The keyword arguments.

        Returns:
            tuple: A tuple containing the processed log message and keyword arguments.
        """
        return f"[PromptPostProcessor] {msg}", kwargs
