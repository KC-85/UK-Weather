from django.urls import reverse


def test_search_returns_partial(client):
    response = client.get(reverse("locations:search"), {"query": "Cardiff"})

    assert response.status_code == 200
    assert b"Cardiff" in response.content
