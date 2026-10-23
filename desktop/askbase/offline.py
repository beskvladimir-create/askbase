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
"""
from __future__ import annotations

import socket

LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}


class NetworkRefused(OSError):
    """Raised instead of opening a connection to anywhere but this machine."""


def _is_local(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return False                      # unix sockets and the unexpected: refuse
    host = address[0]
    if host in LOOPBACK:
        return True
    if isinstance(host, str) and (host.startswith("127.") or host == "::ffff:127.0.0.1"):
        return True
    return False


def enable() -> None:
    """Install the guard. Safe to call twice."""
    if getattr(socket.socket, "_askbase_guarded", False):
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection

    def connect(self, address, *a, **kw):
        if not _is_local(address):
            raise NetworkRefused(f"Askbase не ходит в сеть: отказано {address!r}")
        return real_connect(self, address, *a, **kw)

    def connect_ex(self, address, *a, **kw):
        if not _is_local(address):
            raise NetworkRefused(f"Askbase не ходит в сеть: отказано {address!r}")
        return real_connect_ex(self, address, *a, **kw)

    def create_connection(address, *a, **kw):
        if not _is_local(address):
            raise NetworkRefused(f"Askbase не ходит в сеть: отказано {address!r}")
        return real_create(address, *a, **kw)

    socket.socket.connect = connect          # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex    # type: ignore[method-assign]
    socket.create_connection = create_connection  # type: ignore[assignment]
    socket.socket._askbase_guarded = True    # type: ignore[attr-defined]


def selftest() -> int:
    """Check the guard from the outside. Run with --selftest; 0 means it holds."""
    enable()
    problems: list[str] = []

    try:
        socket.create_connection(("example.com", 80), timeout=2)
    except NetworkRefused:
        pass
    except Exception as e:                   # refused for another reason is not proof
        problems.append(f"выход наружу отклонён, но не нашей проверкой: {e!r}")
    else:
        problems.append("соединение наружу прошло, запрет не работает")

    s = socket.socket()
    try:
        s.connect(("127.0.0.1", 11434))
    except NetworkRefused:
        problems.append("локальное соединение отклонено, модель будет недоступна")
    except OSError:
        pass                                 # nobody listening is fine, the guard let it through
    finally:
        s.close()

    for p in problems:
        print("ПРОВАЛ:", p)
    if not problems:
        print("самопроверка пройдена: наружу нельзя, на этот компьютер можно")
    return 1 if problems else 0
