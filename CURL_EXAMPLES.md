# cURL Examples for RAG API

This document provides copy-paste cURL commands for testing the RAG API.

## Environment Setup

```bash
export API_KEY="local-key"
export BASE_URL="http://localhost:8000"
```

## Health Check

```bash
# Check system health (no auth required)
curl -X GET $BASE_URL/health | jq .
```

## Ingestion

### Ingest a directory

```bash
curl -X POST $BASE_URL/ingest \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "./docs"
  }' | jq .
```

### Ingest a single file upload

```bash
curl -X POST $BASE_URL/ingest \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@./docs/architecture.txt"
```

## Query (Non-Streaming)

### Basic query

```bash
curl -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "top_k": 5
  }' | jq .
```

### Query with custom temperature

```bash
curl -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain vector databases",
    "top_k": 3,
    "temperature": 0.1
  }' | jq .
```

## Streaming Query (SSE)

### Stream with custom format

```bash
curl -N -X POST $BASE_URL/stream \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the types of machine learning?",
    "top_k": 5
  }'
```

### Save streaming output to file

```bash
curl -N -X POST $BASE_URL/stream \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain RAG architecture",
    "top_k": 5
  }' > stream_output.txt
```

## OpenAI-Compatible Endpoints

### Non-streaming chat completion

```bash
curl -X POST $BASE_URL/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "messages": [
      {
        "role": "user",
        "content": "What is reinforcement learning?"
      }
    ],
    "stream": false
  }' | jq .
```

### Streaming chat completion

```bash
curl -N -X POST $BASE_URL/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "messages": [
      {
        "role": "user",
        "content": "Explain vector similarity search"
      }
    ],
    "stream": true,
    "temperature": 0.2
  }'
```

### Multi-turn conversation

```bash
curl -X POST $BASE_URL/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "messages": [
      {
        "role": "user",
        "content": "What is machine learning?"
      },
      {
        "role": "assistant",
        "content": "Machine learning is a subset of AI..."
      },
      {
        "role": "user",
        "content": "What are its main types?"
      }
    ],
    "stream": false
  }' | jq .
```

## Statistics

### Get collection stats

```bash
curl -X GET $BASE_URL/stats \
  -H "Authorization: Bearer $API_KEY" | jq .
```

## Error Cases

### Missing API key

```bash
curl -X POST $BASE_URL/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test"
  }'
# Expected: 401 Unauthorized
```

### Invalid API key

```bash
curl -X POST $BASE_URL/query \
  -H "Authorization: Bearer wrong-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test"
  }'
# Expected: 401 Unauthorized
```

### Empty query

```bash
curl -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": ""
  }'
# Expected: 422 Validation Error
```

## Processing Streaming Output

### Extract just the text deltas

```bash
curl -N -X POST $BASE_URL/stream \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain embeddings"}' \
  | while read line; do
      echo "$line" | jq -r 'select(.delta != null) | .delta' 2>/dev/null
    done
```

### Extract final usage metrics

```bash
curl -N -X POST $BASE_URL/stream \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}' \
  | grep -o '{"complete":true.*}' \
  | jq .usage
```

## Batch Processing

### Ingest multiple files

```bash
for file in ./docs/*.md; do
  echo "Ingesting $file..."
  curl -X POST $BASE_URL/ingest \
    -H "Authorization: Bearer $API_KEY" \
    -F "file=@$file"
  sleep 1
done
```

### Query multiple questions

```bash
questions=(
  "What is machine learning?"
  "Explain vector databases"
  "What is RAG?"
)

for question in "${questions[@]}"; do
  echo "Querying: $question"
  curl -X POST $BASE_URL/query \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$question\"}" \
    | jq -r '.answer' \
    | head -c 200
  echo -e "\n---\n"
done
```

## Performance Testing

### Measure query latency

```bash
time curl -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "top_k": 5
  }' -o /dev/null -s
```

### Concurrent requests

```bash
for i in {1..5}; do
  curl -X POST $BASE_URL/query \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "test query '$i'"}' &
done
wait
```

## Debugging

### Verbose output with headers

```bash
curl -v -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### Show timing information

```bash
curl -w "\nTime: %{time_total}s\n" \
  -X POST $BASE_URL/query \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is ML?"}'
```
