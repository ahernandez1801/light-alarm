"""Constants for ha_alarm_clock."""

from enum import StrEnum
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ha_alarm_clock"

SUBENTRY_TYPE_ALARM = "alarm"
SECTION_ADVANCED = "advanced"
SECTION_SOUND = "sound"
DEFAULT_ENTRY_TITLE = "Sunrise Alarm"
MANUFACTURER = "Sunrise Alarm"

CONF_ALARM_TIME = "alarm_time"
CONF_AUDIO_MEDIA = "audio_media"
CONF_AUDIO_RADIO_MODE = "audio_radio_mode"
CONF_AUDIO_TARGETS = "audio_targets"
CONF_AUDIO_USE_MUSIC_ASSISTANT = "audio_use_music_assistant"
CONF_AUDIO_VOLUME_END = "audio_volume_end"
CONF_AUDIO_VOLUME_MINUTES = "audio_volume_minutes"
CONF_AUDIO_VOLUME_START = "audio_volume_start"
CONF_GATE_ENTITY = "gate_entity"
CONF_GATE_STATE = "gate_state"
CONF_LIGHTS = "lights"
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_PHONE_CRITICAL_SOUND = "phone_critical_sound"
CONF_RAMP_MINUTES = "ramp_minutes"
CONF_SNOOZE_MINUTES = "snooze_minutes"

DEFAULT_AUDIO_VOLUME_END = 60
DEFAULT_GATE_STATE = "home"
DEFAULT_AUDIO_VOLUME_MINUTES = 2
DEFAULT_AUDIO_VOLUME_START = 20
DEFAULT_RAMP_MINUTES = 15
DEFAULT_SNOOZE_MINUTES = 9

MAX_AUDIO_VOLUME_MINUTES = 30
MAX_RAMP_MINUTES = 60
MAX_SNOOZE_MINUTES = 60

MUSIC_ASSISTANT_DOMAIN = "music_assistant"
MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA = "play_media"

STORAGE_KEY = f"{DOMAIN}.alarm_state"
STORAGE_VERSION = 1

ATTR_ALARM_ENABLED = "enabled"
ATTR_ALARM_ONE_TIME = "one_time"
ATTR_ALARM_PHASE = "phase"
ATTR_ALARM_NEXT_FIRE = "next_fire"

NOTIFY_DOMAIN = "notify"
NOTIFY_SERVICE_PREFIX = "mobile_app_"
NOTIFY_CLEAR_MESSAGE = "clear_notification"
NOTIFY_REPEAT_MINUTES = 3
NOTIFY_CRITICAL_VOLUME = 1.0

EVENT_MOBILE_APP_ACTION = "mobile_app_notification_action"
ACTION_SNOOZE_PREFIX = "HA_ALARM_CLOCK_SNOOZE_"
ACTION_DISMISS_PREFIX = "HA_ALARM_CLOCK_DISMISS_"

# Notification text cannot come from translations/en.json: neither persistent_notification
# nor the companion app's notify services accept a translation key.
NOTIFY_TITLE = "Alarm ringing"
NOTIFY_MESSAGE = "{name} is ringing. Snooze or dismiss it to stop the alarm."
NOTIFY_ACTION_SNOOZE_TITLE = "Snooze"
NOTIFY_ACTION_DISMISS_TITLE = "Dismiss"


class AlarmPhase(StrEnum):
    """Where one alarm is in its wake-up cycle."""

    IDLE = "idle"
    RAMPING = "ramping"
    RINGING = "ringing"
    SNOOZED = "snoozed"
