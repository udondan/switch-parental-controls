"""Workarounds for pynintendoparental until fixes are released upstream."""

# Since 2026-11-26 the Nintendo API rejects app version 2.6.0 (build 700), which
# pynintendoparental<=2.7.0 sends, with HTTP 400 "update_required".
# See https://github.com/pantherale0/pynintendoparental/issues/164.
# Remove this module once a pynintendoparental release sends 2.7.0 or newer.
APP_VERSION = "2.7.0"
APP_BUILD = "740"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def patch_app_version() -> bool:
    """Make pynintendoparental send APP_VERSION/APP_BUILD in its request headers.

    The headers are built from module-level constants of pynintendoparental.api on
    every request, so overriding them there takes effect for all clients.

    Does nothing if pynintendoparental already sends the same or a newer version.
    Returns True if the constants were patched.
    """
    from pynintendoparental import api, const

    if _version_tuple(api.MOBILE_APP_VERSION) >= _version_tuple(APP_VERSION):
        return False

    user_agent = f"moon_ANDROID/{APP_VERSION} ({const.MOBILE_APP_PKG}; build:{APP_BUILD}; {const.OS_STR})"
    for module in (api, const):
        module.MOBILE_APP_VERSION = APP_VERSION
        module.MOBILE_APP_BUILD = APP_BUILD
        module.USER_AGENT = user_agent
    return True
