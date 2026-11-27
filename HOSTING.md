# Hosting Plainly applications

Plainly 1.3.0 adds the first provider integration layer for separate Plainly app processes, public website binding, and simple message-driven Discord and Telegram bots.

This is a runtime integration guide, **not a claim that Plainly is a secure multi-tenant sandbox or a complete hosting control panel**.

## Supported app types

| App type | Current status | How it runs |
|---|---|---|
| Plainly programs | Supported | One Plainly interpreter process per app |
| Websites | Supported for small apps and prototypes | Plainly HTTP server behind your provider's HTTPS reverse proxy |
| Telegram bots | Basic text-message integration | Telegram Bot API long polling |
| Discord bots | Basic text-message integration | Discord Gateway WebSocket and message-create events |
| Binary .pbc programs | Compute-only subset | Plainly bytecode VM; website and bot APIs aren't included |

The Discord and Telegram integrations are intentionally small first versions. They process incoming text messages and send text replies. They don't implement slash commands, Discord interactions, reactions, attachments, voice, Telegram webhooks, or every platform API.

## Install the runtime

For a standard interpreter and website runtime:

~~~sh
python -m pip install .
~~~

For Discord and Telegram support, install the optional bot dependency too:

~~~sh
python -m pip install ".[bots]"
~~~

The bot extra uses the synchronous WebSocket client from [websockets](https://websockets.readthedocs.io/en/13.1/reference/sync/client.html). The project supports Python 3.8+, so the optional dependency is constrained below version 14; websockets 13.1 is the final websockets release supporting Python 3.8.

## Host a website

A site declares routes and starts its server in the Plainly source:

~~~plain
when someone visits the path home do
show a heading with the words Welcome to my site end words
show a paragraph with the words Built with Plainly end words
reply with the page
end when

start the server on port 8099
~~~

For local testing, run:

~~~sh
python plainly.py run site.plain
~~~

For a provider-managed deployment, set the port, bind address, and allowed hostname:

~~~sh
python plainly.py run site.plain --host 0.0.0.0 --port 8080 --allow-host app.example.com
~~~

The equivalent environment configuration is:

- **PORT:** port assigned to this app by the provider. It overrides the port written in the program.
- **PLAINLY_HOST:** bind address. The default remains 127.0.0.1.
- **PLAINLY_ALLOWED_HOSTS:** comma-separated hostnames or IP addresses accepted in the HTTP Host header.

When binding to a public interface, Plainly requires an explicit host allowlist. The provider should terminate HTTPS at its reverse proxy, route only the assigned domain to the app, and keep the app process private from direct public access where possible. The /healthz endpoint returns 200 ok for provider health checks.

The built-in server is a small HTTP server, not a full production web framework. It doesn't provide TLS, a database, static-asset management, advanced request limits, or a complete application server feature set.

## Run a Telegram bot

Create a bot through Telegram's BotFather and store its token as an app secret. Never put the token in source code or commit it to Git.

Example:

~~~plain
allow running a Telegram bot

when a Telegram message arrives do
let said be the message text
if said contains the words hello end words then
reply with the words Hello followed by the message author
otherwise
reply with the words You said followed by said
end if
end when

start the Telegram bot
~~~

Set the provider secret/environment variable named PLAINLY_SECRET_TELEGRAM_TOKEN.

Plainly uses Telegram's getUpdates long-polling method and advances the update offset after each update. Telegram long polling and webhooks are alternative update-delivery methods; this first integration uses long polling only. See the [Telegram Bot FAQ](https://core.telegram.org/bots/faq) and [Bot API](https://core.telegram.org/bots/api).

## Run a Discord bot

Create an application and bot in the Discord Developer Portal. Enable the **Message Content Intent** for the application before using message text. Discord classifies this as a privileged intent; applications that require verification may need approval. See [Discord Gateway Intents](https://discord.com/developers/docs/events/gateway#gateway-intents).

Example:

~~~plain
allow running a Discord bot

when a Discord message arrives do
let said be the message text
if said contains the words hello end words then
reply with the words Hello followed by the message author
end if
end when

start the Discord bot
~~~

Set the provider app secret/environment variable named PLAINLY_SECRET_DISCORD_TOKEN.

The first implementation listens for message-create events, ignores bot and self-authored messages, and sends replies to the same channel. It requests guild-message, direct-message, and message-content intents. Give the bot only the channel permissions it needs to read and send messages.

## Connect a hosting provider

The plainly_host.py module provides a small process adapter that a hosting provider can wrap in its own API, dashboard, database, and billing system:

~~~python
from plainly_host import PlainlyHost

runtime = PlainlyHost()

runtime.start(
    app_id="customer-app-123",
    program="main.plain",
    workdir="/srv/plainly/apps/customer-app-123",
    env={
        "PORT": "8080",
        "PLAINLY_HOST": "0.0.0.0",
        "PLAINLY_ALLOWED_HOSTS": "app.example.com",
    },
)

print(runtime.status("customer-app-123"))
print(runtime.logs("customer-app-123"))
runtime.stop("customer-app-123")
~~~

For a bot, inject its token through the env argument instead of the website variables. The adapter deliberately starts a child process with a reduced environment rather than copying every environment variable from the provider control plane.

The adapter exposes:

- start(app_id, program, workdir, env=None)
- status(app_id)
- logs(app_id, max_bytes=65536)
- stop(app_id, timeout=10)
- close()

The process registry is in memory. A provider must maintain its own persistent app records, re-create/reconcile processes after provider restarts, handle authentication and customer permissions, collect logs and metrics, and implement restart policies. This module is an integration building block, not a hosted HTTP API or an entire hosting platform.

## Isolation and production checklist

**Do not run untrusted customer code with only this adapter.** Each app process still has the operating-system permissions and network access granted to its service account. A separate process is not the same as a sandbox.

Before offering this to external customers, a provider must:

1. Run each app in a separate container or VM with a dedicated unprivileged identity and private workspace.
2. Enforce CPU, memory, process-count, disk, and execution limits outside Plainly.
3. Restrict filesystem mounts, network egress, metadata-service access, and access to provider control-plane services.
4. Inject only that app's secrets into its own process. Never pass provider-wide API keys, database credentials, or deployment secrets to customer apps.
5. Apply restart policies, health monitoring, log limits/retention, rate limits, and per-customer quotas.
6. Keep the public web server behind a managed HTTPS reverse proxy and allowlist only the app's assigned hostname.
7. Review and update dependencies, keep runtime images patched, and arrange an independent security review before accepting untrusted programs.

Plainly has not been independently audited. Its language-level file permissions and .pbc instruction limit are not OS security boundaries. Read SECURITY.md before designing a provider integration.
