from unittest.mock import Mock, patch

import pytest

from sf_config_debt_radar.auth import SFClient


@patch("sf_config_debt_radar.auth.build_requests_auth", return_value=(None, None))
@pytest.mark.parametrize(
    ("base_url", "message"),
    [
        ("http://api55.sapsf.eu/odata/v2", "HTTPS"),
        ("https://user:pass@api55.sapsf.eu/odata/v2", "Invalid"),
        ("https://api55.sapsf.eu/odata/v2?tenant=other", "Invalid"),
        ("https://api55.sapsf.eu/odata/v2#fragment", "Invalid"),
    ],
)
def test_client_rejects_unsafe_base_url(_build_auth, base_url, message):
    with pytest.raises(ValueError, match=message):
        SFClient(
            base_url=base_url,
            username="admin@ACME",
            password="secret",
        )


@pytest.fixture
def client():
    with patch(
        "sf_config_debt_radar.auth.build_requests_auth", return_value=(None, None)
    ):
        return SFClient(
            base_url="https://api55.sapsf.eu/odata/v2",
            username="admin@ACME",
            password="secret",
        )


def test_get_allows_relative_and_same_service_full_urls(client):
    client.session.get = Mock(return_value=Mock())

    client.get("EmpJob?$top=1")
    client.get("https://api55.sapsf.eu/odata/v2/PerPerson?$top=1")

    assert [call.args[0] for call in client.session.get.call_args_list] == [
        "https://api55.sapsf.eu/odata/v2/EmpJob?$top=1",
        "https://api55.sapsf.eu/odata/v2/PerPerson?$top=1",
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example/collect",
        "https://api55.sapsf.eu/oauth/token",
        "http://api55.sapsf.eu/odata/v2/EmpJob",
        "https://api55.sapsf.eu:444/odata/v2/EmpJob",
        "https://user:pass@api55.sapsf.eu/odata/v2/EmpJob",
    ],
)
def test_get_rejects_credentialed_urls_outside_configured_service(client, url):
    client.session.get = Mock()

    with pytest.raises(Exception, match="Rejected"):
        client.get(url)

    client.session.get.assert_not_called()
