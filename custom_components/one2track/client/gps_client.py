"""GPS Client for One2Track API."""

from __future__ import annotations

import json
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from aiohttp import ClientResponse, ClientSession

from .client_types import AuthenticationError, One2TrackConfig, TrackerDevice

if TYPE_CHECKING:
    from typing import Any

_LOGGER: Logger = getLogger(__name__)

CONFIG = {
    "login_url": "https://www.one2trackgps.com/auth/users/sign_in",
    "base_url": "https://www.one2trackgps.com/",
    "device_url": "https://www.one2trackgps.com/users/%account%/devices",
    "session_cookie": "_iadmin"
}


class GpsClient:
    """Client for One2Track GPS tracking API."""

    config: One2TrackConfig
    cookie: str
    csrf: str
    account_id: str | None
    session: ClientSession | None

    def __init__(
        self, config: One2TrackConfig, session: ClientSession | None = None
    ) -> None:
        """Initialize the GPS client."""
        self.config = config
        self.account_id = config.id  # might be empty
        self.session = session
        self.cookie = ""
        self.csrf = ""

    def set_account_id(self, account_id: str) -> None:
        """Set the account ID."""
        self.account_id = account_id

    async def get_csrf(self) -> None:
        """Get CSRF token from login page."""
        login_page = await self.call_api(CONFIG["login_url"])
        if login_page.status == 200:
            html = await login_page.text()
            self.csrf = self.parse_csrf(html)
            _LOGGER.debug(f"[pre-login] Found this CSRF: {self.csrf}")
            self.cookie = self.parse_cookie(login_page)
            _LOGGER.debug(f"[pre-login] Found this cookie: {self.cookie}")
        else:
            _LOGGER.warning(f"[pre-log] failed pre-login. response code: {login_page.status}")
            raise AuthenticationError("Login page unavailable")

    async def call_api(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        allow_redirects: bool = True,
        use_json: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> ClientResponse:
        """Call the One2Track API."""
        headers = dict(extra_headers) if extra_headers else {}
        cookies = {'accepted_cookies': 'true'}

        header_keys = {key.lower() for key in headers}

        if data is not None and "content-type" not in header_keys:
            headers["content-type"] = "application/x-www-form-urlencoded"

        if use_json:
            headers["content-type"] = "application/json"
            headers["Accept"] = "application/json"

        if self.cookie:
            cookies['_iadmin'] = self.cookie

        _LOGGER.debug('[http] %s %s %s', url, headers, cookies)

        if self.session is None:
            self.session = ClientSession()

        self.session.cookie_jar.clear()

        if data is not None:
            return await self.session.post(url,
                                           data=data,
                                           headers=headers,
                                           allow_redirects=allow_redirects,
                                           cookies=cookies
                                           )
        else:
            return await self.session.get(url, headers=headers, allow_redirects=allow_redirects, cookies=cookies)

    def parse_cookie(self, response) -> str:
        cookie = ""
        if 'Set-Cookie' in response.headers:
            cookie = response.headers['Set-Cookie']

        if cookie:
            return response.headers['Set-Cookie'].split(CONFIG["session_cookie"])[1].split(";")[
                0].replace("=", "")
        else:
            _LOGGER.warning(f"No new cookie found {self.cookie} was the old cookie")
            return ""

    def parse_csrf(self, html) -> str:
        return html.split("name=\"csrf-token\" content=\"")[1].split("\"")[0]

    async def login(self) -> None:
        """Log in to One2Track."""
        login_data = {
            "authenticity_token": self.csrf,
            "user[login]": self.config.username,
            "user[password]": self.config.password,
            "gdpr": "1",
            "user[remember_me]": "1",
        }
        response = await self.call_api(CONFIG["login_url"], data=login_data, allow_redirects=False)

        _LOGGER.debug("[login] Status: %s", response.status)

        # login is successful when we get a fresh cookie
        if response.status == 302 and "Set-Cookie" in response.headers:
            _LOGGER.debug("[login] login success!")
            self.cookie = self.parse_cookie(response)
            _LOGGER.debug(f"[login] Found this cookie: {self.cookie}")
            _LOGGER.debug(f"[login] Found this redirect: {response.headers['Location']}")
        else:
            _LOGGER.warning(f"[gps] failed to login. response code: {response.status}")
            raise AuthenticationError("Invalid username or password")

    async def get_user_id(self) -> str:
        """Get user account ID from One2Track."""
        response = await self.call_api(CONFIG["base_url"], allow_redirects=False)
        url = response.headers["Location"]
        account_id = url.split("/")[4]
        _LOGGER.debug("[install] extracted %s from %s", account_id, url)
        self.set_account_id(account_id)
        return account_id

    async def install(self) -> str:
        """Complete installation flow and return account ID."""
        await self.get_csrf()
        await self.login()
        account_id = await self.get_user_id()
        return account_id

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid login, cookie, and account id."""
        if not self.cookie or not self.csrf:
            await self.get_csrf()
            await self.login()

        if not self.account_id:
            await self.get_user_id()

    async def update(self) -> list[TrackerDevice] | None:
        """Update and return device data."""
        if self.cookie:
            _LOGGER.debug("already logged in, continue... %s", self.cookie)
        else:
            _LOGGER.debug("renew login")
            await self._ensure_authenticated()

        try:
            devices = await self.get_device_data()
            return devices

        except AuthenticationError:
            _LOGGER.warning("login failed")
            self.cookie = ""
            self.csrf = ""
            # hopefully next update loop login will be better

    async def get_device_data(self) -> list[TrackerDevice] | None:
        """Get device data from One2Track API."""
        url = CONFIG["device_url"].replace("%account%", self.account_id)
        response = await self.call_api(url, use_json=True)
        rawjson = await response.text()

        _LOGGER.debug("[devices] raw json: %s %s", response.status, rawjson)

        if response.status == 200:
            try:
                devices = json.loads(rawjson)
                return list(map(lambda x: x['device'], devices))
            except Exception as e:
                _LOGGER.error("[one2track][error][update] Cannot parse JSON: %s | %s", rawjson, e)
                return None
        else:
            _LOGGER.error(f"[one2track][error][update] Cant get devices updated: code: %s message: %s", response.status,
                          rawjson)
            self.cookie = ""
            self.csrf = ""
            # hopefully next update loop login will be better
            return []

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()

    async def send_device_message(
        self, device_id: str, message: str, title: str | None = None
    ) -> None:
        """Send a text message to a One2Track device."""
        await self._ensure_authenticated()

        messages_url = f"https://www.one2trackgps.com/devices/{device_id}/messages"
        response = await self.call_api(messages_url)

        if response.status != 200:
            body = await response.text()
            _LOGGER.error("[notify] Cannot access message page %s: %s - %s", device_id, response.status, body)
            raise AuthenticationError("Unable to access message page")

        page_html = await response.text()
        try:
            csrf_token = self.parse_csrf(page_html)
        except Exception as ex:
            _LOGGER.error("[notify] Could not parse CSRF token %s", ex)
            raise AuthenticationError("CSRF token missing") from ex

        message_data = {
            "utf8": "✓",
            "authenticity_token": csrf_token,
            "device_message[message]": message
        }

        headers = {
            "X-CSRF-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest"
        }

        response = await self.call_api(
            messages_url,
            data=message_data,
            extra_headers=headers
        )

        if response.status != 200:
            body = await response.text()
            _LOGGER.error(
                "[notify] Failed sending message to %s. Code: %s Body: %s",
                device_id,
                response.status,
                body[:200]
            )
            raise AuthenticationError("Failed to send message")

        _LOGGER.info("[notify] Message sent to %s: %s", device_id, message)
