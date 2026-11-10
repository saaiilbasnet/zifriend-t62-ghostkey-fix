# Zifriend T62 ghost-key fix

Workaround for a hardware fault on the Zifriend T62 mechanical keyboard
(USB HID reports it as "SEMICO USB Keyboard", vendor:product `1a2c:6d5b`)
where **Right Arrow and B are electrically shorted on the PCB**.

Pressing either key sends both `KEY_RIGHT` and `KEY_B` in the same USB
HID report. Confirmed with `evtest` on both keys individually — this is
not a software remap, OS key-repeat bug, or a firmware macro; it's a
short between the two keys' matrix lines on the board itself.

```
Event: type 1 (EV_KEY), code 106 (KEY_RIGHT), value 1
Event: type 1 (EV_KEY), code 48  (KEY_B), value 1
-------------- SYN_REPORT ------------
```

Same pair, every time, no matter which of the two physical keys you
press. Because both codes land in the identical report, there is no
way to tell "the user pressed Right Arrow" apart from "the user pressed
B" in software — a filter that cleans up one necessarily eats the
other too.

## The fix

Since the two keys can't be disambiguated, this script:

- Grabs the keyboard's input device(s) exclusively via `evdev`.
- Always drops `KEY_RIGHT` (it's unusable, so no real B press is lost).
- Remaps `KEY_RIGHTALT` to emit `KEY_RIGHT` instead, giving you a
  working Right Arrow on a spare key.
- Passes every other key through untouched, including real `B`.

The T62 exposes two duplicate `evdev` nodes under the same name; the
script grabs both, since which one carries the live events can vary.

Unplugging the keyboard kills its device node, so the filter exits
(on purpose, with a non-zero status) rather than hang on a dead
device. Combined with `Restart=always` in the systemd service and a
30-second retry loop while looking for the keyboard, replugging it
brings the fix back automatically within a couple of seconds, no
manual restart needed.

## Usage

Requires `python3-evdev`:

```
sudo apt install -y python3-evdev
sudo python3 t62-fix-filter.py
```

Ctrl+C releases the device back to normal.

## Run on boot (systemd)

```
sudo cp t62-fix-filter.py /opt/t62-fix-filter.py
sudo cp t62-fix-filter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now t62-fix-filter.service
```

## Adapting to other boards/keys

If you have a different board with a similar matrix short between two
keys, change `SOURCE_NAME` to your device's name (see
`cat /proc/bus/input/devices`), and swap `KEY_RIGHT`/`KEY_RIGHTALT` for
whichever pair applies to you.

## Diagnosis tools, if you suspect the same issue

```
cat /proc/bus/input/devices      # find your device's event node
sudo evtest /dev/input/eventN    # watch raw key events
```

If pressing one key always produces two keycodes in the same
`SYN_REPORT`, regardless of which of the two keys you physically
press, you likely have the same kind of matrix short — and the same
fix (drop one key, remap a spare key to replace it) will apply.
