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

If the [Music Assistant](https://www.music-assistant.io/) integration is installed, the Sound section offers a
playlist picker and two extra switches:

- **Music Assistant playlist** — a dropdown of the playlists in your Music Assistant library, read from Music
  Assistant when the dialog opens. Choosing one is all you need: it is played instead of **What to play**, and you
  do not have to switch anything else on. You can also type any Music Assistant URI, for example
  `spotify://playlist/aabbccddeeff`.
- **Play through Music Assistant** — for a selection you picked in **What to play** rather than from the playlist
  dropdown, resolve and play it through Music Assistant instead of sending it straight to the speakers.
- **Radio mode** — after the selection ends, Music Assistant keeps playing similar music instead of stopping.

### Pick the Music Assistant copy of your speaker

> ⚠️ This is the one thing that silently stops the music.

Music Assistant creates **its own media player entity** for every player it controls, and it can only play through
those. Most speakers therefore appear twice in the **Speakers** list: once from the integration that found them
(Sonos, Chromecast, ESPHome) and once from Music Assistant. Only the Music Assistant one works for playlists.

If you pick the wrong one, Home Assistant matches no player, plays nothing, and reports no error. The alarm's
dialog now refuses to save a playlist without a Music Assistant speaker and tells you why, and an alarm already
saved that way writes a warning to the log at ring time naming the speakers it could not use.

To tell them apart, hover the entity in the Speakers dropdown and check which integration it belongs to, or look
the entity up under **Settings** → **Devices & services** → **Entities**.

If Music Assistant is later removed, the alarm falls back to playing **What to play** directly and notes it in the
log — it never fails the ring.

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
