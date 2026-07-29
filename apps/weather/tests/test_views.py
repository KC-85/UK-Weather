from django.urls import reverse


def test_weather_detail(client):
    response = client.get(reverse("weather:detail", args=["london"]))

    assert response.status_code == 200
