from app.storage.vector_ids import chunk_id, doc_id, vector_id


def test_vector_ids_are_deterministic():
    d1 = doc_id("invoice-2025-01.txt")
    d2 = doc_id("invoice-2025-01.txt")
    c1 = chunk_id("Payment terms are net 30.")
    c2 = chunk_id("Payment terms are net 30.")
    v1 = vector_id(d1, c1)
    v2 = vector_id(d2, c2)

    assert d1 == d2
    assert c1 == c2
    assert v1 == v2


def test_vector_id_changes_when_doc_changes_for_same_chunk_text():
    c = chunk_id("Shared clause text")
    v_doc_a = vector_id(doc_id("doc-a"), c)
    v_doc_b = vector_id(doc_id("doc-b"), c)

    assert v_doc_a != v_doc_b
