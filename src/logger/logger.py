import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Any

from colorama import Fore, Style, init

from config import COUNT_FILES, MAX_BYTES


init(strip=False, autoreset=True)

if not sys.stdout.isatty():
    os.environ.setdefault('FORCE_COLOR', '1')
    os.environ.setdefault('CLICOLOR_FORCE', '1')
    if 'TERM' not in os.environ:
        os.environ['TERM'] = 'xterm-256color'


class UserFilter(logging.Filter):
    """Пользовательский фильтр: добавляет plain и colored версии user."""

    ROLE_COLOR = {
        'USER': Fore.GREEN,
        'MANAGER': Fore.YELLOW,
        'ADMIN': Fore.BLUE,
    }

    def filter(self, record: Any) -> bool:
        """Добавляет информацию о пользователе в запись лога."""
        user = getattr(record, 'user', None)
        if user is None or user == 'SYSTEM' or not isinstance(user, str):
            record.user_plain = 'SYSTEM'
            record.user_colored = f'{Fore.MAGENTA}SYSTEM{Style.RESET_ALL}'
        else:
            user_clean = user.strip()
            record.user_plain = user_clean
            role = user_clean.split(' ', 1)[0]
            role_color = self.ROLE_COLOR.get(role, Fore.CYAN)
            record.user_colored = f'{role_color}{user_clean}{Style.RESET_ALL}'
        return True


class ColoredFormatter(logging.Formatter):
    """Форматтер логирования, добавляющий цвета ANSI к именам уровней."""

    LEVEL_COLORS = {
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record: Any) -> str:
        """Добавляет цвет к record.levelname."""
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        record.levelname = f'{level_color}{record.levelname}{Style.RESET_ALL}'
        return super().format(record)


logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)
logs_path = os.path.join(logs_dir, 'working.log')

logging.addLevelName(logging.INFO, 'INFO')
logging.addLevelName(logging.WARNING, '⚠️ WARNING')
logging.addLevelName(logging.ERROR, '🛑 ERROR')
logging.addLevelName(logging.CRITICAL, '💀CRITICAL💀')

handler = RotatingFileHandler(
    logs_path,
    maxBytes=MAX_BYTES,
    backupCount=COUNT_FILES,
    encoding='utf-8',
)

stdout_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter(
    fmt='%(asctime)s | %(levelname)s | %(user_plain)s | %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
)

console_formatter = ColoredFormatter(
    fmt='%(asctime)s | %(levelname)s | %(user_colored)s | %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
)

logger = logging.getLogger('app')
logger.setLevel(logging.INFO)

stdout_handler.setFormatter(console_formatter)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(stdout_handler)
logger.addFilter(UserFilter())
logger.propagate = False
