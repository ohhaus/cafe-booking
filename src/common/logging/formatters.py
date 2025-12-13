import logging
from typing import Any

from colorama import Fore, Style


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами ANSI для консольного вывода.

    Добавляет цвета к уровням логирования для улучшения читаемости.
    """

    LEVEL_COLORS = {
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record: Any) -> str:
        """Форматирует запись лога с цветами.

        Args:
            record: Запись лога

        Returns:
            Отформатированная строка лога

        """
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        record.levelname = f'{level_color}{record.levelname}{Style.RESET_ALL}'
        return super().format(record)
