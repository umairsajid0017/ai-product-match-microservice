"""Bounded URL ingestion behaviour (ES-09)."""

import socket

import httpx
import pytest

from app.services import url_fetcher
from app.services.url_fetcher import UnsafeImageURL, fetch_image_bytes, validate_image_url

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Resolve allowlisted hosts to a public address without touching the network."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 0))]

    monkeypatch.setattr(url_fetcher.socket, "getaddrinfo", fake_getaddrinfo)


def test_http_urls_are_rejected():
    with pytest.raises(UnsafeImageURL):
        validate_image_url("http://cdn.everystore.pk/uploads/a.jpg")


def test_non_allowlisted_hosts_are_rejected():
    with pytest.raises(UnsafeImageURL):
        validate_image_url("https://example.com/a.jpg")


def test_private_resolution_is_rejected(monkeypatch):
    def private_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(url_fetcher.socket, "getaddrinfo", private_getaddrinfo)

    with pytest.raises(UnsafeImageURL):
        validate_image_url("https://cdn.everystore.pk/uploads/a.jpg")


def test_allowed_host_is_accepted():
    validate_image_url("https://cdn.everystore.pk/uploads/a.jpg")


class FakeStream:
    def __init__(self, status_code=200, headers=None, chunks=(), url="https://cdn.everystore.pk/a.jpg"):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = list(chunks)
        self.url = url

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", str(self.url)),
                response=httpx.Response(self.status_code),
            )

    def iter_bytes(self, chunk_size):
        for chunk in self._chunks:
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, _method, _url):
        return self._responses.pop(0)


def install_client(monkeypatch, responses):
    monkeypatch.setattr(url_fetcher.httpx, "Client", lambda **_kwargs: FakeClient(responses))


def test_redirect_to_a_forbidden_host_is_rejected(monkeypatch):
    install_client(monkeypatch, [
        FakeStream(status_code=302, headers={"location": "https://example.com/a.jpg"}),
    ])

    with pytest.raises(UnsafeImageURL):
        fetch_image_bytes("https://cdn.everystore.pk/a.jpg")


def test_oversized_download_is_rejected(monkeypatch):
    monkeypatch.setattr(url_fetcher, "MAX_SIZE_BYTES", 10)
    install_client(monkeypatch, [
        FakeStream(chunks=[b"a" * 6, b"b" * 6]),
    ])

    with pytest.raises(UnsafeImageURL):
        fetch_image_bytes("https://cdn.everystore.pk/a.jpg")


def test_redirect_loop_is_bounded(monkeypatch):
    monkeypatch.setattr(url_fetcher.settings, "max_url_redirects", 1)
    install_client(monkeypatch, [
        FakeStream(status_code=302, headers={"location": "https://cdn.everystore.pk/b.jpg"}),
        FakeStream(status_code=302, headers={"location": "https://cdn.everystore.pk/c.jpg"}),
    ])

    with pytest.raises(UnsafeImageURL):
        fetch_image_bytes("https://cdn.everystore.pk/a.jpg")
