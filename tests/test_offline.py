"""The network guard is the product's main claim in code. It gets tested.

Each test restores the real socket functions afterwards, so a guard installed
here cannot leak into the rest of the suite.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase import offline  # noqa: E402


@pytest.fixture(autouse=True)
def restore():
    saved = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection,
             getattr(socket.socket, "_askbase_guarded", False))
    yield
    socket.socket.connect, socket.socket.connect_ex, socket.create_connection = saved[:3]
    if saved[3]:
        socket.socket._askbase_guarded = saved[3]
    elif hasattr(socket.socket, "_askbase_guarded"):
        del socket.socket._askbase_guarded


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
