import logging
from logging.handlers import RotatingFileHandler
import os
import sys

from colorama import init

from src.common.logging.filters import UserFilter
from src.common.logging.formatters import ColoredFormatter
from src.config import COUNT_FILES, MAX_BYTES


# Инициализация colorama
init(strip=False, autoreset=True)

# Настройка для non-TTY окружений
if not sys.stdout.isatty():
    os.environ.setdefault('FORCE_COLOR', '1')
    os.environ.setdefault('CLICOLOR_FORCE', '1')
    if 'TERM' not in os.environ:
        os.environ['TERM'] = 'xterm-256color'

# Создание директории для логов
logs_dir = '/app/logs'
os.makedirs(logs_dir, exist_ok=True)
logs_path = os.path.join(logs_dir, 'working.log')

# Кастомные имена уровней
logging.addLevelName(logging.INFO, 'INFO')
logging.addLevelName(logging.WARNING, '⚠️ WARNING')
logging.addLevelName(logging.ERROR, '🛑 ERROR')
logging.addLevelName(logging.CRITICAL, '💀CRITICAL💀')

# File handler
file_handler = RotatingFileHandler(
    logs_path,
    maxBytes=MAX_BYTES,
    backupCount=COUNT_FILES,
    encoding='utf-8',
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)

# Formatters
file_formatter = logging.Formatter(
    fmt='%(asctime)s | %(levelname)s | %(user_plain)s | %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
)

console_formatter = ColoredFormatter(
    fmt='%(asctime)s | %(levelname)s | %(user_colored)s | %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
)

# Logger setup
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)

console_handler.setFormatter(console_formatter)
file_handler.setFormatter(file_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.addFilter(UserFilter())

logger.propagate = False
