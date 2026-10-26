"""Refuse every connection that is not to this machine.

The product's claim is that the question and the data never leave the computer.
A claim like that should be enforced by the program, not by its author's good
intentions, which is how pii-roundtrip does it: it forbids the network outright.

Askbase cannot go quite that far, because the model is served over the loopback
address. So the rule here is narrower and still checkable: connections to
127.0.0.1, ::1 and a unix socket are allowed, everything else raises. If a
dependency ever tries to phone home, telemetry included, it fails loudly rather
than succeeding quietly.

This is a guard, not a sandbox. A determined piece of native code can open a
socket without going through Python. It stops the realistic failure, which is a
library doing something helpful that nobody asked for.

What this file used to miss, found by review and each reproduced against a
listener on this machine's own non-loopback address:

  - UDP. `sendto` and `sendmsg` carry a destination with them and never call
    connect(), so patching connect() checked nothing. A datagram to 8.8.8.8:53
    went out. That is the exact shape of the statsd-style telemetry the module
    exists to stop.
  - `_socket.socket`, the C base class, cannot be patched at all: it is an
    immutable type and assigning to its methods raises. A caller that reaches
    for `_socket.socket.connect(sock, addr)` deliberately therefore still gets
    through, and nothing in Python can stop that. It is the same exemption the
    paragraph above already states: this is a guard against a library doing
    something helpful nobody asked for, not a sandbox against code that is
    trying to get out. Said here explicitly so the limit is not discovered by
    someone who trusted the word "refuses".
  - DNS. `gethostbyname` resolved a public name freely, which is a usable
    exfiltration channel on its own and needs no bug in any dependency.

The three are closed below, and `selftest()` now exercises each of them,
because the old selftest passed while all three were open: it only tried
`create_connection`.
"""
from __future__ import annotations

import ipaddress
import socket

LOOPBACK = {"localhost", "0.0.0.0", ""}


class NetworkRefused(OSError):
    """Raised instead of opening a connection to anywhere but this machine."""


def _is_local(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return False                      # unix sockets and the unexpected: refuse
    host = address[0]
    if not isinstance(host, str):
        return False
    if host in LOOPBACK:
        return True
    try:
        # Read as an address rather than matched as text. "127." used to be
        # enough of a prefix, and a name like 127.0.0.1.example.com is a
        # perfectly ordinary DNS name that resolves wherever its owner wants:
        # it is also the shortest way out of this guard. Anything that is not
        # a literal address is refused, loopback is allowed in both families,
        # and ::ffff:127.0.0.1 is recognised as the loopback it is.
        ip = ipaddress.ip_address(host.partition("%")[0])
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or ip.is_unspecified or bool(mapped and mapped.is_loopback)


def _refuse(address) -> None:
    if not _is_local(address):
        raise NetworkRefused(f"Askbase не ходит в сеть: отказано {address!r}")


def enable() -> None:
    """Install the guard. Safe to call twice."""
    if getattr(socket.socket, "_askbase_guarded", False):
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection
    real_sendto = socket.socket.sendto
    real_sendmsg = getattr(socket.socket, "sendmsg", None)

    def connect(self, address, *a, **kw):
        _refuse(address)
        return real_connect(self, address, *a, **kw)

    def connect_ex(self, address, *a, **kw):
        _refuse(address)
        return real_connect_ex(self, address, *a, **kw)

    def create_connection(address, *a, **kw):
        _refuse(address)
        return real_create(address, *a, **kw)

    def sendto(self, data, *a):
        # The destination is the last positional argument: sendto(data, addr)
        # or sendto(data, flags, addr). A datagram needs no connect(), which
        # is why guarding connect() alone left UDP wide open.
        if a:
            _refuse(a[-1])
        return real_sendto(self, data, *a)

    def sendmsg(self, buffers, ancdata=None, flags=0, address=None, *a):
        if address is not None:
            _refuse(address)
        return real_sendmsg(self, buffers, ancdata or [], flags, address, *a)

    def refuse_name(name, *a, **kw):
        # Resolution itself is a message to a server. Nothing in this product
        # resolves a name: the model is at a literal loopback address, so a
        # lookup can only be something asking where to send data.
        raise NetworkRefused(f"Askbase не разрешает имена в сети: отказано {name!r}")

    socket.socket.connect = connect                 # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex           # type: ignore[method-assign]
    socket.socket.sendto = sendto                   # type: ignore[method-assign]
    if real_sendmsg is not None:
        socket.socket.sendmsg = sendmsg             # type: ignore[method-assign]
    socket.create_connection = create_connection    # type: ignore[assignment]

    socket.gethostbyname = refuse_name              # type: ignore[assignment]
    socket.gethostbyname_ex = refuse_name           # type: ignore[assignment]
    socket.getaddrinfo = _guarded_getaddrinfo(socket.getaddrinfo)  # type: ignore[assignment]

    socket.socket._askbase_guarded = True           # type: ignore[attr-defined]


def _guarded_getaddrinfo(real):
    """Allow a literal loopback address through, refuse a name.

    getaddrinfo cannot simply be refused: `create_connection` uses it, and the
    model lives at 127.0.0.1. A literal address needs no lookup and is passed
    through; anything that would actually reach a resolver is refused.
    """
    def getaddrinfo(host, port, *a, **kw):
        if host is None or _is_local((host, port)):
            return real(host, port, *a, **kw)
        raise NetworkRefused(f"Askbase не разрешает имена в сети: отказано {host!r}")

    return getaddrinfo


def selftest() -> int:
    """Check the guard from the outside. Run with --selftest; 0 means it holds.

    Every channel gets its own case. The previous version tried one
    (`create_connection`) and reported success while UDP, the C socket class
    and DNS were all open.
    """
    enable()
    problems: list[str] = []
    outside = ("8.8.8.8", 53)

    def expect_refused(what, fn) -> None:
        try:
            fn()
        except NetworkRefused:
            return
        except Exception as e:                   # refused for another reason is not proof
            problems.append(f"{what}: отклонено, но не нашей проверкой: {e!r}")
        else:
            problems.append(f"{what}: прошло наружу, запрет не работает")

    expect_refused("исходящее соединение",
                   lambda: socket.create_connection(outside, timeout=2))
    expect_refused("connect напрямую",
                   lambda: socket.socket().connect(outside))
    expect_refused("connect_ex",
                   lambda: socket.socket().connect_ex(outside))
    expect_refused("UDP sendto", lambda: socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", outside))
    expect_refused("UDP sendmsg", lambda: socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM).sendmsg([b"x"], [], 0, outside))
    expect_refused("разрешение имени",
                   lambda: socket.gethostbyname("example.com"))
    expect_refused("getaddrinfo по имени",
                   lambda: socket.getaddrinfo("example.com", 80))

    s = socket.socket()
    try:
        s.connect(("127.0.0.1", 11434))
    except NetworkRefused:
        problems.append("локальное соединение отклонено, модель будет недоступна")
    except OSError:
        pass                                     # nobody listening is fine, the guard let it through
    finally:
        s.close()

    try:
        socket.getaddrinfo("127.0.0.1", 11434)
    except NetworkRefused:
        problems.append("getaddrinfo по локальному адресу отклонён, модель будет недоступна")

    for p in problems:
        print("ПРОВАЛ:", p)
    if not problems:
        print("самопроверка пройдена: наружу нельзя, на этот компьютер можно")
    return 1 if problems else 0
