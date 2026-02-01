"""
Smoke test script demonstrating the RAG system end-to-end.

This script demonstrates:
1. Ingesting sample documents
2. Querying with non-streaming response
3. Streaming a query with citations

Run this after starting the system with `make up`.
"""

import requests
import json
import time


BASE_URL = "http://localhost:8000"
API_KEY = "local-key"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def check_health():
    """Check if the system is healthy."""
    print("🏥 Checking system health...")
    response = requests.get(f"{BASE_URL}/health")
    health = response.json()
    
    print(f"  Status: {health['status']}")
    print(f"  Qdrant: {'✅' if health['qdrant_connected'] else '❌'}")
    print(f"  Ollama: {'✅' if health['ollama_connected'] else '❌'}")
    print(f"  Embeddings: {'✅' if health['embedding_model_loaded'] else '❌'}")
    
    return health['status'] == 'healthy'


def ingest_documents():
    """Ingest sample documents."""
    print("\n📥 Ingesting documents...")
    
    payload = {"path": "./docs"}
    response = requests.post(
        f"{BASE_URL}/ingest",
        headers=HEADERS,
        json=payload,
        timeout=300
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"  ✅ Ingested {result['documents_processed']} documents")
        print(f"  📄 Created {result['chunks_created']} chunks")
        print(f"  ⏱️  Time: {result['time_taken_seconds']:.2f}s")
        return True
    else:
        print(f"  ❌ Ingestion failed: {response.status_code}")
        print(f"  {response.text}")
        return False


def query_non_streaming():
    """Test non-streaming query."""
    print("\n💬 Testing non-streaming query...")
    
    payload = {
        "query": "What is machine learning and what are its main types?",
        "top_k": 5
    }
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/query",
        headers=HEADERS,
        json=payload,
        timeout=60
    )
    elapsed = time.time() - start
    
    if response.status_code == 200:
        result = response.json()
        print(f"  ✅ Query successful ({elapsed:.2f}s)")
        print(f"\n  Question: {payload['query']}")
        print(f"\n  Answer: {result['answer'][:300]}...")
        print(f"\n  Sources found: {len(result['sources'])}")
        for i, source in enumerate(result['sources'][:3], 1):
            print(f"    {i}. {source['reference']} (score: {source['score']:.3f})")
        
        print(f"\n  Metrics:")
        print(f"    - Retrieval time: {result['retrieval_time_ms']:.2f}ms")
        print(f"    - Total latency: {result['latency_ms']:.2f}ms")
        print(f"    - Trace ID: {result['trace_id']}")
        
        return True
    else:
        print(f"  ❌ Query failed: {response.status_code}")
        print(f"  {response.text}")
        return False


def query_streaming():
    """Test streaming query."""
    print("\n🌊 Testing streaming query...")
    
    payload = {
        "query": "Explain vector databases and their use in RAG systems",
        "top_k": 5
    }
    
    print(f"  Question: {payload['query']}")
    print(f"\n  Streaming answer:\n  ", end="", flush=True)
    
    response = requests.post(
        f"{BASE_URL}/stream",
        headers=HEADERS,
        json=payload,
        stream=True,
        timeout=60
    )
    
    if response.status_code == 200:
        answer_tokens = []
        usage_data = None
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    
                    if 'delta' in data:
                        token = data['delta']
                        answer_tokens.append(token)
                        print(token, end="", flush=True)
                    
                    elif data.get('complete'):
                        usage_data = data.get('usage', {})
                        print("\n")
                
                except json.JSONDecodeError:
                    continue
        
        print(f"\n  ✅ Streaming complete")
        if usage_data:
            print(f"\n  Metrics:")
            print(f"    - Total tokens: {usage_data.get('tokens_generated', 'N/A')}")
            print(f"    - Retrieval time: {usage_data.get('retrieval_time_ms', 0):.2f}ms")
            print(f"    - Total latency: {usage_data.get('latency_ms', 0):.2f}ms")
            print(f"    - Time to first token: {usage_data.get('time_to_first_token_ms', 0):.2f}ms")
        
        return True
    else:
        print(f"\n  ❌ Streaming failed: {response.status_code}")
        return False


def get_statistics():
    """Get collection statistics."""
    print("\n📊 Collection statistics...")
    
    response = requests.get(
        f"{BASE_URL}/stats",
        headers=HEADERS
    )
    
    if response.status_code == 200:
        stats = response.json()
        print(f"  Collection: {stats['collection_name']}")
        print(f"  Total points: {stats['total_points']}")
        print(f"  Vector dimension: {stats['vector_dim']}")
        print(f"  Distance metric: {stats['distance']}")
        print(f"\n  Documents by source:")
        for source, count in list(stats['documents'].items())[:5]:
            print(f"    - {source}: {count} chunks")
        
        return True
    else:
        print(f"  ❌ Failed to get stats: {response.status_code}")
        return False


def main():
    """Run smoke test suite."""
    print("=" * 70)
    print("RAG SYSTEM SMOKE TEST")
    print("=" * 70)
    
    # Check health
    if not check_health():
        print("\n❌ System is not healthy. Ensure all services are running.")
        print("   Run: make up")
        return False
    
    # Ingest documents
    if not ingest_documents():
        print("\n⚠️  Ingestion failed, but continuing with tests...")
    
    # Wait a moment for indexing
    time.sleep(2)
    
    # Get statistics
    get_statistics()
    
    # Test non-streaming query
    if not query_non_streaming():
        return False
    
    # Test streaming query
    if not query_streaming():
        return False
    
    print("\n" + "=" * 70)
    print("✅ ALL SMOKE TESTS PASSED!")
    print("=" * 70)
    print("\n📖 Next steps:")
    print("  - Open OpenWebUI: http://localhost:3000")
    print("  - Configure OpenAI endpoint: http://rag-api:8000/v1")
    print("  - API key: local-key")
    print("  - Start chatting with your documents!")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
