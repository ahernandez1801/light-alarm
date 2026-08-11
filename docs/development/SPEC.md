# Sunrise Alarm — Specification

What this integration is, what it must guarantee, and how audio gets added to it. Architectural rationale lives in
[`DECISIONS.md`](DECISIONS.md); this document is the product definition the code is measured against.

**Status:** implemented and green on the automated gates; never run against real hardware. See
[Status and honesty](#12-status-and-honesty).

---

## 1. Purpose

A wake-up alarm built out of the lights, speakers and phones a Home Assistant user already owns.

The lights fade up over a configurable sunrise that **finishes at the alarm time**, and the alarm then rings —
audibly, visibly, and on the phone — until a human stops it. Multiple independent alarms, each configured and
controlled on its own, with no automation YAML for the user to write.

### What it is not

- **Not a scheduler.** There are no weekday sets, calendars or holiday rules. An alarm repeats daily until switched
  off, and a per-alarm switch makes it fire once and disarm.
- **Not a media player.** It commands other integrations' `light` and `media_player` entities; it never implements
  playback itself.
- **Not a device integration.** Nothing is fetched from anywhere. See [Classification](#3-classification).

### Who it is for

One household, one Home Assistant instance, one person configuring it through the UI. Quality Scale target is Silver,
reaching for Gold where it costs little.

---

## 2. The guarantee

Everything else in this document is negotiable. This is not:

> **A ringing alarm must always have a reachable way to snooze or dismiss it.**

Four independent layers, listed in the order a half-asleep person meets them:

| Layer                        | Configuration       | Reaches the user                                                      |
| ---------------------------- | ------------------- | --------------------------------------------------------------------- |
| Companion app notification   | optional, per alarm | Lock screen, with Snooze and Dismiss buttons                          |
| Persistent notification      | none                | Every Home Assistant UI. Text only — the platform supports no buttons |
| `button` entities            | none                | The alarm's device page, any dashboard card                           |
| `snooze` / `dismiss` actions | user's automation   | A physical button, an NFC tag, a voice assistant                      |

Supporting requirements that follow from it:

- **The phone notification repeats** every `NOTIFY_REPEAT_MINUTES` while ringing, reusing one `tag` so it replaces
  rather than stacks. A notification swiped away by a half-asleep hand must not be the last control.
- **A restart must not strand the user.** The wake-up phase is persisted; a restart mid-sunrise resumes rather than
  leaving the lights at full with nothing left to dismiss.
- **Audio failure must never suppress the ringing state, the notifications or the buttons.** Sound is best-effort;
  the guarantee is not.

The guarantee stops where Home Assistant does. If the host is down, no layer helps — a hardware failsafe is the
user's decision, not this integration's.

---

## 3. Classification

| Manifest key          | Value        | Why                                                                   |
| --------------------- | ------------ | --------------------------------------------------------------------- |
| `integration_type`    | `helper`     | Values are produced from what Home Assistant already has, not fetched |
| `iot_class`           | `calculated` | The source is the clock plus the alarm configuration                  |
| `single_config_entry` | `true`       | Alarms are subentries of one entry, not entries of their own          |
| `requirements`        | none         | No API client, no third-party library                                 |

There is no `api/` package, no credentials, no reauth flow, and no `ConfigEntryNotReady` retry loop.

---

## 4. Structure — one integration, one device per alarm

```text
Config entry "Sunrise Alarm"
├── Subentry "Weekday"   → device → its own time, switches, buttons, sensors
├── Subentry "Weekend"   → device → …
└── Subentry "Guest room" → device → …
```

Each alarm is a config subentry owning exactly one device. Adding an alarm is **Add alarm** on the entry, not a second
setup flow. Entity unique IDs are `{subentry_id}_{key}`, so deleting and re-adding an alarm produces fresh entities
rather than resurrecting an old alarm's history.

### Layering

```text
entities  →  coordinator  →  scheduler  →  clock + subentry configuration
                    ↘  ramp / audio / notifier  →  light, media_player, notify services
```

Entities read `coordinator.data` and nothing else. The coordinator has **no update interval**: the scheduler advances
the state and publishes it with `async_set_updated_data`.

---

## 5. Timing semantics

**The configured time is when the alarm rings.** The sunrise runs up to it.

```text
alarm time − sunrise length        alarm time                     until dismissed
        │                              │                                │
        ├──────── sunrise ─────────────┤═══════ ringing ════════════════┤
   lights at dimmest            lights at full                     lights stay on
                                audio starts, ramps volume
                                notifications sent, repeating
```

- Ringing never begins before the configured time.
- The light transition is computed from **time remaining until the ring**, not from the configured sunrise length. A
  sunrise that starts late — resumed after a restart, compressed by a short snooze — still arrives at full on time.
- `sensor.<alarm>_next_alarm` reports the **ring** time.

### Phases

| Phase     | Meaning                            | `next_alarm` shows         |
| --------- | ---------------------------------- | -------------------------- |
| `idle`    | Armed and waiting, or disarmed     | Next ring, or unknown      |
| `ramping` | Sunrise in progress                | The ring it is heading for |
| `ringing` | Waiting to be snoozed or dismissed | Unknown                    |
| `snoozed` | Stopped, will run the cycle again  | The next ring              |

**Snooze:** lights back to dark, audio stopped, sunrise compressed into the snooze so the lights are at full when it
rings again after the snooze length.

**Dismiss:** the wake-up ends. **Lights are left on** — the user is awake and wants light — but **audio stops**. A
one-time alarm disarms itself here; otherwise it re-arms for the next day.

**No auto-stop.** A ringing alarm rings until a human stops it. Deliberate, and revisitable.

**One at a time.** An alarm whose sunrise is due while another is ramping, ringing or snoozed is skipped for that day.
Whichever timer Home Assistant runs first wins.

---

## 6. Configuration

Held in the subentry. The dialog shows three fields; everything with a sensible default sits in collapsed sections.

| Key              | Section  | Type                      | Default  |
| ---------------- | -------- | ------------------------- | -------- |
| `name`           | —        | text                      | required |
| `alarm_time`     | —        | time                      | `07:00`  |
| `lights`         | —        | light entities, multiple  | required |
| `ramp_minutes`   | Advanced | 1–60 minutes              | `15`     |
| `snooze_minutes` | Advanced | 1–60 minutes              | `9`      |
| `notify_targets` | Advanced | `mobile_app_*` services   | none     |
| _audio keys_     | Sound    | see [§9](#9-audio-design) | none     |

The Sound and Advanced sections only offer what the installation actually has: notification targets appear only when
`notify.mobile_app_*` services exist, Music Assistant options only when that integration is installed.

### Two ways to edit, neither of them YAML

- **The dialog** — Edit alarm on the device or entry page.
- **Entities** — `time.<alarm>_alarm_time`, `number.<alarm>_sunrise_length`, `number.<alarm>_snooze_length`, so an
  alarm can be changed from a dashboard card without opening Settings.

Both write to the same subentry. **Editing does not reload the entry**: the update listener reloads only when the set
of alarms changes, and otherwise re-arms in place. Without that, every dashboard edit would tear down and rebuild
every entity and cancel a wake-up in progress.

Changing the time cancels the pending cycle before scheduling the new one, so exactly one cycle is ever armed. An
alarm that is _currently_ ramping or ringing is not re-armed — the new time applies from its next cycle.

---

## 7. Entities

One set per alarm, on that alarm's device.

| Entity                          | Category | Purpose                    |
| ------------------------------- | -------- | -------------------------- |
| `switch.<alarm>_alarm`          | primary  | Armed or not               |
| `switch.<alarm>_only_once`      | config   | Fire once, then disarm     |
| `time.<alarm>_alarm_time`       | primary  | The ring time, editable    |
| `number.<alarm>_sunrise_length` | config   | Minutes                    |
| `number.<alarm>_snooze_length`  | config   | Minutes                    |
| `binary_sensor.<alarm>_ringing` | primary  | On while ringing           |
| `sensor.<alarm>_next_alarm`     | primary  | Timestamp of the next ring |
| `button.<alarm>_snooze`         | primary  | Snooze                     |
| `button.<alarm>_dismiss`        | primary  | Dismiss                    |

### Service actions

| Action                   | Target | Notes                                               |
| ------------------------ | ------ | --------------------------------------------------- |
| `ha_alarm_clock.snooze`  | device | Same code path as the button; for a physical button |
| `ha_alarm_clock.dismiss` | device | Same                                                |

---

## 8. State and persistence

`enabled` and `one_time` are user-writable runtime state; `phase` and `next_fire` are derived. All four are persisted
in a `Store`, **not** in the subentry — writing them into the subentry would reload the entry on every toggle and
cancel a wake-up in progress.

On startup the coordinator restores all four, and the scheduler resumes rather than re-arming:

| Restored phase | Action                                                                          |
| -------------- | ------------------------------------------------------------------------------- |
| `ringing`      | Ring again, notifications re-sent                                               |
| `ramping`      | Resume for the remaining time, without dropping the lights back to dark         |
| `snoozed`      | Keep the snooze, or start the cycle if it expired while Home Assistant was down |
| ring time past | Ring immediately                                                                |

---

## 9. Audio design

Not yet implemented. This is the specification for it.

### 9.1 What the user actually wants to hear

Three cases, and the design must serve all three without three separate mechanisms:

1. **A speaker in the bedroom** — Sonos, a Chromecast, an ESP speaker, a Google/Alexa device exposed as
   `media_player`. Plays a track, a radio stream, or a playlist.
2. **Music Assistant** — the user has a real library and wants "my Wake Up playlist, shuffled" or a radio-mode
   stream, resolved by Music Assistant rather than by a raw media URL.
3. **The phone itself** — no speaker involved. The companion app notification carries the sound, and on iOS must
   break through silent mode.

### 9.2 Configuration — a "Sound" section

| Key                         | Type                              | Shown when                          | Default |
| --------------------------- | --------------------------------- | ----------------------------------- | ------- |
| `audio_targets`             | `media_player` entities, multiple | always                              | none    |
| `audio_media`               | `MediaSelector`                   | always                              | none    |
| `audio_use_music_assistant` | boolean                           | `music_assistant.play_media` exists | `false` |
| `audio_radio_mode`          | boolean                           | Music Assistant enabled             | `false` |
| `audio_volume_start`        | 0–100 %                           | a target is chosen                  | `20`    |
| `audio_volume_end`          | 0–100 %                           | a target is chosen                  | `60`    |
| `audio_volume_minutes`      | 0–30 minutes                      | a target is chosen                  | `2`     |
| `phone_critical_sound`      | boolean                           | `notify_targets` is non-empty       | `true`  |

**`MediaSelector` is the key UX decision.** It renders Home Assistant's own media browser, which already lists every
source the user has — local media, TTS, radio browser, Spotify, and **Music Assistant's own library when that
integration is installed**. The user picks a playlist the same way they would to play it manually, instead of pasting
a URI. It returns `media_content_id` and `media_content_type`, which is exactly what both playback paths need.

Leaving `audio_targets` empty is valid and means a silent, light-only alarm — which is the current behaviour.

### 9.3 Playback

At ring time, after the phase becomes `ringing` and the notifications have gone out:

1. **Set the starting volume** — `media_player.volume_set` on every target at `audio_volume_start / 100`.
2. **Start playback**, on one of two paths:

   | Path            | Call                                                                                            |
   | --------------- | ----------------------------------------------------------------------------------------------- |
   | Music Assistant | `music_assistant.play_media` with `media_id`, `media_type`, `radio_mode`, targeting the players |
   | Plain           | `media_player.play_media` with `media_content_id`, `media_content_type`                         |

   Music Assistant is chosen when `audio_use_music_assistant` is on **and** the service exists at call time. If the
   integration has since been removed, fall back to `media_player.play_media` and log it — never fail the ring.

3. **Ramp the volume** from `audio_volume_start` to `audio_volume_end` over `audio_volume_minutes`, in steps on a
   timer. `media_player` has no transition parameter, so this is stepped rather than handed off.
4. **Stop on snooze or dismiss** — `media_player.media_stop`, falling back to `media_player.turn_off` for players
   that do not implement it. Cancel the volume ramp timer.

The volume ramp is a separate timer from the light sunrise and must be cancelled on snooze, dismiss, disable and
unload, alongside the notification repeat timer.

### 9.4 The phone as the speaker

No `media_player` involved. The notification already sent at ring time gains the fields that make it audible:

- **Android** — a dedicated notification `channel`, `importance: high`, `ttl: 0` and `priority: high` so a dozing
  phone wakes. The user sets a custom sound on that channel in the companion app's settings; the integration does not
  ship audio files.
- **iOS** — `push.sound` with `critical: 1` and a volume, which breaks through silent mode and Do Not Disturb. Gated
  behind `phone_critical_sound` because it is deliberately intrusive and needs the user's consent to be the default.

This path costs no new configuration beyond the one boolean, and it is the answer for a user with no bedroom speaker.

### 9.5 Failure handling

Audio is best-effort and must never take the alarm down with it:

- Every media call is wrapped; failures log at warning level and the wake-up continues.
- A missing or unavailable target player is not an error worth failing a ring over.
- If Music Assistant is configured but gone, fall back and log.
- The ringing state, the notifications and the buttons are unaffected by any of it.

### 9.6 Deliberately out of scope for the first audio release

TTS announcements ("good morning, 7 °C today"), per-day-of-week media, gradual track changes, audio during the
sunrise rather than at the ring, and any bundled sound files.

---

## 10. Implementation plan for audio

Each step ends green on `script/lint`, `script/type-check`, `script/hassfest` and `script/test`, and is offered as its
own commit.

| Step | Work                                                                                                                |
| ---- | ------------------------------------------------------------------------------------------------------------------- |
| A1   | `const.py` audio keys and defaults; `Sound` section in the alarm schema, conditional on installed integrations      |
| A2   | `utils/audio.py` — `async_start_audio`, `async_stop_audio`, the volume ramp timer, both playback paths              |
| A3   | Scheduler wiring: start audio in `_async_ring`, stop it in `async_snooze` / `async_dismiss` / `async_stop`          |
| A4   | Critical-sound fields in `utils/notifier.py`, behind `phone_critical_sound`                                         |
| A5   | Translations and icons for the Sound section                                                                        |
| A6   | Tests: both playback paths, the volume ramp, stop on snooze and dismiss, Music Assistant absent, target unavailable |
| A7   | `docs/user/` — how to point an alarm at Music Assistant, and how to set the Android channel sound                   |

Optional follow-ups once it works: a `number.<alarm>_volume` entity, and a `media_player` source selector entity so
the track can be changed from a dashboard the way the time already can.

---

## 11. Testing

| Area             | What must be covered                                                                            |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| Config flow      | Setup creates entry plus first alarm; second setup aborts; add and reconfigure subentry flows   |
| Timing           | Sunrise starts a sunrise length early; full brightness at the ring; ringing not before the time |
| Editing          | Time and duration entities write through; the old time no longer fires                          |
| Snooze / dismiss | Lights off on snooze, left on at dismiss; one-time alarm disarms itself                         |
| Restart          | A reload while ringing leaves it ringing                                                        |
| Notifications    | Actions carry the subentry ID; the action event snoozes                                         |
| Audio (A6)       | As listed in [§10](#10-implementation-plan-for-audio)                                           |

Automated tests supplement human review and real-device testing; they do not replace either. Nothing here is a claim
that the alarm has been verified against real hardware.

---

## 12. Status and honesty

What has actually been verified, and what has not:

| Gate                | Result                                                                         |
| ------------------- | ------------------------------------------------------------------------------ |
| `script/lint`       | Ruff format, Ruff check, yamllint and zizmor all pass                          |
| `script/test`       | 23 passed                                                                      |
| `script/hassfest`   | Passes, with one `config.title` translations warning still to look into        |
| `script/type-check` | **Never run** — Pyright needs Node, which is missing from the environment used |
| Shell formatting    | **Never run** — `shfmt` is missing from the same environment                   |

- The integration sets up, and every platform registers its entities. The subentry APIs that were written from
  documentation rather than installed source — creating the first alarm during setup, the subentry flow's helper
  methods, `async_add_entities(config_subentry_id=…)` — are confirmed working.
- Audio (§9–10, steps A1–A7) is implemented and covered by tests against mocked `media_player` services.
- **Nothing has been tested against real hardware.** No real light has been dimmed, no real speaker has played, and
  no real phone has received a notification. Every media, light and notify call in the suite is a mock. The automated
  gates prove the mocks agree with each other, not that a bedroom lamp wakes anybody up.
- `README.md` and `docs/user/` still describe the blueprint's example integration.
- No brand images. No release.

---

## 13. Open questions

- Should an edit to the alarm time cancel a wake-up that is already in progress? Current answer: no, the new time
  applies from the next cycle.
- Should there be an auto-stop after some number of minutes, as a safety net for an empty house? Current answer: no.
- Should the sunrise drive colour temperature warm → cool as well as brightness? Current answer: no, brightness only.
- Should a `media_player` that is already playing something be interrupted, or should the alarm refuse and fall back
  to the phone?
