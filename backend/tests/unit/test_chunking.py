from app.services.chunking import chunk_text_with_tiktoken, clean_text, content_hash


def test_clean_text_normalizes_whitespace() -> None:
    assert clean_text("A\n\nB\tC   D") == "A B C D"


def test_chunk_text_respects_overlap() -> None:
    text = " ".join([f"token{i}" for i in range(1200)])
    chunks = chunk_text_with_tiktoken(text, chunk_tokens=120, overlap_tokens=20)

    assert len(chunks) > 5
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].content
    assert chunks[-1].content


def test_content_hash_consistency() -> None:
    assert content_hash("A   B") == content_hash("A B")
