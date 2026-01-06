import asyncio
from email.mime.text import MIMEText
from email.utils import formataddr
import logging
import smtplib
import ssl

from src.booking.models import Booking
from src.config import settings


logger = logging.getLogger('app')


class NotificationServise:
    """Сервис отправки уведомление."""

    async def _send_email(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
    ) -> None:
        """Отправка email."""

        def send_sync() -> None:
            server: smtplib.SMTP | smtplib.SMTP_SSL | None = None
            try:
                message = MIMEText(body, 'html')

                # From с именем (опционально, но приятно)
                message['From'] = formataddr(
                    (
                        settings.mail.FROM_NAME,
                        settings.mail.FROM,
                    ),
                )
                message['Subject'] = subject

                timeout = 10

                if settings.mail.SSL:
                    server = smtplib.SMTP_SSL(
                        settings.mail.SERVER,
                        settings.mail.PORT,
                        timeout=timeout,
                        context=ssl.create_default_context(),
                    )
                else:
                    server = smtplib.SMTP(
                        settings.mail.SERVER,
                        settings.mail.PORT,
                        timeout=timeout,
                    )

                server.ehlo()

                if settings.mail.TLS:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()

                if settings.mail.USE_CREDENTIALS:
                    server.login(
                        settings.mail.USERNAME,
                        settings.mail.PASSWORD,
                    )

                for email in to_emails:
                    message['To'] = email
                    server.sendmail(
                        settings.mail.FROM,
                        email,
                        message.as_string(),
                    )
                    del message['To']

                logger.info(
                    'Email успешно отправлен на: %s',
                    ', '.join(to_emails),
                )

            except Exception as e:
                logger.error('Ошибка отправки email: %s', e, exc_info=True)
                raise
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

        await asyncio.to_thread(send_sync)

    async def send_booking_confirmation(
        self,
        booking: Booking,
    ) -> None:
        """Отправка подтверждения бронирования пользователю."""
        if not booking.user.email:
            logger.warning(
                f'У пользователя {booking.user.username} '
                'нет email для отправки сообщения',
            )
            return

        subject = f'Подтвержение бронирования №{booking.id}'
        body = f"""
        <html>
        <body>
            <h2>Подтверждение бронирования</h2>
            <p>Спасибо за бронирование!</p>
            <p><strong>Номер бронирования:</strong> {booking.id}</p>
            <p><strong>Кафе:</strong> {booking.cafe.name}</p>
            <p><strong>Дата:</strong> {booking.booking_date}</p>
            <p><strong>Количество гостей:</strong> {booking.guest_number}</p>
            <p>Мы ждем вас!</p>
        </body>
        </html>
        """
        await self._send_email([booking.user.email], subject, body)

    async def send_booking_update(
        self,
        booking: Booking,
    ) -> None:
        """Отправка уведомления об изменении бронирования пользователю."""
        if not booking.user.email:
            logger.warning(
                f'У пользователя {booking.user.username} '
                'нет email для отправки сообщения',
            )
            return
        subject = f'Изменено бронирование №{booking.id}'
        body = f"""
        <html>
        <body>
            <h2>Изменение бронирования</h2>
            <p>Ваше бронирование было изменено.</p>
            <p><strong>Номер бронирования:</strong> {booking.id}</p>
            <p><strong>Кафе:</strong> {booking.cafe.name}</p>
            <p><strong>Новая дата:</strong> {booking.booking_date}</p>
            <p><strong>Количество гостей:</strong> {booking.guest_number}</p>
        </body>
        </html>
        """

        await self._send_email([booking.user.email], subject, body)

    async def notify_managers_and_admins(
        self,
        booking: Booking,
        subject: str,
        body: str,
    ) -> None:
        """Рассылка уведомления администраторам и менеджерам кафе."""
        managers_emails = [
            manager.email for manager in booking.cafe.managers if manager.email
        ]

        if not managers_emails:
            logger.warning(
                f'У менеджеров нет email.{booking.cafe.name}',
            )
            return

        html_body = f"""
        <html>
        <body>
            <h2>{subject}</h2>
            <p>{body}</p>
            <hr>
            <p><strong>Детали бронирования:</strong></p>
            <p><strong>Номер:</strong> {booking.id}</p>
            <p><strong>Кафе:</strong> {booking.cafe.name}</p>
            <p><strong>Клиент:</strong> {booking.user.username}
            ({booking.user.email})</p>
            <p><strong>Дата:</strong> {booking.booking_date}</p>
            <p><strong>Гостей:</strong> {booking.guest_number}</p>
        </body>
        </html>
        """

        await self._send_email(managers_emails, subject, html_body)
