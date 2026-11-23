# iMessageRelay for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Home Assistant integration for [iMessageRelay](https://github.com/ogizhelev/iMessageRelay) — an iOS app that exposes an HTTPS relay for sending iMessages from your homelab.

## Features

- **Auto-discovery** via mDNS — HA detects the app on the local network automatically
- **Send iMessages** from automations via `imessagerelay.send_message`
- **File attachments** — attach images or files as base64 payloads
- **Sensors** — queue depth, runner state, and active aliases
- **Alias management** — add/remove recipient aliases via HA services

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/ogizhelev/iMessageRelay-HA` as an **Integration**
3. Install **iMessage Relay** and restart Home Assistant

### Manual

Copy `custom_components/imessagerelay/` into `config/custom_components/` and restart.

## Configuration

### Auto-discovery

With the iMessageRelay app running on the same network as HA, a discovery notification appears automatically. Confirm and enter your Bearer token.

### Manual

**Settings → Devices & Services → Add Integration → iMessage Relay**

| Field | Description |
|-------|-------------|
| Host | iPhone IP address (e.g. `10.10.4.124`) |
| Port | `8443` (default) |
| Bearer Token | Token from the app (default dev token: `homelab-dev-ozhe`) |
| Verify SSL certificate | Leave unchecked for the app's bundled self-signed cert |

## Services

### `imessagerelay.send_message`

Send an iMessage to one or more recipients by alias name.

```yaml
service: imessagerelay.send_message
data:
  message: "Hello from Home Assistant"
  target:
    - alice
```

Multiple recipients:

```yaml
service: imessagerelay.send_message
data:
  message: "Alert: motion detected"
  target:
    - alice
    - bob
```

With a file attachment — read and encoded automatically from the HA host filesystem:

```yaml
service: imessagerelay.send_message
data:
  message: "See attached snapshot"
  target:
    - alice
  attach_file_path: /config/www/snapshot.jpg
```

With a base64-encoded attachment (e.g. from a camera template sensor):

```yaml
service: imessagerelay.send_message
data:
  message: "See attached snapshot"
  target:
    - alice
  attach_name: "snapshot.jpg"
  attach_data: "{{ states('sensor.camera_snapshot_base64') }}"
```

| Field | Required | Description |
|-------|----------|-------------|
| `message` | Yes | Text body |
| `target` | Yes | List of alias names |
| `attach_file_path` | No | Path to a file on the HA host — read and base64-encoded automatically |
| `attach_name` | No | Filename for a manually base64-encoded attachment |
| `attach_data` | No | Base64-encoded file content (paired with `attach_name`) |

> `attach_file_path` takes precedence over `attach_name`/`attach_data` when both are provided.

---

### `imessagerelay.add_alias`

Map a short name to an iMessage-enabled address (phone number or Apple ID email). Creates or overwrites an existing alias.

```yaml
service: imessagerelay.add_alias
data:
  name: alice
  contact: "+1234567890"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Short alias name used in `target` |
| `contact` | Yes | Phone number or Apple ID email |

---

### `imessagerelay.remove_alias`

Remove a recipient alias by name.

```yaml
service: imessagerelay.remove_alias
data:
  name: alice
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Alias name to remove |

## Entities

| Entity | State | Attributes |
|--------|-------|------------|
| `sensor.imessage_relay_connection` | `connected` / `disconnected` | `host`, `port`, `response_time_ms`, `last_seen` |
| `sensor.imessage_relay_queue_depth` | Number of jobs waiting | `uptime`, `last_callback_at` |
| `sensor.imessage_relay_runner_state` | `idle` / `dispatching` / `waitingForCallback` | — |
| `sensor.imessage_relay_aliases` | Number of active aliases | Each alias as `name: contact` |

The **Connection** sensor always reports a state (`connected`/`disconnected`) rather than going unavailable, so automations can react to the server going offline. It updates on every coordinator poll (default 30 s).
