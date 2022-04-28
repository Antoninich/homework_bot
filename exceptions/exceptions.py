class APIError(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        if self.message:
            return self.message
        else:
            return 'API вернул некорректный ответ'


class RequestError(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        text = (
            'При запросе API Яндекс.Практикум произошла ошибка: '
            f'{self.message}'
        )
        return text
