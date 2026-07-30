from django.urls import reverse


def test_home_includes_interactive_region_panel_states(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b'id="weather-panel"' in response.content
    assert b'hx-sync="this:replace"' in response.content
    assert b'id="region-panel-loading"' in response.content
    assert b'id="region-panel-error"' in response.content
    assert b"data-region-panel-retry" in response.content
