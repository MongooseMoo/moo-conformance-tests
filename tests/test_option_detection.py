from types import SimpleNamespace

from moo_conformance.test_conformance import _has_option


class FailingTransport:
    def execute(self, _code: str):
        raise AssertionError("manifest-backed option detection must not probe the server")


def test_has_option_uses_validated_profile_feature_before_server_probe():
    runner = SimpleNamespace(transport=FailingTransport())

    assert _has_option(
        runner,
        "PROMOTE_NUMBERS",
        {"option.PROMOTE_NUMBERS": True},
    )
