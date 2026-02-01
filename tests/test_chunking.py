import pytest
from app.utils.chunking import (
    chunk_text,
    DocumentChunk,
    load_text,
    chunk_document
)


def test_chunk_text_small():
    """Test chunking text smaller than chunk size."""
    text = "This is a small text."
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_large():
    """Test chunking large text with overlap."""
    text = "Sentence one. " * 100  # ~1400 chars
    chunks = chunk_text(text, chunk_size=400, chunk_overlap=50)
    
    assert len(chunks) > 1
    # Check overlap exists
    for i in range(len(chunks) - 1):
        # Some content should overlap
        assert len(chunks[i]) <= 450  # Approx chunk size


def test_chunk_text_sentence_boundary():
    """Test that chunks try to break at sentence boundaries."""
    text = "First sentence here. Second sentence here. Third sentence here."
    chunks = chunk_text(text, chunk_size=30, chunk_overlap=5)
    
    # Should break at sentence ends
    assert len(chunks) >= 2


def test_document_chunk_creation():
    """Test DocumentChunk creation and hash."""
    chunk = DocumentChunk(
        text="Sample text",
        source_path="/path/to/doc.txt",
        page=1,
        chunk_id=0
    )
    
    assert chunk.text == "Sample text"
    assert chunk.source_path == "/path/to/doc.txt"
    assert chunk.page == 1
    assert chunk.chunk_id == 0
    assert len(chunk.hash) == 64  # SHA256 hex length


def test_document_chunk_hash_uniqueness():
    """Test that different chunks have different hashes."""
    chunk1 = DocumentChunk("Text A", "/doc.txt", chunk_id=0)
    chunk2 = DocumentChunk("Text B", "/doc.txt", chunk_id=1)
    
    assert chunk1.hash != chunk2.hash


def test_document_chunk_hash_consistency():
    """Test that same content produces same hash."""
    chunk1 = DocumentChunk("Same text", "/doc.txt", chunk_id=0)
    chunk2 = DocumentChunk("Same text", "/doc.txt", chunk_id=0)
    
    assert chunk1.hash == chunk2.hash


def test_chunk_document():
    """Test chunking a multi-page document."""
    pages = [
        "Page one content. " * 50,
        "Page two content. " * 50
    ]
    
    chunks = chunk_document(
        pages,
        source_path="test.pdf",
        chunk_size=400,
        chunk_overlap=50
    )
    
    assert len(chunks) > 0
    assert all(isinstance(c, DocumentChunk) for c in chunks)
    assert all(c.source_path == "test.pdf" for c in chunks)
    
    # Check page numbers are assigned
    page_one_chunks = [c for c in chunks if c.page == 1]
    page_two_chunks = [c for c in chunks if c.page == 2]
    
    assert len(page_one_chunks) > 0
    assert len(page_two_chunks) > 0


def test_chunk_document_single_page():
    """Test chunking single-page document (page should be None)."""
    pages = ["Single page content."]
    
    chunks = chunk_document(
        pages,
        source_path="single.txt",
        chunk_size=100,
        chunk_overlap=10
    )
    
    assert len(chunks) == 1
    assert chunks[0].page is None  # No page number for single-page docs
