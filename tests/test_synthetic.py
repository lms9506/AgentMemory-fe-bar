"""Tests for synthetic data generation."""

from agent_memory.synthetic import generate_dataset


def test_generate_dataset_reproducible():
    a = generate_dataset(client_count=3, sessions_per_client=1, seed=99)
    b = generate_dataset(client_count=3, sessions_per_client=1, seed=99)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_generate_dataset_shape():
    ds = generate_dataset(client_count=2, sessions_per_client=2, seed=1)
    assert len(ds.clients) == 2
    assert len(ds.portfolios) == 2
    assert len(ds.conversations) == 4
    assert ds.clients[0].client_id == "client_0000"
    assert all(c.client_id == p.client_id for c, p in zip(ds.clients, ds.portfolios, strict=True))
