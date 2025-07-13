import argparse
import socket


def init_parser():
    parser = argparse.ArgumentParser(
        prog="Hydra Input",
        description="A remaper for Controller and Keyboards.")

    parser.add_argument('-r', '--run', required=False, default=False, action="store_true", help="Start the daemon")
    parser.add_argument('-R', '--reload', required=False, default=False, action="store_true", help="Reloaf config")
    parser.add_argument('-s', '--status', required=False, default=False, action="store_true", help="Print status from daemon")
    parser.add_argument('-u', '--update', required=False, default=False, action="store_true", help="update device list")
    parser.add_argument('-k', '--kill', required=False, default=False, action="store_true", help="update device list")
    # parser.add_argument('-c', '--conf', required=False, metavar="path", help="Load a config by path.")


    return parser.parse_args()


def print_d(msg: str = "", no_print: bool = False):
    if not no_print:
        print(msg)


def send_msg(SOCKET_FILE: str, msg: str, no_print: bool = False):
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        client_socket.connect(SOCKET_FILE)
        # print(f"Verbunden mit Server an {SOCKET_FILE}")
    except socket.error as msg_error:
        print_d(f"Konnte keine Verbindung zum Server herstellen: {msg_error}", no_print)
        print_d("Stellen Sie sicher, dass der Server läuft.", no_print)
        return 1

    try:
        # print(f"Sende: '{msg}'")
        client_socket.sendall(msg.encode('utf-8'))

        data = client_socket.recv(1024)
        response = data.decode('utf-8')
        client_socket.close()
        return response
        # print(f"Empfangen vom Server: '{response}'")

    except Exception as e:
        print_d(f"Fehler bei der Kommunikation mit dem Server: {e}", no_print)
    finally:
        client_socket.close()
        # print_d("Client-Socket geschlossen.", no_print)


def main():
    SOCKET_FILE = "/home/tzwicker/python/HydraInput/src/Hydra.sock"

    args = init_parser()


    if args.run:
        feedback = send_msg(SOCKET_FILE, "run", True)
        if feedback == "running":
            print("Der Daemon läuft bereits.")
        else:
            print("Daemon wird gestartet.")

    elif args.reload:
        send_msg(SOCKET_FILE, "reload")

    elif args.status:
        feedback = send_msg(SOCKET_FILE, "status")
        print(feedback)

    elif args.update:
        send_msg(SOCKET_FILE, "update")

    elif args.kill:
        feedback = send_msg(SOCKET_FILE, "kill", True)
        if feedback == "running":
            print("Der Daemon wird beendet.")
        else:
            print("Der Daemon läuft nicht.")

    else:
        print("Minimum 1 Argument required! --help for more info.")


if __name__ == "__main__":
    main()


