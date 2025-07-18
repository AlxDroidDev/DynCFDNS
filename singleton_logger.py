import logging
import threading
import os
from typing import Optional


class SingletonLogger:
    """Thread-safe singleton logger."""

    _instance: Optional['SingletonLogger'] = None
    _lock = threading.Lock()
    _logger: Optional[logging.Logger] = None
    _initialized = False

    def __new__(cls) -> 'SingletonLogger':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SingletonLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._setup_logger()
                    self._initialized = True

    def _setup_logger(self):
        """Setup the logger configuration."""
        self._logger = logging.getLogger('DynCFDNS')
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to prevent duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        # Create file handler
        log_dir = "/app/logs"
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler("/app/logs/dyncfdns.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        # Prevent propagation to root logger
        self._logger.propagate = False

    def debug(self, message: str):
        """Log debug message."""
        self._logger.debug(message)

    def info(self, message: str):
        """Log info message."""
        self._logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self._logger.warning(message)

    def warn(self, message: str):
        """Log warning message (alias for compatibility)."""
        self._logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self._logger.error(message)

    def critical(self, message: str):
        """Log critical message."""
        self._logger.critical(message)

    def exception(self, message: str):
        """Log exception with traceback."""
        self._logger.exception(message)

    def set_level(self, level: int):
        """Set logging level."""
        self._logger.setLevel(level)


# Global logger instance
logger = SingletonLogger()

info = logger.info
warn = logger.warning
error = logger.error
critical = logger.critical
debug = logger.debug
