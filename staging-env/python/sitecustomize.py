"""
Loaded automatically by Python in the staging API container only
(PYTHONPATH points here). Sends Mailtrap requests to the local stand-in named
by MAILTRAP_STAND_IN, so staging never emails real addresses. The app code
is unchanged.
"""
import os

_stand_in = os.environ.get("MAILTRAP_STAND_IN")

if _stand_in:
    try:
        import mailtrap.http as _mailtrap_http

        def _url(self, path, _base=_stand_in.rstrip("/")):
            return f"{_base}/{path.lstrip('/')}"

        _mailtrap_http.HttpClient._url = _url
    except ImportError:
        pass
