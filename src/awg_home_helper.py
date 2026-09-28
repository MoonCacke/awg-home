#!/usr/bin/python3
"""Small, fixed-purpose macOS helper for one local AmneziaWG profile.

The root commands never accept a profile path or shell snippet from the GUI.
The installer places this file, awg, and the profile in root-owned locations.
"""

import base64
import configparser
import fcntl
import ipaddress
import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("/Library/PrivilegedHelperTools/awg-home")
PROFILE = Path("/Library/Application Support/AWG Home/client.conf")
ENGINE = ROOT / "amneziawg-go"
AWG = ROOT / "awg"
RUNTIME = Path("/var/run/awg-home")
STATE = RUNTIME / "state.json"
LOCK = RUNTIME / "lock"
NAME_FILE = RUNTIME / "interface.name"
LOG = RUNTIME / "engine.log"


class AWGError(Exception):
    pass


def run(argv, *, check=True):
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=12)
    if check and result.returncode:
        raise AWGError("Команда {} завершилась с ошибкой {}".format(
            Path(argv[0]).name, result.returncode))
    return result.stdout.strip()


def key32(value):
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (ValueError, base64.binascii.Error):
        return False


def parse_profile(text):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str.lower
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise AWGError("Профиль повреждён или имеет повторяющиеся поля") from exc
    if set(parser.sections()) != {"Interface", "Peer"}:
        raise AWGError("Нужен профиль с одним Interface и одним Peer")
    interface = dict(parser.items("Interface"))
    peer = dict(parser.items("Peer"))
    interface_keys = {"privatekey", "address", "mtu", "dns", "jc", "jmin",
                      "jmax", "s1", "s2", "h1", "h2", "h3", "h4"}
    peer_keys = {"publickey", "endpoint", "allowedips", "persistentkeepalive"}
    if set(interface) - interface_keys or set(peer) - peer_keys:
        raise AWGError("В профиле есть параметры, которые эта версия не поддерживает")
    if not key32(interface.get("privatekey", "")) or not key32(peer.get("publickey", "")):
        raise AWGError("Ключ в профиле имеет неправильный формат")
    try:
        address = ipaddress.ip_interface(interface["address"])
        if address.version != 4 or address.network.prefixlen != 32:
            raise ValueError()
        mtu = int(interface.get("mtu", "1280"))
        if not 576 <= mtu <= 1500:
            raise ValueError()
        endpoint_host, port_text = peer["endpoint"].rsplit(":", 1)
        endpoint = ipaddress.IPv4Address(endpoint_host)
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError()
        if peer["allowedips"].replace(" ", "") != "0.0.0.0/0":
            raise ValueError()
        keepalive = int(peer.get("persistentkeepalive", "0"))
        if not 0 <= keepalive <= 65535:
            raise ValueError()
        dns = [str(ipaddress.IPv4Address(x.strip())) for x in
               interface.get("dns", "").split(",") if x.strip()]
        if not dns:
            raise ValueError()
        for name in ("jc", "jmin", "jmax", "s1", "s2", "h1", "h2", "h3", "h4"):
            if name in interface and not 0 <= int(interface[name]) <= 4294967295:
                raise ValueError()
        if "jmin" in interface and "jmax" in interface:
            if int(interface["jmin"]) > int(interface["jmax"]):
                raise ValueError()
    except (KeyError, ValueError, ipaddress.AddressValueError) as exc:
        raise AWGError("Адрес, DNS, порт или параметры профиля некорректны") from exc
    return {"interface": interface, "peer": peer, "address": str(address),
            "mtu": mtu, "endpoint": str(endpoint), "dns": dns}


def stripped_config(profile):
    interface = profile["interface"]
    peer = profile["peer"]
    fields = ["[Interface]", "PrivateKey = " + interface["privatekey"]]
    for name in ("Jc", "Jmin", "Jmax", "S1", "S2", "H1", "H2", "H3", "H4"):
        if name.lower() in interface:
            fields.append(name + " = " + interface[name.lower()])
    fields += ["", "[Peer]", "PublicKey = " + peer["publickey"],
               "Endpoint = " + peer["endpoint"], "AllowedIPs = 0.0.0.0/0"]
    if "persistentkeepalive" in peer:
        fields.append("PersistentKeepalive = " + peer["persistentkeepalive"])
    return "\n".join(fields) + "\n"


def check_root_owned(path, *, secret=False):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
        raise AWGError("Ненадёжный файл установки: " + str(path))
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise AWGError("Файл установки доступен для изменения другим пользователям")
    if secret and info.st_mode & (stat.S_IRGRP | stat.S_IROTH):
        raise AWGError("Профиль VPN должен быть доступен только root")
    for parent in path.parents:
        if parent == Path("/"):
            break
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0:
            raise AWGError("Ненадёжный каталог установки: " + str(parent))
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise AWGError("Каталог установки доступен для изменения другим пользователям")


def default_route():
    output = run(["/sbin/route", "-n", "get", "-inet", "default"])
    gateway = re.search(r"^\s*gateway:\s*(\S+)", output, re.M)
    device = re.search(r"^\s*interface:\s*(\S+)", output, re.M)
    if not gateway or not device:
        raise AWGError("Не удалось определить основной интернет-маршрут")
    ipaddress.IPv4Address(gateway.group(1))
    if device.group(1).startswith("utun"):
        raise AWGError("Уже включён другой VPN. Отключите его перед AWG Home")
    return gateway.group(1), device.group(1)


def refuse_other_vpn(endpoint):
    for destination in ("1.1.1.1", endpoint):
        output = run(["/sbin/route", "-n", "get", "-inet", destination])
        match = re.search(r"^\s*interface:\s*(\S+)", output, re.M)
        if match and match.group(1).startswith("utun"):
            raise AWGError("Уже включён другой VPN. Отключите его перед AWG Home")


def network_service(device):
    output = run(["/usr/sbin/networksetup", "-listnetworkserviceorder"])
    current = None
    for line in output.splitlines():
        match = re.match(r"^\(\d+\) (.+)$", line)
        if match:
            current = match.group(1)
            continue
        match = re.search(r"\(Hardware Port: .*?, Device: ([^)]+)\)", line)
        if current and match and match.group(1) == device and not current.startswith("*"):
            return current
    raise AWGError("Не удалось найти сетевую службу для " + device)


def current_dns(service):
    output = run(["/usr/sbin/networksetup", "-getdnsservers", service])
    if "aren't any DNS Servers" in output or not output:
        return ["Empty"]
    values = output.splitlines()
    for value in values:
        ipaddress.ip_address(value)
    return values


def running(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False


def write_state(data):
    tmp = RUNTIME / ("state.{}.tmp".format(os.getpid()))
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(str(tmp), str(STATE))
    finally:
        if tmp.exists():
            tmp.unlink()


def read_state():
    try:
        return json.loads(STATE.read_text())
    except FileNotFoundError:
        return None


def stop_locked(state):
    errors = []
    service = state.get("service")
    if state.get("dns_set") and service:
        try:
            run(["/usr/sbin/networksetup", "-setdnsservers", service] + state["old_dns"])
        except Exception as exc:
            errors.append(str(exc))
    for target in reversed(state.get("routes", [])):
        command = ["/sbin/route", "-q", "-n", "delete", "-inet", target]
        result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=12)
        if result.returncode:
            errors.append("Не удалось удалить маршрут " + target)
    pid = state.get("pid")
    if pid and running(pid):
        command = run(["/bin/ps", "-p", str(pid), "-o", "command="], check=False)
        if "amneziawg-go" in command and "-f utun" in command:
            os.kill(int(pid), signal.SIGTERM)
        else:
            errors.append("PID туннеля теперь принадлежит другому процессу")
    for path in (NAME_FILE,):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if not errors:
        try:
            STATE.unlink()
        except FileNotFoundError:
            pass
    return errors


def start_locked():
    old = read_state()
    if old:
        if running(old.get("pid")):
            print("Уже подключено")
            return
        errors = stop_locked(old)
        if errors:
            raise AWGError("Остались старые сетевые настройки; нажмите «Отключить»")
    for path in (PROFILE, ENGINE, AWG, Path(__file__)):
        check_root_owned(path, secret=(path == PROFILE))
    profile = parse_profile(PROFILE.read_text())
    gateway, device = default_route()
    refuse_other_vpn(profile["endpoint"])
    service = network_service(device)
    old_dns = current_dns(service)
    state = {"pid": None, "iface": None, "routes": [], "service": service,
             "old_dns": old_dns, "dns_set": False, "gateway": gateway,
             "device": device, "endpoint": profile["endpoint"]}
    try:
        if NAME_FILE.exists():
            NAME_FILE.unlink()
        environment = os.environ.copy()
        environment["WG_TUN_NAME_FILE"] = str(NAME_FILE)
        log_fd = os.open(str(LOG), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(log_fd, "ab") as log:
            process = subprocess.Popen([str(ENGINE), "-f", "utun"], env=environment,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        state["pid"] = process.pid
        write_state(state)
        interface = None
        for _ in range(60):
            if process.poll() is not None:
                raise AWGError("Движок AmneziaWG завершился при запуске")
            if NAME_FILE.exists():
                candidate = NAME_FILE.read_text().strip()
                if re.fullmatch(r"utun\d+", candidate):
                    interface = candidate
                    if Path("/var/run/amneziawg/" + interface + ".sock").is_socket():
                        break
            time.sleep(0.1)
        if not interface:
            raise AWGError("Сетевой интерфейс не появился")
        state["iface"] = interface
        write_state(state)
        stripped = RUNTIME / "stripped.conf"
        fd = os.open(str(stripped), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as out:
                out.write(stripped_config(profile))
            run([str(AWG), "setconf", interface, str(stripped)])
        finally:
            stripped.unlink(missing_ok=True)
        run(["/sbin/ifconfig", interface, "inet", profile["address"],
             profile["address"].split("/")[0], "alias"])
        run(["/sbin/ifconfig", interface, "mtu", str(profile["mtu"])])
        run(["/sbin/ifconfig", interface, "up"])
        run(["/sbin/route", "-q", "-n", "add", "-inet", profile["endpoint"],
             "-gateway", gateway])
        state["routes"].append(profile["endpoint"])
        write_state(state)
        for prefix in ("0.0.0.0/1", "128.0.0.0/1"):
            run(["/sbin/route", "-q", "-n", "add", "-inet", prefix,
                 "-interface", interface])
            state["routes"].append(prefix)
            write_state(state)
        run(["/usr/sbin/networksetup", "-setdnsservers", service] + profile["dns"])
        state["dns_set"] = True
        write_state(state)
        subprocess.Popen([sys.executable, str(Path(__file__)), "watch", str(process.pid)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        print("Подключено через " + interface)
    except Exception:
        stop_locked(state)
        raise


def lock_and_run(action):
    RUNTIME.mkdir(mode=0o755, exist_ok=True)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return action()


def watch(pid):
    while True:
        time.sleep(5)
        state = read_state()
        if not state or state.get("pid") != pid:
            return
        if not running(pid):
            lock_and_run(lambda: stop_locked(read_state() or state))
            return
        try:
            gateway, device = default_route()
            if gateway != state["gateway"] or device != state["device"]:
                lock_and_run(lambda: stop_locked(read_state() or state))
                return
        except Exception:
            continue


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("start", "stop", "status", "watch"):
        raise AWGError("Допустимые команды: start, stop, status")
    command = sys.argv[1]
    if command == "status":
        state = read_state()
        print("Подключено" if state and running(state.get("pid")) else "Отключено")
        return
    if os.geteuid() != 0:
        raise AWGError("Для управления туннелем нужен пароль администратора")
    if command == "start":
        lock_and_run(start_locked)
    elif command == "stop":
        def stop():
            state = read_state()
            if not state:
                print("Уже отключено")
                return
            errors = stop_locked(state)
            if errors:
                raise AWGError("; ".join(errors))
            print("Отключено")
        lock_and_run(stop)
    elif command == "watch" and len(sys.argv) == 3:
        watch(int(sys.argv[2]))


if __name__ == "__main__":
    try:
        main()
    except (AWGError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
