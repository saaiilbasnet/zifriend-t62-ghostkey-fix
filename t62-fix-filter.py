#!/usr/bin/env python3
"""
Workaround for Zifriend T62 hardware fault: Right Arrow and B are
electrically shorted on the PCB - pressing EITHER one sends both
KEY_RIGHT and KEY_B in the same USB HID report (confirmed via evtest).
There's no way to tell them apart in software, so Right Arrow is
unusable as-is.

This grabs the T62 exclusively and re-emits its keys through a virtual
device with one change: KEY_RIGHT is always dropped (never forwarded),
and KEY_RIGHTALT is remapped to send KEY_RIGHT instead. Real B still
works normally since it's forwarded untouched.

Run as: sudo python3 t62-fix-filter.py
Stop with Ctrl+C - releases the real device back to normal.
"""
import evdev
from evdev import InputDevice, UInput, ecodes as e, categorize

SOURCE_NAME = "SEMICO USB Keyboard"

def find_devices():
    """The T62 exposes duplicate nodes under the same name - grab every
    one that has arrow keys, since the real events can come from any
    of them depending on the HID interface Linux picked."""
    found = []
    for path in evdev.list_devices():
        dev = InputDevice(path)
        if dev.name == SOURCE_NAME and e.EV_KEY in dev.capabilities():
            if e.KEY_RIGHT in dev.capabilities()[e.EV_KEY]:
                found.append(dev)
    if not found:
        raise RuntimeError(f"Could not find input device named {SOURCE_NAME!r}")
    return found

def filter_device(dev, ui):
    dev.grab()
    try:
        for ev in dev.read_loop():
            if ev.type == e.EV_KEY and ev.code == e.KEY_RIGHT:
                continue  # Right Arrow is fused with B - unusable, always drop
            if ev.type == e.EV_KEY and ev.code == e.KEY_RIGHTALT:
                ui.write(e.EV_KEY, e.KEY_RIGHT, ev.value)
                ui.syn()
                continue
            ui.write_event(ev)
    finally:
        dev.ungrab()

def main():
    devices = find_devices()
    for d in devices:
        print(f"Grabbing {d.path} ({d.name})")

    # one shared virtual output, capabilities merged from all nodes
    cloned_caps = {}
    for d in devices:
        for ktype, kcodes in d.capabilities().items():
            if ktype == e.EV_SYN:
                continue
            cloned_caps.setdefault(ktype, set())
            cloned_caps[ktype].update(kcodes if isinstance(kcodes, list) else [kcodes])
    cloned_caps = {k: sorted(v) for k, v in cloned_caps.items()}
    ui = UInput(cloned_caps, name=SOURCE_NAME + " (filtered)")

    import threading
    threads = [threading.Thread(target=filter_device, args=(d, ui), daemon=True) for d in devices]
    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        pass
    finally:
        for d in devices:
            try:
                d.ungrab()
            except OSError:
                pass
        ui.close()
        print("Released devices, filter stopped.")

if __name__ == "__main__":
    main()
