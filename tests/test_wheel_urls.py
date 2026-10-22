import hashlib
import io
from urllib.parse import quote, urljoin

import pytest

from wheel_stub.wheel import WheelFilter, download_manual


@pytest.mark.parametrize(
    "prefix",
    ["", "../files/", "https://files.example.org/"],
)
@pytest.mark.parametrize("version", ["1!1.6.51rc1", "1.4.98rc1+local"])
def test_wheel_filter_decodes_filename_and_preserves_url(prefix, version):
    filename = f"isaacteleop-{version}-py3-none-any.whl"
    encoded_filename = quote(filename, safe="")
    href = f"{prefix}{encoded_filename}"
    project_url = "https://example.org/isaacteleop/"
    parser = WheelFilter(project_url=project_url)

    parser.feed(f'<a href="{href}#sha256=abc123">download</a>')

    wheel_url, wheel_filename, digest = parser.wheel_files[0]
    assert wheel_filename == filename
    assert encoded_filename in wheel_url
    assert wheel_url.split("#")[0] == urljoin(project_url, href)
    assert digest == ("sha256", "abc123")


@pytest.mark.parametrize("version", ["1.4.98rc1", "1!1.6.51rc1"])
def test_download_manual_with_encoded_epoch_in_index(monkeypatch, tmp_path, version):
    payload = b"wheel contents"
    digest = hashlib.sha256(payload).hexdigest()
    epoch_filename = "isaacteleop-1!1.6.51rc1-py3-none-any.whl"
    older_filename = "isaacteleop-1.4.98rc1-py3-none-any.whl"
    html = "".join(
        f'<a href="{quote(filename, safe="")}#sha256={digest}">download</a>'
        for filename in [epoch_filename, older_filename]
    )
    project_url = "https://example.org/isaacteleop/"
    filename = f"isaacteleop-{version}-py3-none-any.whl"
    expected_url = project_url + quote(filename, safe="")
    requested_urls = []

    def fake_urlopen(url):
        requested_urls.append(url)
        if url == project_url:
            return io.BytesIO(html.encode())
        assert url == expected_url
        return io.BytesIO(payload)

    monkeypatch.setattr("wheel_stub.wheel.urlopen_with_retry", fake_urlopen)

    result = download_manual(
        tmp_path, "isaacteleop", version, {"index_url": "https://example.org/"}
    )

    assert result == filename
    assert (tmp_path / filename).read_bytes() == payload
    assert requested_urls == [project_url, expected_url]
