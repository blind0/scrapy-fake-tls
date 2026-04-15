from __future__ import annotations

import base64
import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse

from scrapy import signals
from scrapy.http import HtmlResponse, Request
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet import defer

from scrapy_fake_tls.session import SessionPool

logger = logging.getLogger(__name__)

try:
    from scrapy.core.downloader.handlers.base import BaseDownloadHandler

    _MODERN_SCRAPY = True
except ImportError:
    from scrapy.core.downloader.handlers.http11 import (
        HTTP11DownloadHandler as BaseDownloadHandler,
    )

    _MODERN_SCRAPY = False


class AsyncCurlCffiDownloadHandler(BaseDownloadHandler):
    lazy = False

    def __init__(self, settings, crawler=None) -> None:

        super().__init__(crawler=crawler)

        self._settings = settings
        self._crawler = crawler
        self._default_impersonate: str = settings.get(
            "CURL_CFFI_IMPERSONATE", "chrome"
        )
        self._default_timeout: float = settings.getfloat(
            "DOWNLOAD_TIMEOUT", 60.0
        )
        verify_installed_reactor(
            "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
        )
        self._pool = SessionPool()
        logger.info(
            "CurlCffi handler initialised  "
            "(impersonate=%s, timeout=%s)",
            self._default_impersonate,
            self._default_timeout,
        )

    @classmethod
    def from_crawler(cls, crawler):
        handler = cls(crawler.settings, crawler=crawler)
        crawler.signals.connect(handler.close, signals.engine_stopped)
        return handler

    async def download_request(
        self, request: Request,
    ) -> defer.Deferred:
        return await self._download(request)

    async def close(self) -> None:
        logger.debug(
            "Closing %d curl_cffi sessions", self._pool.size,
        )
        await self._pool.close_all()

    async def _download(self, request: Request) -> HtmlResponse:
        impersonate: str = request.meta.get(
            "impersonate", self._default_impersonate,
        )
        proxy: Optional[str] = request.meta.get("proxy")
        proxy_headers: Optional[dict] = request.meta.get("proxy_headers")

        proxy_auth_raw = request.headers.pop(b"Proxy-Authorization", None)
        if proxy_auth_raw and proxy:
            raw = proxy_auth_raw[0] if isinstance(proxy_auth_raw, list) else proxy_auth_raw
            auth_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if auth_str.startswith("Basic "):
                creds = base64.b64decode(auth_str[6:]).decode("utf-8")
                parsed = urlparse(proxy)
                proxy = urlunparse(parsed._replace(netloc=f"{creds}@{parsed.netloc}"))

        session = self._pool.get_or_create(
            impersonate=impersonate,
            proxy=proxy,
            proxy_headers=proxy_headers,
        )

        headers = dict(request.headers.to_unicode_dict())
        timeout = request.meta.get(
            "download_timeout", self._default_timeout,
        )

        response = await session.request(
            method=request.method,
            url=request.url,
            headers=headers,
            data=request.body or None,
            timeout=timeout,
            allow_redirects=False,
        )

        resp_headers = Headers(response.headers.multi_items())
        resp_headers.pop("Content-Encoding", None)

        respcls = responsetypes.from_args(
            headers=resp_headers,
            url=response.url,
            body=response.content,
        )

        resp = respcls(
            url=response.url,
            status=response.status_code,
            headers=resp_headers,
            body=response.content,
            request=request,
        )

        return resp
