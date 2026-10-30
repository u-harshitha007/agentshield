#!/bin/bash
# Run model evaluation

set -e

echo "=== AgentShield Model Evaluation ==="
echo ""
echo "Checking Ollama..."

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "ERROR: Ollama not running. Start it first:"
    echo "  Windows: Start Ollama from Start Menu"
    echo "  Mac/Linux: ollama serve"
    exit 1
fi

echo "✓ Ollama is running"
echo ""

# List available models
echo "Available models:"
curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4

echo ""
echo "Running evaluation..."
echo ""

# Run Python evaluation
python eval/model_eval.py

echo ""
echo "✓ Evaluation complete"
echo "Results saved to docs/model-eval.md"
