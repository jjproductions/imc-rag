from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Header
from typing import Optional, List
import os
import tempfile
import shutil
from datetime import datetime
import time
import logging

from app.models.schemas import IngestRequest, IngestResponse
from app.utils.chunking import process_directory, load_document, chunk_document
from app.services.embeddings import get_embedding_service
from app.services.qdrant_client import get_qdrant_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def verify_api_key(authorization: str = Header(...)):
    """Verify API key from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    path: Optional[str] = None,
    files: Optional[List[UploadFile]] = File(None),
    _: None = Depends(verify_api_key)
):
    """
    Ingest documents into the vector database.
    
    Supports:
    - path: Directory or file path to ingest
    - files: Uploaded files
    """
    start_time = time.time()
    
    embedding_service = get_embedding_service()
    qdrant_service = get_qdrant_service()
    
    all_chunks = []
    doc_ids = set()
    
    # Process path-based ingestion
    if path:
        logger.info(f"Ingesting from path: {path}")
        
        if os.path.isdir(path):
            all_chunks.extend(
                process_directory(path, settings.chunk_size, settings.chunk_overlap)
            )
        elif os.path.isfile(path):
            pages = load_document(path)
            chunks = chunk_document(
                pages,
                path,
                settings.chunk_size,
                settings.chunk_overlap
            )
            all_chunks.extend(chunks)
        else:
            raise HTTPException(status_code=400, detail=f"Path not found: {path}")
    
    # Process uploaded files
    if files:
        logger.info(f"Processing {len(files)} uploaded files")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for upload_file in files:
                # Save to temp location
                temp_path = os.path.join(temp_dir, upload_file.filename)
                with open(temp_path, 'wb') as f:
                    shutil.copyfileobj(upload_file.file, f)
                
                # Process file
                pages = load_document(temp_path)
                chunks = chunk_document(
                    pages,
                    upload_file.filename,
                    settings.chunk_size,
                    settings.chunk_overlap
                )
                all_chunks.extend(chunks)
    
    if not all_chunks:
        raise HTTPException(status_code=400, detail="No documents to ingest")
    
    # Generate embeddings in batches
    logger.info(f"Generating embeddings for {len(all_chunks)} chunks")
    texts = [chunk.text for chunk in all_chunks]
    embeddings = embedding_service.embed_batch(texts, batch_size=32)
    
    # Prepare points for Qdrant
    points = []
    for i, (chunk, embedding) in enumerate(zip(all_chunks, embeddings)):
        doc_id = os.path.basename(chunk.source_path)
        doc_ids.add(doc_id)
        
        point = {
            'id': f"{doc_id}_{chunk.chunk_id}_{chunk.hash[:8]}",
            'vector': embedding,
            'payload': {
                'doc_id': doc_id,
                'chunk_id': chunk.chunk_id,
                'text': chunk.text,
                'source_path': chunk.source_path,
                'page': chunk.page,
                'hash': chunk.hash,
                'created_at': datetime.utcnow().isoformat()
            }
        }
        points.append(point)
    
    # Upsert to Qdrant (idempotent)
    inserted_count = qdrant_service.upsert_points(points)
    
    time_taken = time.time() - start_time
    
    logger.info(
        f"✅ Ingestion complete: {len(doc_ids)} documents, "
        f"{len(all_chunks)} chunks, {inserted_count} new points in {time_taken:.2f}s"
    )
    
    return IngestResponse(
        status="success",
        documents_processed=len(doc_ids),
        chunks_created=len(all_chunks),
        time_taken_seconds=time_taken,
        doc_ids=list(doc_ids)
    )


async def ingest_directory(directory_path: str):
    """Helper function for CLI ingestion."""
    all_chunks = process_directory(
        directory_path,
        settings.chunk_size,
        settings.chunk_overlap
    )
    
    if not all_chunks:
        print(f"No documents found in {directory_path}")
        return
    
    embedding_service = get_embedding_service()
    qdrant_service = get_qdrant_service()
    
    # Generate embeddings
    texts = [chunk.text for chunk in all_chunks]
    embeddings = embedding_service.embed_batch(texts, batch_size=32)
    
    # Prepare points
    points = []
    for chunk, embedding in zip(all_chunks, embeddings):
        doc_id = os.path.basename(chunk.source_path)
        
        point = {
            'id': f"{doc_id}_{chunk.chunk_id}_{chunk.hash[:8]}",
            'vector': embedding,
            'payload': {
                'doc_id': doc_id,
                'chunk_id': chunk.chunk_id,
                'text': chunk.text,
                'source_path': chunk.source_path,
                'page': chunk.page,
                'hash': chunk.hash,
                'created_at': datetime.utcnow().isoformat()
            }
        }
        points.append(point)
    
    # Upsert
    inserted = qdrant_service.upsert_points(points)
    print(f"✅ Ingested {len(all_chunks)} chunks ({inserted} new)")
