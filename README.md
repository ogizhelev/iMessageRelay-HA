# iMessageRelay for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Home Assistant integration for [iMessageRelay](https://github.com/ogizhelev/iMessageRelay) — an iOS app that exposes an HTTPS relay for sending iMessages from your homelab.

## Features

- **Auto-discovery** via mDNS — HA detects the app on the local network automatically
- **Notify service** — send iMessages (and file attachments) from automations
- **Sensors** — queue depth and runner state
- **Alias management** — add/remove recipient aliases via HA services

## Installation

### HACS (recommended)

1. In HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/ogizhelev/iMessageRelay-HA` as an **Integration**
3. Install **iMessage Relay** and restart Home Assistant

### Manual

Copy `custom_components/imessagerelay/` into your HA `config/custom_components/` directory and restart.

## Configuration

### Auto-discovery

With the iMessageRelay app running on your iPhone, HA will show a discovery notification. Confirm the host/port and enter your Bearer token.

### Manual

**Settings → Devices & Services → Add Integration → iMessage Relay**

| Field | Description |
|-------|-------------|
| Host | iPhone IP address (e.g. `10.10.6.195`) |
| Port | `8443` (default) |
| Bearer Token | Token from the app's Setup screen (default dev token: `homelab-dev-ozhe`) |

> The app uses a self-signed TLS certificate — HA connects with SSL verification disabled.

## Usage

### Send a message

```yaml
service: notify.imessage_relay
data:
  message: "Hello from Home Assistant"
  target:
    - alice
```

### Send with file attachment

```yaml
service: notify.imessage_relay
data:
  message: "See attached"
  target:
    - alice
  data:
    attach_name: "snapshot.jpg"
    attach_data: "{{ states('sensor.camera_snapshot_base64') }}"
```

### Add an alias

```yaml
service: imessagerelay.add_alias
data:
  name: alice
  contact: "+1234567890"
```

### Remove an alias

```yaml
service: imessagerelay.remove_alias
data:
  name: alice
```

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.imessage_relay_queue_depth` | Number of jobs waiting to be sent |
| `sensor.imessage_relay_runner_state` | `idle` / `dispatching` / `waitingForCallback` |

The runner state sensor also exposes `aliases` and `alias_count` as state attributes.
