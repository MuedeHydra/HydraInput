#!/usr/bin/env python3

from conf_reader import conf_reader
import evdev
from evdev import ecodes as e
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

# daten der achsen [X, Y, RX, RY, Z, RZ]
controller_axes = [[], [], [], [], 0, 0]

# for second layer
layer = 0

# controller modus (disable mouse and mapping)
controller_modus = 0
grabed: bool = False

MOUSE_CAPABILITIES = {
    e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL],
    e.EV_KEY: evdev.ecodes.keys.keys()
}


# init global var: ui
ui = 0


def read_conf():
    try:
        conf = conf_reader(os.path.expanduser("~/.config/HydraInput/HydraInput.conf"))
        return conf
    except FileNotFoundError:
        print("Could not open the configuration file:\t/home/username/.config/HydraInput/HydraInput.conf\n\tTrying to load the default configuration file.")

    conf = conf_reader(f"{os.path.dirname(__file__)}/HydraInput.conf")
    return conf


def encode_conf_def(data):
    di = {}
    key = 0
    action = 0
    for i in data:
        if i in ["up", "down", "left", "right"]:
            key = i
        else:
            key = getattr(e, i)

        if data[i] in ["SwitchMode", "SecondLayer"]:
            action = data[i]
        else:
            action = getattr(e, data[i])

        di[key] = action
    return di


def encode_conf(conf):
    conf["default_layer_encod"] = encode_conf_def(conf["default_layer"])
    conf["second_layer_encod"] = encode_conf_def(conf["second_layer"])
    return conf


def find_controller_device(partial_name='controller'):
    """Findet einen Controller-Gerätepfad basierend auf einem Teil des Namens."""
    devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
    for device in devices:
        if "touchpad" in device.name.lower():
            continue
        if "motion sensors" in device.name.lower():
            continue
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


def center_controller(dev, controller_axes):
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
    controller_axes[0] = [center_x, min_x, max_x]
    controller_axes[1] = [center_y, min_y, max_y]
    controller_axes[2] = [center_rx, min_rx, max_rx]
    controller_axes[3] = [center_ry, min_ry, max_ry]
    controller_axes[4] = dev.absinfo(e.ABS_Z).max
    controller_axes[5] = dev.absinfo(e.ABS_RZ).max


def move_mouse():
    global controller_axes, ui
    t = time.time()

    while True:
        time.sleep(0.005)
        if controller_modus:
            continue
        if time.time() >= t + 0.1:
            ui.write(e.EV_REL, e.REL_HWHEEL, int(np.interp(controller_axes[0][0], [controller_axes[0][1], controller_axes[0][2]], [-1 * conf["SCROLL_SENSITIVITY"], conf["SCROLL_SENSITIVITY"]])))
            if conf["SCROLL_INVERT"]:
                ui.write(e.EV_REL, e.REL_WHEEL, int(np.interp(controller_axes[1][0], [controller_axes[1][1], controller_axes[1][2]], [conf["SCROLL_SENSITIVITY"], -1 * conf["SCROLL_SENSITIVITY"]])))
            else:
                ui.write(e.EV_REL, e.REL_WHEEL, int(np.interp(controller_axes[1][0], [controller_axes[1][1], controller_axes[1][2]], [-1 * conf["SCROLL_SENSITIVITY"], conf["SCROLL_SENSITIVITY"]])))
            t = time.time()

        ui.write(e.EV_REL, e.REL_X, int(np.interp(controller_axes[2][0], [controller_axes[2][1], controller_axes[2][2]], [-1 * conf["MOUSE_SENSITIVITY"], conf["MOUSE_SENSITIVITY"]])))
        ui.write(e.EV_REL, e.REL_Y, int(np.interp(controller_axes[3][0], [controller_axes[3][1], controller_axes[3][2]], [-1 * conf["MOUSE_SENSITIVITY"], conf["MOUSE_SENSITIVITY"]])))
        ui.syn()


def grab_controller(dev, status=2):
    """status = 0 off, 1, on, 2 toggle"""
    global grabed
    if status == 2:
        status = not grabed
    if status:
        try:
            dev.grab()  # Gerät greifen, um Events zu unterdrücken
            print("Controller gegrabbt: Original-Inputs werden unterdrückt.")
            grabed = True
        except OSError as err:
            print(f"Warnung: Konnte Controller nicht grabben (Benötigt Root-Rechte oder CAP_SYS_RAWIO): {err}")
            print("Original-Controller-Inputs werden weiterhin an das System gesendet.")
            # Wenn grabben fehlschlägt, setzen wir den Modus zurück, um Verwirrung zu vermeiden
            grabed = False
    else:
        try:
            dev.ungrab()  # Gerät freigeben
            print("Controller freigegeben: Original-Inputs werden wieder an das System gesendet.")
            grabed = False
        except OSError as err:
            print(f"Warnung: Konnte Controller nicht freigeben: {err}")

    time.sleep(0.2)


def send_key(button, state):
    global layer, controller_modus

    # for PS controller
    if button == e.BTN_TL2:
        return
    if button == e.BTN_TR2:
        return

    if layer == 0:
        BUTTON_MAPPING = conf["default_layer_encod"]
    else:
        BUTTON_MAPPING = conf["second_layer_encod"]

    # print(BUTTON_MAPPING)
    action = BUTTON_MAPPING[button]

    if action == "SwitchMode":
        if state:
            controller_modus = not(controller_modus)
            print(f"{controller_modus = }")
    elif controller_modus:
        return
    elif action == "SecondLayer":
        layer = state
        print(f"{layer = }")
    else:
        # print(f"action = {action}\t | {state}")
        ui.write(e.EV_KEY, action, state)
        ui.syn()


def main():
    global conf
    global e, ui
    global controller_axes, grabed

    conf = read_conf()
    conf = encode_conf(conf)
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

    center_controller(dev, controller_axes)

    # Virtuelles Mausgerät erstellen
    try:
        ui = evdev.UInput(MOUSE_CAPABILITIES, name="Muede_Mouse_Keyboard", vendor=0x1234, product=0x5678, version=1)
        print("The virtual mouse 'Controller_Mouse_Keyboard_Evdev' has been created.")
    except PermissionError:
        print("Error: No authorization to create /dev/uinput.")
        print("Make sure you are in the ‘input’ group and the udev rule is active, or run with sudo (Not recomendet).")
        dev.close()
        return
    except Exception as e:
        print(f"Error when creating the virtual device: {e}")
        dev.close()
        return

    print("\nController mouse control active. Press Ctrl+C to exit.")

    threading.Thread(target=move_mouse, daemon=True).start()

    try:
        # Events vom Controller lesen und verarbeiten
        for event in dev.read_loop():
            if controller_modus == grabed:
                grab_controller(dev)

            # Joystick-Achsen-Events verarbeiten
            if event.type == e.EV_ABS:
                if event.code == e.ABS_X:
                    controller_axes[0][0] = event.value
                elif event.code == e.ABS_Y:
                    controller_axes[1][0] = event.value
                elif event.code == e.ABS_RX:
                    controller_axes[2][0] = event.value
                elif event.code == e.ABS_RY:
                    controller_axes[3][0] = event.value

                # D-Pad
                elif event.code == e.ABS_HAT0X:
                    if event.value == 1:
                        send_key("right", 1)
                    elif event.value == -1:
                        send_key("left", 1)
                    else:
                        send_key("right", 0)
                        send_key("left", 0)

                elif event.code == e.ABS_HAT0Y:
                    if event.value == -1:
                        send_key("up", 1)
                    elif event.value == 1:
                        send_key("down", 1)
                    else:
                        send_key("up", 0)
                        send_key("down", 0)

                elif event.code == e.ABS_Z:
                    if event.value <= 10:
                        send_key(event.code, 0)
                    elif event.value >= controller_axes[4] * 0.9:
                        send_key(event.code, 1)

                elif event.code == e.ABS_RZ:
                    if event.value <= 10:
                        send_key(event.code, 0)
                    elif event.value >= controller_axes[5] * 0.9:
                        send_key(event.code, 1)

            # Tasten-Events verarbeiten
            elif event.type == e.EV_KEY:
                send_key(event.code, event.value)

    except KeyboardInterrupt:
        print("\nBeendet durch Benutzer.")
    finally:
        if grabed:
            grab_controller(dev, 0)

        if 'dev' in locals() and dev:
            dev.close()
            print(f"Controller {dev.name} geschlossen.")
        if 'ui' in locals() and ui:
            ui.close()
            print("Virtuelle Maus geschlossen.")


if __name__ == "__main__":
    main()
