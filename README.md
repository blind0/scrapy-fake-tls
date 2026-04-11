# scrapy-fake-tls

Scrapy download handler с подменой TLS-отпечатков на базе библиотеки [curl_cffi](https://github.com/lexiforest/curl_cffi).

Является drop-in заменой для стандартного HTTP-обработчика Scrapy. Позволяет имитировать TLS/HTTP2-отпечатки (JA3/JA4, AKAMAI) реальных браузеров, делая запросы вашего парсера неотличимыми от трафика обычных пользователей.

## Особенности

- Подмена TLS-отпечатка: поддержка Chrome, Firefox, Safari, Edge и других браузеров.
- Ротация отпечатков на лету: изменение отпечатка для каждого отдельного запроса через `request.meta["impersonate"]`.
- Поддержка прокси: возможность передачи пользовательских заголовков для прокси-серверов (например, `Proxy-Authorization`).
- Асинхронная архитектура: нативная поддержка `asyncio` и пулинг соединений для высокой производительности.
- Работа "из коробки" без сложной настройки — используются оптимальные параметры по умолчанию.
- Полная совместимость со Scrapy версий от 2.11 до 2.15+.

## Установка

```bash
pip install scrapy-fake-tls
```

## Быстрый старт

Настройте проект Scrapy, добавив в `settings.py` следующие параметры:

```python
# Обязательно: использование асинхронного реактора
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Замена стандартных обработчиков загрузки
DOWNLOAD_HANDLERS = {
    "http": "scrapy_fake_tls.AsyncCurlCffiDownloadHandler",
    "https": "scrapy_fake_tls.AsyncCurlCffiDownloadHandler",
}

# Опционально: браузер для имитации по умолчанию (стандартно "chrome")
CURL_CFFI_IMPERSONATE = "chrome"
```

После этого все запросы будут использовать базовый TLS-отпечаток выбранного браузера (по умолчанию — Chrome последних версий).

## Параметры отдельных запросов (Request Meta)

Вы можете изменять отпечаток и другие параметры прямо в запросах.

```python
import scrapy

class MySpider(scrapy.Spider):
    name = "example"

    def start_requests(self):
        yield scrapy.Request(
            "https://tls.browserleaks.com/json",
            meta={"impersonate": "firefox"},
        )
        yield scrapy.Request(
            "https://tls.browserleaks.com/json",
            meta={"impersonate": "safari"},
        )
```

### Поддерживаемые браузеры

Существует возможность использовать общие сокращения (подставляющие актуальную версию) или указывать конкретную сборку:

| Общее имя | Доступные версии |
|---|---|
| `chrome` | `chrome99`, `chrome120`, `chrome131`, `chrome136`, `chrome142`, `chrome145` |
| `firefox` | `firefox133`, `firefox135`, `firefox144`, `firefox147` |
| `safari` | `safari15_3`, `safari17_0`, `safari18_0`, `safari18_4` |
| `edge` | `edge99`, `edge101` |

Указание общего имени (например, `"chrome"`) автоматически задействует последнюю поддерживаемую версию.

## Прокси и заголовки прокси

Для использования прокси и специфических заголовков, отправляемых только на прокси-узел (и недоступных конечному серверу), используйте `proxy_headers`:

```python
yield scrapy.Request(
    url,
    meta={
        "proxy": "http://user:pass@proxy-host:8080",
        "proxy_headers": {
            "Proxy-Authorization": "Basic dXNlcjpwYXNz",
            "X-Custom-Proxy-Header": "value",
        },
    },
)
```

Заголовки прокси передаются через механизм `CURLOPT_PROXYHEADER` в libcurl.

## Спецификация параметров Request.meta

| Ключ | Тип | Описание |
|---|---|---|
| `impersonate` | `str` | Отпечаток какого браузера имитировать (напр. "chrome") |
| `proxy` | `str` | URL прокси-сервера |
| `proxy_headers` | `dict` | Словарь дополнительных заголовков для прокси |
| `download_timeout` | `float` | Индивидуальный таймаут загрузки (в секундах) |
| `dont_redirect` | `bool` | Принудительный запрет на редиректы для запроса |

## Основные настройки (Settings)

| Параметр | По умолчанию | Описание |
|---|---|---|
| `CURL_CFFI_IMPERSONATE` | `"chrome"` | Глобальный отпечаток браузера |
| `DOWNLOAD_TIMEOUT` | `180` | Таймаут загрузки (в секундах) |

## Принцип работы и архитектура

1. При первом выполнении запроса с уникальным набором параметров `(impersonate, proxy, proxy_headers)`, обработчик инициализирует и кеширует новую сессию `curl_cffi.AsyncSession`.
2. Последующие запросы с тем же набором параметров используют кешированную сессию, переиспользуя TCP-соединения (Connection Pooling).
3. При завершении работы Scrapy-паука (остановка движка), все открытые сессии корректно закрываются.

## Зависимости

- Python >= 3.10
- Scrapy >= 2.11
- curl_cffi >= 0.7

## Лицензия

Распространяется на условиях лицензии MIT. 
