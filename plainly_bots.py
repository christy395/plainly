#!/usr/bin/env python3
"""Optional network adapters for Plainly Discord and Telegram bots.

The adapters run one bot in one OS process. They are integrations, not a
multi-tenant security boundary. Providers must isolate each app externally.
"""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BotRuntimeError(RuntimeError):
    """A safe, user-facing bot integration error."""


def _json_request(url, payload=None, timeout=35, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", "User-Agent": "Plainly/1.3.0"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except HTTPError as exc:
        # Never include the URL here: Telegram URLs contain the bot token.
        if exc.code in (401, 403):
            raise BotRuntimeError("the bot token is not valid or the service rejected it") from None
        raise BotRuntimeError("the bot service returned HTTP %d" % exc.code) from None
    except (URLError, OSError, TimeoutError):
        raise BotRuntimeError("could not reach the bot service API") from None
    if len(raw) > 2 * 1024 * 1024:
        raise BotRuntimeError("the bot service response was too large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BotRuntimeError("the bot service returned an invalid response") from None
    if not isinstance(result, dict):
        raise BotRuntimeError("the bot service returned an unexpected response")
    return result


def _api_result(result, platform):
    if not result.get("ok"):
        description = str(result.get("description", "")).lower()
        if "token" in description or result.get("error_code") in (401, 403):
            raise BotRuntimeError("the %s bot token is not valid" % platform)
        raise BotRuntimeError("the %s bot API rejected a request" % platform)
    return result.get("result")


def run_telegram_bot(token, handler, stop_event=None):
    """Poll Telegram updates and pass text messages to handler(event, reply)."""
    if not token or not isinstance(token, str):
        raise BotRuntimeError("set PLAINLY_SECRET_TELEGRAM_TOKEN before starting the bot")
    api = os.environ.get("PLAINLY_TELEGRAM_API", "https://api.telegram.org").rstrip("/")
    offset = 0
    print("Plainly Telegram bot is starting.")
    while stop_event is None or not stop_event.is_set():
        query = urlencode({"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["message"])})
        result = _api_result(_json_request(
            "%s/bot%s/getUpdates?%s" % (api, token, query), timeout=35), "Telegram")
        if not isinstance(result, list):
            raise BotRuntimeError("the Telegram API returned an invalid updates list")
        for update in result:
            if not isinstance(update, dict):
                continue
            try:
                update_id = int(update.get("update_id"))
            except (TypeError, ValueError):
                continue
            offset = max(offset, update_id + 1)
            message = update.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("text"), str):
                continue
            author = message.get("from") or {}
            chat = message.get("chat") or {}
            if not isinstance(author, dict) or not isinstance(chat, dict) or author.get("is_bot"):
                continue
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            event = {
                "platform": "telegram",
                "text": message["text"],
                "author": str(author.get("first_name") or author.get("username") or author.get("id") or "Someone"),
                "channel": str(chat_id),
                "is_bot": False,
            }

            def reply(value, destination=chat_id):
                text = str(value)
                _api_result(_json_request(
                    "%s/bot%s/sendMessage" % (api, token),
                    {"chat_id": destination, "text": text},
                ), "Telegram")

            handler(event, reply)
    print("Plainly Telegram bot stopped.")


def _discord_request(api, token, channel_id, text):
    if not re.fullmatch(r"[0-9]{1,24}", str(channel_id)):
        raise BotRuntimeError("Discord supplied an invalid channel identifier")
    _json_request(
        "%s/channels/%s/messages" % (api.rstrip("/"), channel_id),
        {"content": str(text), "allowed_mentions": {"parse": []}},
        headers={"Authorization": "Bot " + token,
                 "User-Agent": "DiscordBot (https://github.com/christy395/plainly, 1.3.0)"},
    )


def _discord_session(token, handler, api, gateway, stop_event=None):
    if stop_event is not None and stop_event.is_set():
        return
    try:
        from websockets.sync.client import connect
    except ImportError:
        raise BotRuntimeError(
            "Discord bots need the optional dependency; install Plainly with: pip install plainly-lang[bots]"
        ) from None

    with connect(gateway, open_timeout=15, close_timeout=5, max_size=2 * 1024 * 1024) as ws:
        try:
            hello = json.loads(ws.recv(timeout=20))
        except (ValueError, TimeoutError):
            raise BotRuntimeError("Discord did not send a valid gateway greeting") from None
        if not isinstance(hello, dict) or hello.get("op") != 10 or not isinstance(hello.get("d"), dict):
            raise BotRuntimeError("Discord sent an unexpected gateway greeting")
        try:
            heartbeat_interval = float(hello["d"].get("heartbeat_interval", 45000)) / 1000.0
        except (TypeError, ValueError):
            raise BotRuntimeError("Discord sent an invalid heartbeat interval") from None
        if not 0.1 <= heartbeat_interval <= 300:
            raise BotRuntimeError("Discord sent an invalid heartbeat interval")

        sequence = None
        # GUILDS is deliberately not requested. Message and content intents
        # are enough for the message event used by this first integration.
        intents = (1 << 9) | (1 << 12) | (1 << 15)
        ws.send(json.dumps({"op": 2, "d": {
            "token": token,
            "intents": intents,
            "properties": {"os": "plainly", "browser": "plainly", "device": "plainly"},
        }}))

        # Discord requires the first heartbeat at a random point within the
        # interval. Every later heartbeat must be acknowledged before the next.
        next_heartbeat = time.monotonic() + heartbeat_interval * __import__("random").random()
        heartbeat_acknowledged = True
        self_user_id = None
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            now = time.monotonic()
            if now >= next_heartbeat:
                if not heartbeat_acknowledged:
                    raise RuntimeError("Discord heartbeat was not acknowledged")
                ws.send(json.dumps({"op": 1, "d": sequence}))
                heartbeat_acknowledged = False
                next_heartbeat = time.monotonic() + heartbeat_interval

            # Poll the stop event at least once per second so provider shutdowns
            # do not wait for a long Discord heartbeat interval.
            timeout = max(0.1, min(1.0, heartbeat_interval, next_heartbeat - time.monotonic()))
            try:
                raw = ws.recv(timeout=timeout)
            except TimeoutError:
                if stop_event is not None and stop_event.is_set():
                    return
                continue
            try:
                packet = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(packet, dict):
                continue

            op = packet.get("op")
            if op == 11:
                heartbeat_acknowledged = True
                continue
            if op == 1:
                if not heartbeat_acknowledged:
                    raise RuntimeError("Discord requested a heartbeat before acknowledging the previous one")
                ws.send(json.dumps({"op": 1, "d": sequence}))
                heartbeat_acknowledged = False
                next_heartbeat = time.monotonic() + heartbeat_interval
                continue
            if op in (7, 9):
                # Reconnect or invalid-session: close this connection and let
                # the outer loop establish a fresh Identify session.
                raise RuntimeError("Discord requested a gateway reconnect")
            if op == 0 and packet.get("s") is not None:
                sequence = packet["s"]
            if op != 0:
                continue

            event_name = packet.get("t")
            data = packet.get("d")
            if event_name == "READY" and isinstance(data, dict):
                user = data.get("user") or {}
                self_user_id = str(user.get("id", "")) if isinstance(user, dict) else None
                continue
            if event_name != "MESSAGE_CREATE" or not isinstance(data, dict):
                continue
            author = data.get("author") or {}
            if not isinstance(author, dict):
                continue
            author_id = str(author.get("id", ""))
            if author.get("bot") or (self_user_id and author_id == self_user_id):
                continue
            if not isinstance(data.get("content"), str):
                continue
            channel_id = data.get("channel_id")
            if channel_id is None:
                continue
            event = {
                "platform": "discord",
                "text": data["content"],
                "author": str(author.get("global_name") or author.get("username") or "Someone"),
                "channel": str(channel_id),
                "is_bot": False,
            }

            def reply(value, destination=channel_id):
                _discord_request(api, token, destination, value)

            handler(event, reply)

def run_discord_bot(token, handler, stop_event=None):
    """Connect to the Discord Gateway and handle message-create events."""
    if not token or not isinstance(token, str):
        raise BotRuntimeError("set PLAINLY_SECRET_DISCORD_TOKEN before starting the bot")
    api = os.environ.get("PLAINLY_DISCORD_API", "https://discord.com/api/v10")
    gateway = os.environ.get("PLAINLY_DISCORD_GATEWAY",
                             "wss://gateway.discord.gg/?v=10&encoding=json")
    print("Plainly Discord bot is starting.")
    delay = 2
    while stop_event is None or not stop_event.is_set():
        try:
            _discord_session(token, handler, api, gateway, stop_event)
            delay = 2
        except BotRuntimeError:
            raise
        except Exception as exc:
            # Never print the bot token or the platform API URL.
            name = type(exc).__name__
            detail = str(exc).replace(token, "[redacted]") if token else str(exc)
            print("Plainly Discord connection ended (%s: %s); reconnecting." %
                  (name, detail[:240]), file=__import__("sys").stderr, flush=True)
        if stop_event is not None and stop_event.wait(delay):
            break
        time.sleep(0 if stop_event is not None else delay)
        delay = min(delay * 2, 60)
    print("Plainly Discord bot stopped.")
