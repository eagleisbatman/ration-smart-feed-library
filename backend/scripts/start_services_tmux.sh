#!/bin/bash

# Feed Formulation Backend - tmux Service Starter
# This script starts the server and ngrok in separate tmux sessions
# Run this script from the project root directory

# Get the project root directory (parent of scripts directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Starting Feed Formulation Services with tmux..."
echo "📁 Project root: $PROJECT_ROOT"

# Kill existing sessions if they exist
echo "🔄 Cleaning up existing sessions..."
tmux kill-session -t feed-server 2>/dev/null
tmux kill-session -t feed-ngrok 2>/dev/null

# Start the server in tmux session
echo "📡 Starting server in tmux session..."
tmux new-session -d -s feed-server
tmux send-keys -t feed-server "cd $PROJECT_ROOT" Enter
tmux send-keys -t feed-server "source .venv/bin/activate" Enter
tmux send-keys -t feed-server "echo 'Server starting...'" Enter
tmux send-keys -t feed-server "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" Enter

# Wait a moment for server to start
sleep 3

# Start ngrok in tmux session
echo "🌐 Starting ngrok in tmux session..."
tmux new-session -d -s feed-ngrok
tmux send-keys -t feed-ngrok "cd $PROJECT_ROOT" Enter
tmux send-keys -t feed-ngrok "echo 'ngrok starting...'" Enter
tmux send-keys -t feed-ngrok "ngrok http 8000" Enter

# Wait a moment for ngrok to start
sleep 3

# Show session status
echo "✅ Services started in tmux sessions:"
echo ""
echo "📋 Available sessions:"
tmux list-sessions
echo ""
echo "🔧 Management commands:"
echo "  Attach to server:    tmux a -t feed-server"
echo "  Attach to ngrok:     tmux a -t feed-ngrok"
echo "  List sessions:       tmux ls"
echo "  Kill server:         tmux kill-session -t feed-server"
echo "  Kill ngrok:          tmux kill-session -t feed-ngrok"
echo ""
echo "🌐 Check ngrok URL:"
echo "  curl -s http://localhost:4040/api/tunnels | python -m json.tool"
echo ""
echo "📡 Test server:"
echo "  curl -s http://localhost:8000/ | python -m json.tool"
echo ""
echo "🎉 Services are running! You can now lock your MacBook." 