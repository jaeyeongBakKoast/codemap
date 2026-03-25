import json
from unittest.mock import patch, MagicMock
from codemap.ai.client import AiClient


def test_client_init():
    client = AiClient("http://localhost:11434", "qwen3:30b", "ko")
    assert client.base_url == "http://localhost:11434"
    assert client.model == "qwen3:30b"
    assert client.language == "ko"
    assert client.available is True


def test_client_strips_trailing_slash():
    client = AiClient("http://localhost:11434/", "qwen3:30b")
    assert client.base_url == "http://localhost:11434"


def test_chat_returns_content():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "Hello world"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat("system msg", "user msg")
    assert result == "Hello world"
    assert client.available is True


def test_chat_connection_refused_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_disabled_returns_empty_immediately():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    client._disabled = True
    result = client.chat("system", "user")
    assert result == ""


def test_chat_timeout_retries_once():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "OK"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    from urllib.error import URLError
    import socket
    timeout_err = URLError(socket.timeout("timed out"))

    with patch("urllib.request.urlopen", side_effect=[timeout_err, mock_response]):
        result = client.chat("system", "user")
    assert result == "OK"
    assert client.available is True


def test_chat_timeout_twice_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    from urllib.error import URLError
    import socket
    timeout_err = URLError(socket.timeout("timed out"))

    with patch("urllib.request.urlopen", side_effect=[timeout_err, timeout_err]):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_http_5xx_retries_once():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "OK"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    from urllib.error import HTTPError
    err_500 = HTTPError("http://localhost", 500, "Internal Server Error", {}, None)

    with patch("urllib.request.urlopen", side_effect=[err_500, mock_response]):
        result = client.chat("system", "user")
    assert result == "OK"
    assert client.available is True


def test_chat_http_5xx_twice_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    from urllib.error import HTTPError
    err_500 = HTTPError("http://localhost", 500, "Internal Server Error", {}, None)

    with patch("urllib.request.urlopen", side_effect=[err_500, err_500]):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_json_parses_response():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": '{"key": "value"}'}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result == {"key": "value"}


def test_chat_json_strips_code_fence():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    fenced = '```json\n{"key": "value"}\n```'
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": fenced}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result == {"key": "value"}


def test_chat_json_returns_none_on_invalid_json():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "not json at all"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result is None
