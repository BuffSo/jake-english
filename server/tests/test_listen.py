"""wait_for_address: the server waits for its address before loading whisper and the voice (ADR-0011)."""
import socket

import pytest

from je_server.listen import wait_for_address

# TEST-NET-1 (RFC 5737): never put on a real interface, so binding it fails like a Tailscale address
# before Tailscale is up
NOT_ON_THIS_MAC = "192.0.2.1"


class Waited(Exception):
    pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def no_sleep(_seconds: float) -> None:
    raise AssertionError("should not wait")


def stop_on_sleep(_seconds: float) -> None:
    raise Waited


def test_returns_at_once_when_the_address_can_be_bound():
    wait_for_address("127.0.0.1", free_port(), sleep=no_sleep)


def test_waits_while_the_address_is_not_on_this_mac():
    with pytest.raises(Waited):
        wait_for_address(NOT_ON_THIS_MAC, free_port(), sleep=stop_on_sleep)


def test_waits_while_the_port_is_taken_and_goes_on_once_it_is_free():
    # a worktree server still holding the port when launchd starts this one (DEVENV guide 「카드가 서버를 시험할 때」)
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen()
    port = holder.getsockname()[1]
    sleeps: list[float] = []

    def free_after_first_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        holder.close()

    try:
        wait_for_address("127.0.0.1", port, sleep=free_after_first_sleep)
    finally:
        holder.close()
    assert len(sleeps) == 1


def test_does_not_wait_on_a_host_that_cannot_be_an_ipv4_address():
    # a JE_HOST that is not an IPv4 address at all must fail loudly in uvicorn, not wait
    wait_for_address("::1", free_port(), sleep=no_sleep)


def test_gives_up_with_an_error_after_the_limit():
    # a well-formed but wrong JE_HOST (a mistyped digit) binds like Tailscale not up yet. Exiting
    # with an error after the limit shows it in the log and in launchd's last exit code, instead of
    # a server that looks running while nothing listens (PR #26 review)
    sleeps: list[float] = []
    with pytest.raises(SystemExit) as stopped:
        wait_for_address(NOT_ON_THIS_MAC, free_port(), sleep=sleeps.append, limit=6.0)
    assert len(sleeps) == 3
    assert "JE_HOST" in str(stopped.value.code)
