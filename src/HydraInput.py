#!/usr/bin/python

from conf_reader import conf_reader
import evdev
from evdev import InputDevice, UInput, ecodes as e
import numpy as np
import time
import threading
import os


conf = {}

# Empfindlichkeit der Mausbewegung (wie schnell die Maus auf Joystick-Bewegung reagiert)
MOUSE_SENSITIVITY = 5
SCROLL_SENSITIVITY = 1

# Schwellenwert für Joystick-Achsen (um "drift" zu vermeiden, wenn Joystick nicht ganz zentriert ist)
AXIS_DEADZONE = 1000

# daten der achsen [X, Y, RX, RY]
controller_axes = [0, 0, 0 ,0]

MOUSE_CAPABILITIES = {
    e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL],
    e.EV_KEY: evdev.ecodes.keys.keys(), # <-- NEU: Alle bekannten Tastencodes verwenden
    # e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE,
    #            e.KEY_UP, e.KEY_DOWN, e.KEY_RIGHT, e.KEY_LEFT,
    #            e.KEY_LEFTMETA, e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT,
    #            e.KEY_NEXTSONG, e.KEY_PREVIOUSSONG, e.KEY_PLAYPAUSE,
    #            e.KEY_VOLUMEUP, e.KEY_VOLUMEDOWN, e.KEY_MUTE, ],
}


BUTTON_MAPPING = {
    e.BTN_A: e.BTN_LEFT,    # A-Taste (Xbox) / X-Taste (PS) -> Linksklick
    e.BTN_B: e.BTN_RIGHT,   # B-Taste (Xbox) / Kreis-Taste (PS) -> Rechtsklick
    e.BTN_X: e.KEY_E,
    e.BTN_Y: e.KEY_R,

    e.BTN_START: e.KEY_ENTER,
    e.BTN_SELECT: e.BTN_RIGHT,
    e.BTN_MODE: e.BTN_RIGHT,
    167: e.BTN_RIGHT,       # Record

    "up": e.KEY_UP,
    "down": e.KEY_DOWN,
    "right": e.KEY_RIGHT,
    "left": e.KEY_LEFT,

    e.ABS_Z: e.KEY_LEFTCTRL,
    # e.BTN_TL: e.KEY_PREVIOUSSONG,
    e.BTN_TL: e.KEY_LEFTMETA,
    e.BTN_THUMBL: e.KEY_PAUSE,

    e.ABS_RZ: e.KEY_LEFTSHIFT,
    # e.BTN_TR: e.KEY_NEXTSONG,
    e.BTN_TR: e.KEY_ENTER,
    e.BTN_THUMBR: e.BTN_MIDDLE
}


ui = 0

def find_controller_device(partial_name='controller'):
    """Findet einen Controller-Gerätepfad basierend auf einem Teil des Namens."""
    devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
    for device in devices:
        if partial_name.lower() in device.name.lower() or 'joystick' in device.name.lower():
            print(f"Gefundenen Controller: {device.name} ({device.path})")
            return device.path
    print("Kein passender Controller gefunden. Bitte CONTROLLER_PATH manuell einstellen.")
    return None


def init_controller():
    if conf["CONTROLLER_PATH"] == '/dev/input/eventX':
        print("Versuche, einen Controller automatisch zu finden...")
        found_path = find_controller_device()
        if found_path:
            conf["CONTROLLER_PATH"] = found_path
        else:
            print("Fehler: Kein Controller-Pfad konfiguriert oder gefunden. Bitte einstellen.")
            exit(1)

def center_controller(dev, e, controller_axes):
    # Joystick-Achsenbereiche ermitteln
    absinfo_x = dev.absinfo(e.ABS_X)
    absinfo_y = dev.absinfo(e.ABS_Y)
    absinfo_rx = dev.absinfo(e.ABS_X)
    absinfo_ry = dev.absinfo(e.ABS_Y)
    
    # Standardwerte, falls Achseninfos nicht verfügbar sind (sollten aber bei Joysticks sein)
    min_x, max_x = absinfo_x.min, absinfo_x.max
    min_y, max_y = absinfo_y.min, absinfo_y.max
    min_rx, max_rx = absinfo_rx.min, absinfo_rx.max
    min_ry, max_ry = absinfo_ry.min, absinfo_ry.max
    center_x = (min_x + max_x) // 2
    center_y = (min_y + max_y) // 2
    center_rx = (min_rx + max_rx) // 2
    center_ry = (min_ry + max_ry) // 2

    print(f"Joystick X-Achse Bereich: {min_x} - {max_x}, Mitte: {center_x}")
    print(f"Joystick Y-Achse Bereich: {min_y} - {max_y}, Mitte: {center_y}")
    print(f"Empfindlichkeit: {MOUSE_SENSITIVITY}, Deadzone: {AXIS_DEADZONE}")

    # Aktuelle Joystick-Achsenwerte speichern
    controller_axes[0] = center_x
    controller_axes[1] = center_y
    controller_axes[2] = center_rx
    controller_axes[3] = center_ry


def move_mouse():
    global e, controller_axes, ui
    t = time.time()

    while True:
        time.sleep(0.005)
        if(time.time() >= t + 0.1):
            ui.write(e.EV_REL, e.REL_HWHEEL, int(np.interp(controller_axes[0], [-32768, 32768], [-1 * conf["SCROLL_SENSITIVITY"], conf["SCROLL_SENSITIVITY"]])))
            if conf["SCROLL_INVERT"]:
                ui.write(e.EV_REL, e.REL_WHEEL, int(np.interp(controller_axes[1], [-32768, 32768], [conf["SCROLL_SENSITIVITY"], -1 * conf["SCROLL_SENSITIVITY"]])))
            else:
                ui.write(e.EV_REL, e.REL_WHEEL, int(np.interp(controller_axes[1], [-32768, 32768], [-1 * conf["SCROLL_SENSITIVITY"], conf["SCROLL_SENSITIVITY"]])))
            t = time.time()

        ui.write(e.EV_REL, e.REL_X, int(np.interp(controller_axes[2], [-32768, 32768], [-1 * conf["MOUSE_SENSITIVITY"], conf["MOUSE_SENSITIVITY"]])))
        ui.write(e.EV_REL, e.REL_Y, int(np.interp(controller_axes[3], [-32768, 32768], [-1 * conf["MOUSE_SENSITIVITY"], conf["MOUSE_SENSITIVITY"]])))
        ui.syn()
 


def main():
    global conf
    global e, ui
    global controller_axes

    conf = conf_reader(os.path.expanduser("~/.config/HydraInput/HydraInput.conf"))

    init_controller()

    try:
        dev = evdev.InputDevice(conf["CONTROLLER_PATH"])
        print(f"Controller {dev.name} ({dev.path}) geöffnet.")
    except FileNotFoundError:
        print(f"Fehler: Controller unter {CONTROLLER_PATH} nicht gefunden.")
        print("Stelle sicher, dass der Pfad korrekt ist und du Berechtigungen hast (z.B. in der 'input'-Gruppe sein).")
        return
    except PermissionError:
        print(f"Fehler: Keine Berechtigung, Controller {CONTROLLER_PATH} zu öffnen.")
        print("Stelle sicher, dass du in der 'input'-Gruppe bist oder das Skript mit sudo ausführst (nicht empfohlen für Dauerbetrieb).")
        return

    center_controller(dev, e, controller_axes)

    # Virtuelles Mausgerät erstellen
    try:
        ui = UInput(MOUSE_CAPABILITIES, name='Controller_Mouse_Evdev', vendor=0x1234, product=0x5678, version=1)
        print("Virtuelle Maus 'Controller_Mouse_Evdev' erstellt.")
    except PermissionError:
        print("Fehler: Keine Berechtigung, /dev/uinput zu erstellen.")
        print("Stelle sicher, dass du in der 'input'-Gruppe bist und die Udev-Regel aktiv ist, oder führe mit sudo aus.")
        dev.close()
        return
    except Exception as e:
        print(f"Fehler beim Erstellen der virtuellen Maus: {e}")
        dev.close()
        return


    print("\nController-Maussteuerung aktiv. Drücke Strg+C, um zu beenden.")


    threading.Thread(target=move_mouse, daemon=True).start()

    try:
        # Events vom Controller lesen und verarbeiten
        for event in dev.read_loop():
            # Joystick-Achsen-Events verarbeiten
            if event.type == e.EV_ABS:
                if event.code == e.ABS_X:
                    controller_axes[0] = event.value
                elif event.code == e.ABS_Y:
                    controller_axes[1] = event.value
                elif event.code == e.ABS_RX:
                    controller_axes[2] = event.value
                elif event.code == e.ABS_RY:
                    controller_axes[3] = event.value
                
                # D-Pad
                elif event.code == e.ABS_HAT0X:
                    if event.value == 1:
                        action = BUTTON_MAPPING["right"]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()
                    elif event.value == -1:
                        action = BUTTON_MAPPING["left"]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()
                    else:
                        action = BUTTON_MAPPING["right"]
                        ui.write(e.EV_KEY, action, 0)
                        action = BUTTON_MAPPING["left"]
                        ui.write(e.EV_KEY, action, 0)
                        ui.syn()

                elif event.code == e.ABS_HAT0Y:
                    if event.value == -1:
                        action = BUTTON_MAPPING["up"]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()
                    elif event.value == 1:
                        action = BUTTON_MAPPING["down"]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()
                    else:
                        action = BUTTON_MAPPING["up"]
                        ui.write(e.EV_KEY, action, 0)
                        action = BUTTON_MAPPING["down"]
                        ui.write(e.EV_KEY, action, 0)
                        ui.syn()

                elif event.code == e.ABS_Z:
                    if event.value <= 10:
                        action = BUTTON_MAPPING[event.code]
                        ui.write(e.EV_KEY, action, 0)
                        ui.syn()
                    elif event.value >= 1000:
                        action = BUTTON_MAPPING[event.code]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()


                elif event.code == e.ABS_RZ:
                    if event.value <= 10:
                        action = BUTTON_MAPPING[event.code]
                        ui.write(e.EV_KEY, action, 0)
                        ui.syn()
                    elif event.value >= 1000:
                        action = BUTTON_MAPPING[event.code]
                        ui.write(e.EV_KEY, action, 1)
                        ui.syn()

            # Tasten-Events verarbeiten
            elif event.type == e.EV_KEY:
                action = BUTTON_MAPPING[event.code]
                ui.write(e.EV_KEY, action, event.value)
                ui.syn()

    except KeyboardInterrupt:
        print("\nBeendet durch Benutzer.")
    finally:
        if 'dev' in locals() and dev:
            dev.close()
            print(f"Controller {dev.name} geschlossen.")
        if 'ui' in locals() and ui:
            ui.close()
            print("Virtuelle Maus geschlossen.")

if __name__ == "__main__":
    main()
    
