# Alarm Sound

Every alarm can ring audibly as well as visually. Sound is optional: an alarm with no speakers configured is a
silent, light-only alarm, and everything on this page — the speakers included — can be changed at any time in the
alarm's **Sound** section: open the Sunrise Alarm integration entry, choose **Edit alarm** next to the alarm, or
**Add alarm** to create a new one.

Sound is best-effort by design. If a speaker is offline or playback fails, the alarm still rings: the lights, the
notifications and the Snooze/Dismiss buttons are never affected by an audio problem.

## Playing on a speaker

1. In the **Sound** section, pick one or more **Speakers** — any media player in Home Assistant works: Sonos,
   Chromecast, an ESPHome speaker, a voice assistant device.
2. Pick **What to play** from the media browser — a track, a playlist, or a radio stream, the same way you would
   play it by hand.
3. Set the volumes. At the alarm time the speakers are set to the **Starting volume**, playback begins, and the
   volume rises to the **Final volume** over the **Volume ramp length**. Set the ramp length to zero to stay at the
   starting volume.

Playback stops when you snooze or dismiss the alarm. Snoozing and re-ringing starts it again from the starting
volume.

## Playing through Music Assistant

If the [Music Assistant](https://www.music-assistant.io/) integration is installed, the Sound section offers two
extra switches:

- **Play through Music Assistant** — the selection is resolved and played by Music Assistant instead of being sent
  straight to the speakers. Use this when your alarm media lives in a Music Assistant library or provider, for
  example "my Wake Up playlist, shuffled".
- **Radio mode** — after the selection ends, Music Assistant keeps playing similar music instead of stopping.

Pick the playlist or track from Music Assistant's own section of the media browser, then enable **Play through
Music Assistant**. The speakers you target must be players Music Assistant knows about.

If Music Assistant is later removed, the alarm falls back to playing the media directly and notes it in the log —
it never fails the ring.

## Using the phone as the speaker

No speaker in the bedroom? The companion app notification the alarm already sends can carry the sound.

### iPhone

**Ring through silent mode** (on by default when notification targets are configured) marks the notification as
critical, so it sounds even when the phone is muted or in Do Not Disturb. Switch it off in the alarm's Sound
section if you do not want that.

### Android

Android does not use the critical flag. Instead, the alarm's notifications arrive on a dedicated **Alarm ringing**
notification channel, and you choose the sound for that channel once:

1. Let the alarm ring once, so the channel exists.
2. On the phone, open **Settings** → **Apps** → **Home Assistant** → **Notifications**.
3. Find the **Alarm ringing** channel.
4. Set its **Sound** to the tone you want, and its importance to **Urgent** so it plays over Do Not Disturb if you
   want that.

The integration does not ship any sound files; the channel plays whatever tone you pick there.
