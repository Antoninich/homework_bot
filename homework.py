from http import HTTPStatus
import logging
import os
import sys
import time

from dotenv import load_dotenv
from exceptions.exceptions import APIError
import requests
import telegram
from telegram.error import Unauthorized

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO)
logging.StreamHandler(sys.stdout)
_log = logging.getLogger(__name__)

old_message = ''
old_verdict = ''


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.

    Параметры:
        bot: Bot
        message: str

    """
    global old_message
    if old_message != message:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        old_message = message
        _log.info('Сообщение успешно отправлено в Telegram')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.

    Параметры:
        current_timestamp: int

    Возвращаемое значение:
        Ответ API, преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    status_code = response.status_code
    if status_code != HTTPStatus.OK:
        raise APIError(f'Некорректный ответ от API {status_code}')

    response = response.json()
    return response


def check_response(response):
    """Проверяет ответ API на корректность.

    Параметры:
        response: dict

    Возвращаемое значение:
        Список домашних работ (он может быть и пустым), доступный в ответе API
        по ключу 'homeworks'.
    """
    try:
        homeworks = response.get('homeworks')
    except AttributeError:
        raise TypeError('API вернул некорректный ответ')

    if homeworks is None:
        raise APIError
    elif type(homeworks) != list:
        raise APIError
    elif response is None:
        raise APIError
    elif not homeworks:
        _log.debug('Нет отправленных работ')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент из списка
    домашних работ.

    Параметры:
        homework: list

    Возвращаемое значение:
        Подготовленную для отправки в Telegram строку, содержащую один из
        вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status is None:
        raise APIError('API не вернул статус')
    if homework_name is None:
        raise KeyError('API не вернул имя работы')
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise APIError(f'API вернул неизвестный статус {homework_status}')

    verdict = HOMEWORK_STATUSES[homework_status]

    global old_verdict
    if old_verdict != verdict:
        old_verdict = verdict
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        _log.debug('Статус работы не изменился')


def check_tokens():
    """Проверяет доступность переменных окружения.

    Возвращаемое значение:
        True, если переменные присутствуют.
        False, если переменных нет.
    """
    env_vars = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for env in env_vars:
        if env is None:
            text = (
                f'Отсутствует обязательная переменная окружения {env}.'
                'Программа принудительно остановлена.'
            )
            _log.critical(text)
            return False
    return True


def main():
    """Основная логика работы программы.
    Последовательность действий:
        - Сделать запрос к API.
        - Проверить ответ.
        - Если есть обновления — получить статус работы из обновления и
        отправить сообщение в Telegram.
        - Подождать некоторое время и сделать новый запрос.
    """
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        _log.debug(f'Подключён к боту Telegram {bot.name}')
    except Unauthorized:
        raise SystemExit('С таким токеном TELEGRAM_TOKEN бот не существует')

    current_timestamp = int(time.time())

    while True:
        try:
            if not check_tokens():
                text = (
                    'Отсутствует обязательная переменная окружения.'
                    'Подробности в логе.'
                    'Программа принудительно остановлена.'
                )
                raise SystemExit(text)
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                messages = parse_status(homeworks[0])
                if messages:
                    send_message(bot, messages)

            current_timestamp = current_timestamp + RETRY_TIME
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            _log.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        except KeyboardInterrupt:
            sys.exit('Выполнение программы прервано')
        else:
            _log.debug('Запущен новый цикл проверки')


if __name__ == '__main__':
    main()
