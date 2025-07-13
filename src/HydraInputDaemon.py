import numpy as np
import threading
import socket
import time
import os
import select
import evdev
from evdev import ecodes as e

from conf_reader import conf_reader


conf = {}

# daten der achsen [X, Y, RX, RY, Z, RZ]
controller_axes = [[0, -1, 1], [0, -1, 1], [0, -1, 1],[0, -1, 1],[0, -1, 1],[0, -1, 1]]

# for second layer
layer = 0

# controller modus (disable mouse and mapping)
controller_modus = 0
grabed: bool = False

# thread status
thread_status = [0]

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

    conf = conf_reader(f"{os.path.dirname(__file__)}/../HydraInput.conf")
    return conf


def encode_conf_def(data):
    di = {}
    key = 0
    action = 0
    for i in data:
        if i in ["up", "down", "left", "right",
                 "WHEEL_UP", "WHEEL_DOWN", "WHEEL_RIGHT", "WHEEL_LEFT"]:
            key = i
        else:
            key = getattr(e, i)

        if data[i] in ["SwitchMode", "SecondLayer"]:
            action = data[i]
        else:
            action = getattr(e, data[i])

        di[key] = action
    return di


def load_conf():
    conf = read_conf()
    conf["default_layer_encod"] = encode_conf_def(conf["default_layer"])
    conf["second_layer_encod"] = encode_conf_def(conf["second_layer"])
    return conf


def init_socket(SOCKET_FILE):
    if os.path.exists(SOCKET_FILE):
        os.remove(SOCKET_FILE)

    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server_socket.bind(SOCKET_FILE)
        print(f"Server lauscht auf {SOCKET_FILE}")
    except socket.error as msg:
        print(f"Fehler beim Binden des Sockets: {msg}")
        server_socket.close()
        return (server_socket, 1)

    server_socket.listen(1)  # anzahl clients
    return (server_socket, 0)


def creat_virtual_device():
    # Virtuelles Mausgerät erstellen
    try:
        ui = evdev.UInput(MOUSE_CAPABILITIES, name="Muede_Mouse_Keyboard", vendor=0x1234, product=0x5678, version=1)
        print("The virtual mouse 'Controller_Mouse_Keyboard_Evdev' has been created.")
        return ui
    except PermissionError:
        print("Error: No authorization to create /dev/uinput.")
        print("Make sure you are in the ‘input’ group and the udev rule is active, or run with sudo (Not recomendet).")
        return
    except Exception as e:
        print(f"Error when creating the virtual device: {e}")
        return


def center_controller(dev, controller_axes):
    axes = [e.ABS_X, e.ABS_Y, e.ABS_X, e.ABS_Y, e.ABS_Z, e.ABS_RZ]
    for n, i in enumerate(axes):
        absinfo_n = dev.absinfo(i)
        min_n, max_n = absinfo_n.min, absinfo_n.max
        center_n = (min_n + max_n) // 2
        controller_axes[n] = [center_n, min_n, max_n]


def find_controller_device(single: bool, exclude_name: list[str], partial_name='controller'):
    """Findet einen Controller-Gerätepfad basierend auf einem Teil des Namens."""
    devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
    target = []
    skip = False
    for device in devices:
        for i in exclude_name:
            if i.lower() in device.name.lower():
                skip = True
        if skip:
            skip = False
            continue

        if partial_name.lower() in device.name.lower():
        # if partial_name.lower() in device.name.lower() or 'joystick' in device.name.lower():
            print(f"Gefundenen Controller: {device.name} ({device.path})")
            target.append(device.path)

            if single:
                return target
    return target


def init_controller(conf):
    if conf["CONTROLLER_PATH"] == [""]:
        print("Versuche, einen Controller automatisch zu finden...")
        found_path = find_controller_device(conf["SINGEL_DEVICE"],
                                            conf["CONTROLLER_NAME_EXCLUDE"],
                                            conf["CONTROLLER_NAME"])
        if found_path:
            conf["CONTROLLER_PATH"] = found_path
            return 0
        else:
            print("Kein passender Controller gefunden. Bitte CONTROLLER anschliesen.")
            return 1
    return 2


def init_controll_controller(conf):
    devices = []
    try:
        for dev in conf["CONTROLLER_PATH"]:
            dev = evdev.InputDevice(dev)
            devices.append(dev)
            print(f"Controller {dev.name} ({dev.path}) geöffnet.")
        if len(devices) == 1:
            center_controller(devices[0], controller_axes)
        return devices
    except FileNotFoundError:
        print(f"Fehler: Controller unter {CONTROLLER_PATH} nicht gefunden.")
        print("Stelle sicher, dass der Pfad korrekt ist und du Berechtigungen hast (z.B. in der 'input'-Gruppe sein).")
        return
    except PermissionError:
        print(f"Fehler: Keine Berechtigung, Controller {CONTROLLER_PATH} zu öffnen.")
        print("Stelle sicher, dass du in der 'input'-Gruppe bist oder das Skript mit sudo ausführst (nicht empfohlen für Dauerbetrieb).")
        return

def grab_controller(devices, status=2):
    """status = 0 off, 1, on, 2 toggle"""
    global grabed
    if status == 2:
        status = not grabed
    if status:
        try:
            for dev in devices:
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
            for dev in devices:
                dev.ungrab()  # Gerät freigeben
            print("Controller freigegeben: Original-Inputs werden wieder an das System gesendet.")
            grabed = False
        except OSError as err:
            print(f"Warnung: Konnte Controller nicht freigeben: {err}")

    time.sleep(0.2)


def send_key(button, state, orginal=None):
    global layer, controller_modus

    if layer == 0:
        BUTTON_MAPPING = conf["default_layer_encod"]
    else:
        BUTTON_MAPPING = conf["second_layer_encod"]

    # print(BUTTON_MAPPING)
    if button in BUTTON_MAPPING:
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
            # Note: Bug es muss noch detekiert werden ob REL, ABS oder KEY!!!
            ui.write(e.EV_KEY, action, state)
            ui.syn()
    else:
        if conf["PASSTHROU"]:
            if orginal:
                button = orginal
            ui.write(e.EV_KEY, button, state)
            ui.syn()


def send_ABS(event):
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
        elif event.value >= controller_axes[4][2] * 0.9:
            send_key(event.code, 1)

    elif event.code == e.ABS_RZ:
        if event.value <= 10:
            send_key(event.code, 0)
        elif event.value >= controller_axes[5][2] * 0.9:
            send_key(event.code, 1)


def controll_controller(devices, pipe_read_fd):
    global thread_status, controller_axes
    thread_status[0] = 1

    try:
        while True:
            if controller_modus == grabed:
                grab_controller(devices[:-1])

            r, w, x = select.select(devices, [], [])
            for dev in r:
                if dev == pipe_read_fd:
                    return

                for event in dev.read():

                    if event.type == e.EV_KEY:
                        if event.value == 2:
                            continue
                        print(event.code, event.value)
                        send_key(event.code, event.value)

                    elif event.type == e.EV_ABS:
                        send_ABS(event)
                        print(f"controller = {evdev.ecodes.bytype[evdev.ecodes.EV_ABS][event.code]},\t{event.value}")

                    elif event.type == e.EV_REL:
                        if event.code == e.REL_WHEEL:  # vertikal wheel
                            if event.value == 1:
                                send_key("WHEEL_UP", 1, event.code)
                                send_key("WHEEL_UP", 0, event.code)
                            elif event.value == -1:
                                send_key("WHEEL_DOWN", 1, event.code)
                                send_key("WHEEL_DOWN", 0, event.code)
                        elif event.code == e.REL_HWHEEL:  # Horizontal wheel
                            if event.value == 1:
                                send_key("WHEEL_RIGHT", 1, event.code)
                                send_key("WHEEL_RIGHT", 0, event.code)
                            elif event.value == -1:
                                send_key("WHEEL_LEFT", 1, event.code)
                                send_key("WHEEL_LEFT", 0, event.code)
                        print(f"maus = {evdev.ecodes.bytype[evdev.ecodes.EV_REL][event.code]},\t{event.value}")
    except OSError:
        controller_axes = [[0, -1, 1], [0, -1, 1], [0, -1, 1],[0, -1, 1],[0, -1, 1],[0, -1, 1]]
        print("Controller getrennt.")
        thread_status[0] = 0



def run_controller(conf, pipe_read_fd):
    controller_feedback = init_controller(conf)
    if controller_feedback == 0:
        pass
    elif controller_feedback == 1:
        return
    elif controller_feedback == 2:
        pass

    
    dev = init_controll_controller(conf)
    # controll_controller(dev)
    dev.append(pipe_read_fd)
    threading.Thread(target=controll_controller, args=(dev, pipe_read_fd,)).start()
    return dev



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


def main():
    global conf, ui
    SOCKET_FILE = os.path.expanduser("/home/tzwicker/python/HydraInput/src/Hydra.sock")
    last_update = time.time()
    conf = load_conf()

    try:
        server_socket, feedback = init_socket(SOCKET_FILE)
        if feedback:
            print("konnte socket nicht erstellen!")
            exit(0)

        ui = creat_virtual_device()

        # pipe to stop the controller thread
        pipe_read_fd, pipe_write_fd = os.pipe()

        dev = run_controller(conf, pipe_read_fd)

        if conf["ENABLE_MOUSE"]:
            threading.Thread(target=move_mouse, daemon=True).start()

        while True:
            connection, client_address = server_socket.accept()
            
            data = connection.recv(1024)
            if data:
                message = data.decode('utf-8')
                print(f"Empfangen: '{message}'")

                response = "running"
                connection.sendall(response.encode('utf-8'))

                if message == "kill":
                    break

                elif message == "reload":
                    conf = load_conf()

                elif message == "status":
                    pass

                elif message == "update":
                    if time.time() <= last_update + 2:
                        print("zu schnelles updaten!")
                    else:
                        print("update ...")
                        if thread_status[0] == 0:
                            dev = run_controller(conf, pipe_read_fd)


                        # update()

                    last_update = time.time()

    except KeyboardInterrupt:
        print("manuel stop")

    finally:
        connection.close()
        os.write(pipe_write_fd, b'x')  # stop thread
        if grabed:
            grab_controller(dev[:-1], 0)

        if 'dev' in locals() and dev:
            for i in dev[:-1]:
                i.close()
                print(f"Controller {i.name} geschlossen.")
        if 'ui' in locals() and ui:
            ui.close()
            print("Virtuelle Maus geschlossen.")


if __name__ == "__main__":
    main()
