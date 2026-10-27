"""The network guard is the product's main claim in code. It gets tested.

Each test restores the real socket functions afterwards, so a guard installed
here cannot leak into the rest of the suite.
"""
from __future__ import annotations

import inspect
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase import offline

# Everything enable() touches, so a test cannot leave the process patched. The
# earlier version restored three names out of the eight; once UDP and DNS were
# guarded too, one test enabling the guard would have left name resolution
# broken for every test after it, in this file and in any other.
_PATCHED_ON_SOCKET = ("connect", "connect_ex", "sendto", "sendmsg")
_PATCHED_ON_MODULE = ("create_connection", "gethostbyname", "gethostbyname_ex",
                      "getaddrinfo")


@pytest.fixture(autouse=True)
def restore():
    on_class = {n: getattr(socket.socket, n) for n in _PATCHED_ON_SOCKET
                if hasattr(socket.socket, n)}
    on_module = {n: getattr(socket, n) for n in _PATCHED_ON_MODULE
                 if hasattr(socket, n)}
    was_guarded = getattr(socket.socket, "_askbase_guarded", False)
    yield
    for name, fn in on_class.items():
        setattr(socket.socket, name, fn)
    for name, fn in on_module.items():
        setattr(socket, name, fn)
    if was_guarded:
        socket.socket._askbase_guarded = was_guarded
    elif hasattr(socket.socket, "_askbase_guarded"):
        del socket.socket._askbase_guarded


@pytest.fixture
def guarded(restore):
    """The guard installed, and taken back off afterwards by `restore`."""
    offline.enable()
    return offline


def test_the_outside_world_is_refused():
    offline.enable()
    with pytest.raises(offline.NetworkRefused):
        socket.create_connection(("example.com", 80), timeout=1)


@pytest.mark.parametrize("host", ["8.8.8.8", "example.com", "huggingface.co", "::1.2.3.4"])
def test_every_remote_host_is_refused(host):
    offline.enable()
    s = socket.socket()
    try:
        with pytest.raises(offline.NetworkRefused):
            s.connect((host, 443))
    finally:
        s.close()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.1.1"])
def test_this_machine_is_allowed(host):
    # The model is served over loopback, so refusing it would break the product.
    offline.enable()
    s = socket.socket()
    # A short timeout matters: on macOS an address like 127.0.1.1 is not bound
    # and the connection hangs for over a minute instead of being refused. The
    # test asks which error the guard produces, not whether anything answers.
    s.settimeout(0.2)
    try:
        s.connect((host, 1))
    except offline.NetworkRefused:
        pytest.fail(f"{host} должен быть разрешён")
    except OSError:
        pass                          # refused or timed out: either way the guard let it through
    finally:
        s.close()


def test_a_unix_socket_or_odd_address_is_refused():
    # Not a claim about unix sockets being dangerous: anything the guard cannot
    # recognise as local is refused, because the default must be the safe one.
    offline.enable()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        with pytest.raises(offline.NetworkRefused):
            s.connect("/tmp/askbase-nonexistent.sock")
    finally:
        s.close()


def test_enabling_twice_does_not_stack_wrappers():
    offline.enable()
    once = socket.socket.connect
    offline.enable()
    assert socket.socket.connect is once


def test_connect_ex_is_guarded_too():
    # connect_ex returns an error code instead of raising, which is exactly how
    # a quiet phone-home would slip past a guard that only covers connect.
    offline.enable()
    s = socket.socket()
    try:
        with pytest.raises(offline.NetworkRefused):
            s.connect_ex(("example.com", 80))
    finally:
        s.close()


def test_the_selftest_passes_in_a_clean_process():
    assert offline.selftest() == 0
@pytest.mark.parametrize("host", [
    "127.0.0.1.example.com",          # an ordinary DNS name, resolved by its owner
    "127.evil.example.com",
    "127.0.0.1.attacker.test",
])
def test_a_name_that_merely_starts_with_127_is_refused(host):
    # The guard used to match the text "127." at the front of the host, which
    # a hostname can carry while resolving anywhere in the world. That is the
    # cheapest way out of a promise that nothing leaves this computer.
    offline.enable()
    s = socket.socket()
    s.settimeout(0.2)
    try:
        with pytest.raises(offline.NetworkRefused):
            s.connect((host, 443))
    finally:
        s.close()


@pytest.mark.parametrize("host", ["::ffff:127.0.0.1", "0:0:0:0:0:0:0:1", "127.0.0.1%lo0"])
def test_the_other_spellings_of_this_machine_are_allowed(host):
    # The model is served over loopback, and a library is free to hand the
    # address over in any of its forms.
    offline.enable()
    s = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET)
    s.settimeout(0.2)
    try:
        s.connect((host, 1))
    except offline.NetworkRefused:
        pytest.fail(f"{host} должен быть разрешён")
    except OSError:
        pass                          # nobody listening: the guard let it through
    finally:
        s.close()


# ---- the channels the guard used to miss ------------------------------------
# Each of these was reproduced against a listener on this machine's own
# non-loopback address, so the old result was the guard's decision rather than
# the internet being unreachable. selftest() passed while all of them were
# open, because it only ever tried create_connection.

OUTSIDE = ("8.8.8.8", 53)


def test_a_udp_datagram_cannot_leave(guarded):
    # sendto carries its destination and never calls connect(), so guarding
    # connect() alone checked nothing. This is the shape of statsd telemetry.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with pytest.raises(offline.NetworkRefused):
        s.sendto(b"exfiltrated", OUTSIDE)
    s.close()


def test_sendmsg_cannot_leave_either(guarded):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with pytest.raises(offline.NetworkRefused):
        s.sendmsg([b"exfiltrated"], [], 0, OUTSIDE)
    s.close()


def test_a_datagram_to_this_machine_is_allowed(guarded):
    # The model is reached over loopback, so loopback must stay open, and a
    # guard that blocked it would break the product rather than protect it.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(b"ping", ("127.0.0.1", 11434))
    except offline.NetworkRefused:
        pytest.fail("локальная датаграмма отклонена")
    except OSError:
        pass                        # nobody listening is fine
    finally:
        s.close()


def test_resolving_a_name_is_refused(guarded):
    # A lookup is itself a message to a server, and a usable exfiltration
    # channel that needs no bug in any dependency. Nothing in this product
    # resolves a name: the model sits at a literal loopback address.
    with pytest.raises(offline.NetworkRefused):
        socket.gethostbyname("example.com")
    with pytest.raises(offline.NetworkRefused):
        socket.getaddrinfo("example.com", 80)


def test_a_literal_loopback_address_still_resolves(guarded):
    # getaddrinfo cannot simply be refused: create_connection uses it.
    assert socket.getaddrinfo("127.0.0.1", 11434)


def test_the_selftest_checks_every_channel_not_one(guarded):
    # The regression that matters most here: a selftest that passes while the
    # guard leaks is worse than no selftest, because the install page tells
    # people to run it as proof.
    source = inspect.getsource(offline.selftest)
    for channel in ("sendto", "sendmsg", "gethostbyname", "getaddrinfo",
                    "connect_ex", "create_connection"):
        assert channel in source, f"самопроверка не трогает {channel}"


def test_the_selftest_passes_with_the_guard_installed(guarded, capsys):
    assert offline.selftest() == 0
    assert "пройдена" in capsys.readouterr().out
