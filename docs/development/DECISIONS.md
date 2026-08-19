# Architectural and Design Decisions

This document records significant architectural and design decisions made during the development of this integration.

## Format

Each decision is documented with:

- **Date:** When the decision was made
- **Context:** Why this decision was necessary
- **Decision:** What was decided
- **Rationale:** Why this approach was chosen
- **Consequences:** Expected impacts and trade-offs

> [!NOTE]
> Guidance on _when_ a decision is worth recording here, and a copy-ready entry template, lives in the
> [`ha-planning`](../../.agents/skills/ha-planning/SKILL.md) agent skill.

---

## Decision Log

### Use DataUpdateCoordinator for All Data Fetching

**Date:** 2025-11-29 (Template initialization)

**Context:** The integration needs to fetch data from an external API and share it with multiple entities. Home Assistant provides several patterns for this.

**Decision:** Use `DataUpdateCoordinator` from `homeassistant.helpers.update_coordinator` as the central data management component.

**Rationale:**

- Provides built-in support for update intervals and error handling
- Automatic retry with exponential backoff
- Shared data access prevents duplicate API calls
- Standard pattern recommended by Home Assistant
- Entities automatically become unavailable when coordinator fails

**Consequences:**

- All entities must inherit from `CoordinatorEntity`
- Single update interval applies to all entities
- Data is fetched even if no entities are enabled
- Coordinator manages entity lifecycle and availability

---

### Separate API Client from Coordinator

**Date:** 2025-11-29 (Template initialization)

**Context:** The coordinator needs to fetch data, but business logic should be separated from data transport.

**Decision:** Implement API communication in separate `api/client.py` module, coordinator only orchestrates updates.

**Rationale:**

- Separation of concerns: transport vs. orchestration
- Easier to test API client in isolation
- Simpler to swap API implementation if needed
- Clearer error handling boundaries

**Consequences:**

- Additional abstraction layer
- Coordinator depends on API client
- API client raises custom exceptions for error translation

---

### Platform-Specific Directories

**Date:** 2025-11-29 (Template initialization)

**Context:** Integration supports multiple platforms (sensor, binary_sensor, switch, etc.).

**Decision:** Each platform gets its own directory with individual entity files.

**Rationale:**

- Clear organization as integration grows
- Easier to find specific entity implementations
- Supports multiple entities per platform cleanly
- Follows Home Assistant Core pattern

**Consequences:**

- More files/directories than single-file approach
- Platform `__init__.py` must import and register entities
- Slightly more initial setup overhead

---

### EntityDescription for Static Metadata

**Date:** 2025-11-29 (Template initialization)

**Context:** Entities have static metadata (name, icon, device class) that doesn't change.

**Decision:** Use `EntityDescription` dataclasses to define static entity metadata.

**Rationale:**

- Declarative and easy to read
- Type-safe with dataclasses
- Recommended Home Assistant pattern
- Separates static configuration from dynamic behavior

**Consequences:**

- Each entity type needs an EntityDescription
- Dynamic entities need custom handling
- Static and dynamic properties clearly separated

---

## Future Considerations

### State Restoration

**Status:** Not yet implemented

Consider implementing state restoration for switches and configurable settings to maintain state across Home Assistant restarts when the external device is unavailable.

### Multi-Device Support

**Status:** Not yet implemented

Current architecture assumes single device per config entry. If multi-device support is needed, coordinator data structure will need redesign to map device ID → data.

### Polling vs. Push

**Status:** Uses polling

Currently implements polling-based updates. If the API supports webhooks or WebSocket, consider implementing push-based updates for real-time responsiveness.

---

## Scaffolding Decisions

### No API Client — the Integration Computes Its Values

**Date:** 2026-08-11 (Scaffolding)

**Context:** Sunrise Alarm has no device and no endpoint. Its values come from the clock, the alarm configuration, and
the light entities Home Assistant already has.

**Decision:** Delete the `api/` package. Classify the integration as `integration_type: helper` and
`iot_class: calculated`. The coordinator keeps its place in the layering but has no update interval — the scheduler
advances the state and publishes it with `async_set_updated_data`.

**Rationale:**

- There is nothing to fetch, so a client would only wrap a calculation.
- Entities still read `coordinator.data` and never reach past it, so the layering the rest of the project assumes is
  intact.
- A plain state listener was rejected: several alarms share one wake-up cycle, and the entities need a single copy of
  that state.

**Consequences:**

- No credentials, no reauth flow, and no `ConfigEntryAuthFailed` path.
- Setup cannot fail for connectivity reasons, so there is no `ConfigEntryNotReady` retry loop either.
- Adding audio later means adding a phase to the scheduler, not a client.

---

### One Config Entry, One Subentry per Alarm

**Date:** 2026-08-11 (Scaffolding)

**Context:** The integration has to hold an arbitrary number of alarms, each with its own time, lights and entities,
and each editable after setup.

**Decision:** `single_config_entry: true`. The setup dialog creates the entry together with its first alarm, and every
further alarm is a config subentry of type `alarm` with its own device. Alarms are edited through the subentry
reconfigure dialog rather than through `time` and `number` entities.

> **Partially superseded (2026-08-18):** the one-device-per-alarm half is replaced by "One Shared Device, Alarms
> Named Through a Placeholder" below. The single entry and the subentry-per-alarm shape stand.

**Rationale:**

- One device per alarm groups that alarm's switches, buttons and sensors where a user looks for them.
- Subentries give "Add alarm" and "Edit alarm" in the UI without a second setup flow.
- Dialog-based editing is cheaper to build now, and adding editing entities later is additive — no entity ID changes.

**Consequences:**

- Every platform's `async_setup_entry` iterates subentries and passes `config_subentry_id` to `async_add_entities`.
- The unique ID of an entity is `{subentry_id}_{key}`; deleting and re-adding an alarm produces new entities.
- Changing a subentry reloads the whole entry, which resets any wake-up in progress.

---

### Switch Positions Persist in a Store, Not in the Subentry

**Date:** 2026-08-11 (Scaffolding)

**Context:** "Alarm enabled" and "only once" are switches the user flips at runtime, but they still have to survive a
restart. The obvious home for them is the subentry data next to the alarm's time and lights.

**Decision:** Keep them in a `homeassistant.helpers.storage.Store` owned by the coordinator, saved with
`async_delay_save`.

**Rationale:**

- Writing them into the subentry would reload the config entry on every toggle, cancelling a wake-up in progress.
- The subentry holds configuration the user typed; these two are live state.

**Consequences:**

- Deleting an alarm leaves its stored pair behind until the next save rewrites the file; nothing reads it.
- Tests that assert persistence need `hass.async_block_till_done()` past the save delay.

---

### One Shared Device, Alarms Named Through a Placeholder

**Date:** 2026-08-18

**Context:** One device per alarm scattered the integration across as many device pages as there are alarms, and
`integration_type: helper` filed the entry under Helpers — the developer looked for one integration with the alarms
inside it and could not find the edit dialogs.

**Decision:** All entities sit on one device owned by the config entry (`identifiers={(DOMAIN, entry_id)}`), each
carrying its alarm's name through the `alarm_name` translation placeholder. Entities are no longer registered with
`config_subentry_id`. `integration_type` becomes `service`. The snooze and dismiss actions still target the device and
resolve to every alarm of its entry; the scheduler ignores the idle ones, so they act on the active wake-up.

**Rationale:**

- One page listing every alarm's entities matches how the household actually uses it.
- Per-alarm names must come from a placeholder because every alarm now shares the device name.
- Device targeting for the actions stays valid — "one at a time" means the active alarm is unambiguous.

**Consequences:**

- Breaking pre-release: entity IDs gain the `sunrise_alarm_` device prefix. No migration, per the pre-1.0 policy.
- Deleting a subentry no longer cascades through a device; `_async_remove_stale_registry_entries` in `__init__.py`
  removes orphaned registry entries (and any leftover per-alarm device) on the reload that follows.
- Unique IDs are unchanged (`{subentry_id}_{key}`).

---

## Decision Review

These decisions should be reviewed periodically (suggested: quarterly or when major features are added) to ensure they still serve the integration's needs.
