import os
import hashlib
from typing import List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a text chunk from a document."""
    
    def __init__(
        self,
        text: str,
        source_path: str,
        page: int = None,
        chunk_id: int = 0
    ):
        self.text = text
        self.source_path = source_path
        self.page = page
        self.chunk_id = chunk_id
        self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of chunk for deduplication."""
        content = f"{self.source_path}:{self.text}"
        return hashlib.sha256(content.encode()).hexdigest()


def load_document(file_path: str) -> List[str]:
    """
    Load document and return pages/sections.
    
    Args:
        file_path: Path to document
        
    Returns:
        List of text content (one per page/section)
    """
    ext = Path(file_path).suffix.lower()
    
    if ext == '.pdf':
        return load_pdf(file_path)
    elif ext == '.md':
        return load_markdown(file_path)
    elif ext == '.txt':
        return load_text(file_path)
    else:
        logger.warning(f"Unsupported file type: {ext}, treating as text")
        return load_text(file_path)


def load_pdf(file_path: str) -> List[str]:
    """Load PDF and return pages."""
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(file_path)
        pages = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                pages.append(text)
        
        logger.info(f"Loaded PDF: {file_path} ({len(pages)} pages)")
        return pages
    
    except Exception as e:
        logger.error(f"Error loading PDF {file_path}: {e}")
        return []


def load_markdown(file_path: str) -> List[str]:
    """Load Markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by headers as logical sections
        sections = []
        current_section = []
        
        for line in content.split('\n'):
            if line.startswith('#'):
                if current_section:
                    sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        logger.info(f"Loaded Markdown: {file_path} ({len(sections)} sections)")
        return sections if sections else [content]
    
    except Exception as e:
        logger.error(f"Error loading Markdown {file_path}: {e}")
        return []


def load_text(file_path: str) -> List[str]:
    """Load plain text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Loaded text: {file_path}")
        return [content]
    
    except Exception as e:
        logger.error(f"Error loading text {file_path}: {e}")
        return []


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100
) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Input text
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence ending punctuation
            for punct in ['. ', '.\n', '! ', '?\n', '? ']:
                last_punct = text.rfind(punct, start, end)
                if last_punct != -1:
                    end = last_punct + 1
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - chunk_overlap
        if start >= len(text):
            break
    
    return chunks


def chunk_document(
    pages: List[str],
    source_path: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100
) -> List[DocumentChunk]:
    """
    Chunk a document into overlapping pieces.
    
    Args:
        pages: List of pages/sections from document
        source_path: Source file path
        chunk_size: Target chunk size
        chunk_overlap: Overlap size
        
    Returns:
        List of DocumentChunk objects
    """
    all_chunks = []
    chunk_id = 0
    
    for page_num, page_text in enumerate(pages, 1):
        text_chunks = chunk_text(page_text, chunk_size, chunk_overlap)
        
        for text_chunk in text_chunks:
            chunk = DocumentChunk(
                text=text_chunk,
                source_path=source_path,
                page=page_num if len(pages) > 1 else None,
                chunk_id=chunk_id
            )
            all_chunks.append(chunk)
            chunk_id += 1
    
    logger.info(f"Created {len(all_chunks)} chunks from {source_path}")
    return all_chunks


def process_directory(
    directory: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100
) -> List[DocumentChunk]:
    """
    Recursively process all documents in a directory.
    
    Args:
        directory: Directory path
        chunk_size: Target chunk size
        chunk_overlap: Overlap size
        
    Returns:
        List of all chunks from all documents
    """
    all_chunks = []
    supported_extensions = {'.pdf', '.md', '.txt'}
    
    directory_path = Path(directory)
    if not directory_path.exists():
        logger.error(f"Directory does not exist: {directory}")
        return []
    
    # Find all supported files
    files = []
    for ext in supported_extensions:
        files.extend(directory_path.rglob(f'*{ext}'))
    
    logger.info(f"Found {len(files)} documents in {directory}")
    
    for file_path in files:
        pages = load_document(str(file_path))
        if pages:
            chunks = chunk_document(
                pages,
                str(file_path),
                chunk_size,
                chunk_overlap
            )
            all_chunks.extend(chunks)
    
    logger.info(f"Total chunks created: {len(all_chunks)}")
    return all_chunks
