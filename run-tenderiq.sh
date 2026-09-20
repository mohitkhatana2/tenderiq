#!/bin/zsh
# Starts TenderIQ from a clean Apple Silicon or Intel Mac without Homebrew.
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
NODE_VERSION="22.14.0"
ARCH="$(uname -m)"
[[ "$ARCH" == "arm64" ]] && NODE_ARCH="arm64" || NODE_ARCH="x64"

mkdir -p "$TOOLS_DIR"

if [[ ! -x "$TOOLS_DIR/node/bin/node" ]]; then
  echo "Installing local Node.js runtime…"
  curl -fL -o /tmp/tenderiq-node.tar.gz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-darwin-${NODE_ARCH}.tar.gz"
  tar -xzf /tmp/tenderiq-node.tar.gz -C "$TOOLS_DIR"
  mv "$TOOLS_DIR/node-v${NODE_VERSION}-darwin-${NODE_ARCH}" "$TOOLS_DIR/node"
fi
export PATH="$TOOLS_DIR/node/bin:$PATH"

if [[ ! -x "$TOOLS_DIR/uv/uv" ]]; then
  echo "Installing local Python manager…"
  UV_INSTALL_DIR="$TOOLS_DIR/uv" UV_NO_MODIFY_PATH=1 sh -c "$(curl -LsSf https://astral.sh/uv/0.5.14/install.sh)"
fi

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  echo "Installing Python and API dependencies…"
  UV_CACHE_DIR="$TOOLS_DIR/cache" UV_PYTHON_INSTALL_DIR="$TOOLS_DIR/python" "$TOOLS_DIR/uv/uv" python install 3.12
  UV_CACHE_DIR="$TOOLS_DIR/cache" UV_PYTHON_INSTALL_DIR="$TOOLS_DIR/python" "$TOOLS_DIR/uv/uv" venv --python 3.12 "$ROOT_DIR/backend/.venv"
  UV_CACHE_DIR="$TOOLS_DIR/cache" "$TOOLS_DIR/uv/uv" pip install --python "$ROOT_DIR/backend/.venv/bin/python" -r "$ROOT_DIR/backend/requirements.txt"
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing web dependencies…"
  NPM_CONFIG_CACHE="$TOOLS_DIR/npm-cache" npm install --prefix "$ROOT_DIR/frontend"
fi

echo "Starting TenderIQ at http://localhost:5173"
cd "$ROOT_DIR/backend"
./.venv/bin/uvicorn app.main:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT INT TERM
cd "$ROOT_DIR"
npm run dev --prefix frontend
