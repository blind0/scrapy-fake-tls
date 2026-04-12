from __future__ import annotations

import logging
from typing import Dict, Optional

from curl_cffi import CurlOpt
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)


class SessionPool:
    def __init__(self) -> None:
        self._sessions: Dict[str, AsyncSession] = {}

    def get_or_create(
        self,
        impersonate: str,
        proxy: Optional[str] = None,
        proxy_headers: Optional[dict] = None,
    ) -> AsyncSession:
        session_key = self._build_key(impersonate, proxy, proxy_headers)

        if session_key not in self._sessions:
            curl_options = self._build_curl_options(proxy_headers)
            session = AsyncSession(
                impersonate=impersonate,
                proxy=proxy,
                curl_options=curl_options,
            )
            self._sessions[session_key] = session
            logger.debug(
                "Created new session: impersonate=%s proxy=%s key=%s",
                impersonate,
                proxy,
                session_key,
            )

        return self._sessions[session_key]

    async def close_all(self) -> None:
        sessions, self._sessions = self._sessions, {}
        for key, session in list(sessions.items()):
            try:
                await session.close()
                logger.debug("Closed session: %s", key)
            except Exception:
                logger.debug("Failed to close session: %s", key, exc_info=True)

    @property
    def size(self) -> int:
        return len(self._sessions)

    @staticmethod
    def _build_key(
        impersonate: str,
        proxy: Optional[str],
        proxy_headers: Optional[dict],
    ) -> str:
        proxy_key = proxy or "direct"
        if proxy_headers:
            ph_key = str(sorted(proxy_headers.items()))
        else:
            ph_key = "no_ph"
        return f"{impersonate}|{proxy_key}|{ph_key}"

    @staticmethod
    def _build_curl_options(
        proxy_headers: Optional[dict],
    ) -> Optional[dict]:
        if not proxy_headers:
            return None
        header_list = [f"{k}: {v}".encode() for k, v in proxy_headers.items()]
        return {CurlOpt.PROXYHEADER: header_list}
