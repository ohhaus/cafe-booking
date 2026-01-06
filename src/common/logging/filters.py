import logging
from typing import Any

from colorama import Fore, Style


class UserFilter(logging.Filter):
    """Фильтр для добавления информации о пользователе в логи.

    Добавляет plain и colored версии user в запись лога.
    """

    ROLE_COLOR = {
        'USER': Fore.GREEN,
        'MANAGER': Fore.YELLOW,
        'ADMIN': Fore.BLUE,
    }

    def filter(self, record: Any) -> bool:
        """Добавляет информацию о пользователе в запись лога.

        Args:
            record: Запись лога

        Returns:
            True (фильтр всегда пропускает записи)

        """
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
