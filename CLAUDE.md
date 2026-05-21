# CLAUDE.md

Project-specific notes for future Claude sessions. README is the user-facing
intro; this file is the things you'd waste hours rediscovering.

## What this is

Two-service Docker Compose stack against a single TP-Link M8550 5G router:

- `collector/` — Python (`uv`), polls the router every 5s via
  `tplinkrouterc6u`'s `TPLinkEXClient`, writes to `data/m8550.db` (SQLite WAL).
- `web/` — Next.js 15, reads the same DB read-only, polls its own `/api/*`.

Both containers run as uid 1000; the data dir is bind-mounted into each.

## Workflow

- `docker compose up -d --build` rebuilds and restarts both services. Web on
  `localhost:3000`. Test live behavior here, not in a dev server.
- Collector tests: `cd collector && .venv/bin/python -m pytest`.
- Web type/lint: `cd web && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint app components lib`.
  `pnpm` isn't on `$PATH`; call binaries from `node_modules/.bin/` directly.
- **Vitest currently won't start** on the host — its `rolldown` dep needs
  `node:util.styleText` (Node 22+) and the system Node is older. TS + ESLint
  cover correctness for now; if you need behaviour tests for web code, write
  them as collector-side or end-to-end (via curl + sqlite inspection).
- Run live router probes from `recon/` (or inline scripts) with:
  ```bash
  cd collector && set -a && source ../.env && set +a && .venv/bin/python -c '...'
  ```
  `M8550_PASSWORD` lives in `.env` (gitignored).

## Router quirks worth remembering

### EX-firmware attr serialization is broken

`tplinkrouterc6u/client/ex.py:281` serializes ActItem attrs with:

```python
attrs_str = ', '.join([attr if ':' in attr else f'"{attr}":""' for attr in act.attrs])
```

So `attrs=["PageNumber=1"]` becomes the malformed JSON key `"PageNumber=1":""`
— the router silently rejects the SET (errorcode 9007) and your call appears
to succeed-but-do-nothing. The upstream MR client uses `=` because MR firmware
has a different request format; the EX firmware is JSON and needs proper
quoting.

**Pass attrs pre-quoted as JSON fragments so the serializer leaves them
intact**: `attrs=['"PageNumber":"1"']`, `attrs=['"unread":"0"']`. The presence
of `:` is what triggers the "keep as-is" branch. This is the workaround we use
in `LibRouterClient.list_sms`, `_locate_sms`, and `mark_sms_read`.

### SMS inbox pagination

Router paginates `DEV2_LTE_SMS_RECVMSGENTRY` at **8 messages/page**. Use:

```
SET DEV2_LTE_SMS_RECVMSGBOX attrs=['"PageNumber":"<n>"']
GL  DEV2_LTE_SMS_RECVMSGENTRY attrs=['index','from','content','receivedTime','unread']
```

Walk pages 1..N until the GL returns an empty list, then stop. `GET
DEV2_LTE_SMS_RECVMSGBOX` returns `totalNumber` if you want to sanity-check.

### SMS deletion is not available

The EX firmware rejects `del` on `DEV2_LTE_SMS_RECVMSGENTRY` with errorcode
71011 **and** drops the HTTP status line from the response (the body is just
the chunked-encoded encrypted JSON). To `requests` that surfaces as
`BadStatusLine('40\r\n')` — looks like a transport bug, is actually an
application-level rejection. `SET deleted=1`, `OP …`, `SET deleteMsg=…` on
`RECVMSGBOX`, and every `/cgi/sms_*` path we tried also fail. Captured with a
raw socket call if you want to verify.

So "delete" in this app is a **local soft-hide** via the `sms_hidden(sms_id)`
table — `list_sms()` (both collector and web) LEFT JOINs it out. The button is
labelled "Hide" with a tooltip explaining the firmware limit. Don't try to
make it a real delete without first finding what the M8550 web UI itself does
(probably via SPA-bundled JS we couldn't fetch without proper SPA auth).

### Single-session contention

M8550 allows **one** logged-in session at a time. The Tether mobile app will
kick our session. `LibRouterClient` arms a 5-minute `_kicked_until` backoff
when this happens — we deliberately do *not* immediately re-auth, because that
would just kick Tether right back. Don't shorten the backoff without a real
reason.

A second flavour of session loss surfaces as TCP RST (`OSError`) instead of
401. We tolerate `stale_session_threshold` (default 4) consecutive `OSError`s
before treating it as session-lost and triggering one reauth attempt.

#### Polite login: probe `/cgi/getBusy` first

Before any `authorize()` call (startup + the two reauth paths in
`snapshot()`), the collector hits `POST /cgi/getBusy` **unauthenticated**.
Semantics observed on this firmware:

| State                                | Response                                            |
|--------------------------------------|-----------------------------------------------------|
| Nobody is logged in                  | `200` body has `isLogined=0` and `isBusy=0`         |
| Someone else is logged in            | `200` body has `isLogined=1` and `isBusy=1`         |
| **Phantom lock** (firmware bug)      | `200` body has `isLogined=0` and `isBusy=1`         |
| We probed with our own JSESSIONID    | `406 Not Acceptable`                                |

We treat the slot as busy **only when both** `isLogined=1` and `isBusy=1`.
The "phantom lock" state is a firmware bug: the previous session ended but
`isBusy` never cleared. Originally we only inspected `isBusy=1`, which stranded
the collector for 10h+ waiting on a session that didn't exist. There's
nothing to be polite to when `isLogined=0`, so we authorise.

When busy, we arm the cooldown and raise `AuthError` instead of calling
`authorize()` — exactly the polite behaviour the router's own web UI
implements via its "kick existing session?" popup. The probe is module-level
`_router_busy(host)` in `router.py`; tests inject a `busy_probe` callable into
`LibRouterClient` to avoid live network calls, plus unit tests cover the
parser directly so the phantom case can't regress.

The login endpoint itself **does not** signal contention — `Action: "1"` is
the only working value and it always succeeds, silently kicking any prior
session. The popup in the web UI is implemented client-side; without the
getBusy pre-check we'd kick Tether every time the collector restarts. Don't
remove the getBusy probe without a fundamentally different detection scheme.

### `unread`, `pageNumber`, `totalNumber` on RECVMSGBOX

`GET DEV2_LTE_SMS_RECVMSGBOX` returns `unreadNumber` — but it only counts
unread messages that are accessible (on currently-loaded page), not the full
inbox. Don't trust it as the unread badge source; count via `sms_messages` in
the local DB instead.

## DB schema gotchas

- `data/m8550.db` is shared. Collector holds the write handle. Web has two:
  the read-only main handle (`web/lib/db.ts`) and a write handle scoped to
  things only the web side touches — `push_subscriptions`
  (`web/lib/push-db.ts`) and `sms_actions` (`web/lib/sms-db.ts`).
- `Store.replace_sms()` does a full DELETE+INSERT mirror of the router inbox
  each poll. It also (a) preserves `sms_hidden` tombstones across polls, and
  (b) clears tombstones whose id is no longer on the router so future
  slot-reuse doesn't silently hide a new message.
- Push-notify `new_messages` calculation deliberately filters out hidden ids,
  so a hidden-but-still-on-router message doesn't ping every re-mirror.

## Action queue (user-initiated SMS mutations)

Web → `sms_actions(id, sms_id, action, created_at)` → collector drains in
`Poller._process_sms_actions()` at the **start of every 5s tick**. Two
actions:

- `mark_read` → `router.mark_sms_read(id)` (walks pages to locate slot,
  SET unread=0).
- `delete` → `store.hide_sms_local(id)` — no router call.

Transient errors (`AuthError`/`ConnectionError`) keep the row queued; anything
else logs and drops the row so a poisoned action can't loop forever. (Earlier
we *did* call `router.delete_sms` for the delete action; that produced a
runaway retry storm because the firmware rejects DEL with a transport-level
error. If you re-introduce a router-side path, make sure failure modes
fast-fail rather than re-queue.)

## Testing patterns

- Collector tests fake the underlying `tplinkrouterc6u` client with a
  `MagicMock` for `ActItem` and a `side_effect` list for `req_act` (see
  `test_router_lib.py`). Each Python-level `req_act` call consumes one entry.
- The fake's `ActItem` returns generic MagicMocks for ActItem instances —
  inspect `fake_lib.ActItem.call_args_list` to assert what acts were created
  (operation, oid, stack, attrs). The `req_act` arg list itself is opaque.
- `FakeRouter` in `test_poller.py` mirrors the `RouterClient` protocol —
  extend it when you add new router methods.

## Recent context

- The SMS feature shipped in three steps: pagination fix (`4d7b324`),
  mark-read + hide actions (`aec62d1`), web pagination at 8/page (`9ff6369`).
  Earlier delete attempts left ~17 stuck "delete" actions in `sms_actions`
  during testing — they're cleared. If you see a stuck queue again, clear it
  with `DELETE FROM sms_actions` (rare, only happens if a router call
  permanently fails for some reason).
- The user is in Lithuania (LABAS carrier — Bitė Lietuva). Test SMS often come
  through as Lithuanian-language promotional messages.
