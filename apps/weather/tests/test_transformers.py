from apps.weather.services.transformers import normalize_forecast


def test_normalize_forecast_returns_payload():
    payload = {"temperature": 12}

    assert normalize_forecast(payload) == payload
