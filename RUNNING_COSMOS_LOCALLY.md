# Running Stock OpenC3 COSMOS and Testing MCP Server

## Environment Limitation

**Note**: Docker is not available in the Claude Code environment, so I cannot run COSMOS directly here. However, I've prepared a complete guide for you to run it on your local machine.

## Stock COSMOS Installation (Your Local Machine)

### Prerequisites

1. **Docker Desktop** installed and running
   - **macOS/Windows**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

2. **System Requirements**
   - Minimum: 8GB RAM, 1 CPU, 80GB disk
   - Recommended: 16GB RAM, 2+ CPUs, 100GB disk

3. **Ports Available**
   - 2900 (COSMOS web interface)
   - 8765 (MCP server, once plugin installed)

### Step-by-Step Installation

#### 1. Clone COSMOS Project

```bash
# Create a directory for COSMOS
mkdir ~/cosmos-test
cd ~/cosmos-test

# Clone the project
git clone https://github.com/OpenC3/cosmos-project.git .

# Verify files
ls -la
# Should see: compose.yaml, openc3.sh, openc3.bat, .env, etc.
```

#### 2. Check Configuration

```bash
# View COSMOS version
cat .env | grep OPENC3_TAG
# Current latest: 6.9.1
```

#### 3. Start COSMOS

**macOS/Linux:**
```bash
./openc3.sh run
```

**Windows:**
```bash
openc3.bat run
```

This will:
- Download COSMOS Docker images (~5-10 minutes first time)
- Start all COSMOS services
- Initialize the database
- Deploy base plugins

**Expected output:**
```
[+] Running 8/8
 ✔ Container cosmos-openc3-redis-1              Started
 ✔ Container cosmos-openc3-redis-ephemeral-1    Started
 ✔ Container cosmos-openc3-minio-1              Started
 ✔ Container cosmos-openc3-traefik-1            Started
 ✔ Container cosmos-openc3-cosmos-cmd-tlm-api-1 Started
 ✔ Container cosmos-openc3-cosmos-script-runner-api-1 Started
 ✔ Container cosmos-openc3-cosmos-init-1        Started
 ✔ Container cosmos-openc3-operator-1           Started
```

#### 4. Verify COSMOS is Running

```bash
# Check containers
docker ps

# You should see ~8 containers running with names like:
# - cosmos-openc3-operator-1
# - cosmos-openc3-cosmos-cmd-tlm-api-1
# - cosmos-openc3-minio-1
# - cosmos-openc3-redis-1
# etc.
```

**Access web interface:**
- URL: http://localhost:2900
- First time: Set a password (minimum 8 characters)
- You should see the COSMOS home screen

#### 5. Install Demo Plugin

The demo plugin provides test targets (INST, INST2, EXAMPLE, etc.) for testing the MCP server.

**Via Web UI:**
1. Navigate to http://localhost:2900/tools/admin
2. Click **Plugins** tab
3. The `openc3-cosmos-demo` plugin should already be in the list
4. If not installed, click the upload button and browse to install it

**Via CLI:**
```bash
# The demo plugin is typically pre-installed
# Check if it's there:
docker exec cosmos-openc3-operator-1 ls /plugins/DEFAULT/

# Should see: openc3-cosmos-demo and tool plugins
```

#### 6. Verify Targets

1. Go to http://localhost:2900/tools/cmdtlmserver
2. You should see interfaces:
   - INST_INT
   - INST2_INT
   - EXAMPLE_INT
   - TEMPLATED_INT
3. All should show as "Connected" (green)

Now COSMOS is running with demo targets ready for testing!

## Installing MCP Server Plugin

### 1. Copy Plugin to COSMOS Machine

If you're running COSMOS on the same machine as this repo:

```bash
# Copy the gem file
cp /home/user/openc3_cosmos/openc3-cosmos-mcp-server/openc3-cosmos-mcp-server-0.1.0.gem ~/cosmos-test/
```

If COSMOS is on a different machine:
```bash
# Use scp, or download from GitHub, or copy via USB
```

### 2. Install via Admin UI

1. Open http://localhost:2900/tools/admin
2. Click **Plugins** tab
3. Click **"Upload Plugin"** button
4. Select `openc3-cosmos-mcp-server-0.1.0.gem`
5. Keep default settings:
   - mcp_server_port: 8765
   - mcp_microservice_name: OPENC3_MCP_SERVER
6. Click **Install**
7. Wait for installation (should take < 30 seconds)

### 3. Verify MCP Server Installation

**Check microservice status:**
1. Go to http://localhost:2900/tools/cmdtlmserver
2. Look for **OPENC3_MCP_SERVER** in the microservices list
3. Status should be **Running** (green)

**Check health endpoint:**
```bash
curl http://localhost:8765/health
```

Expected response:
```json
{
  "status": "ok",
  "cosmos_connected": true,
  "scope": "DEFAULT",
  "targets_count": 5
}
```

**If health check fails:**
```bash
# Check logs
docker logs cosmos-openc3-operator-1 | grep mcp_server

# Check if port is accessible
docker exec cosmos-openc3-operator-1 curl http://localhost:8765/health

# Verify Python dependencies
docker exec cosmos-openc3-operator-1 python3 -m pip list | grep fastapi
```

### 4. Test MCP Resources Directly

```bash
# List all resources
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "resources/list",
    "params": {}
  }' | jq

# Get target list
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/list"}
  }' | jq

# Get INST command file
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/INST/cmd_file"}
  }' | jq -r '.result.contents[0].text'
```

## Configure Claude Code

### 1. Edit Configuration File

**macOS:**
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```powershell
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

### 2. Add MCP Server Configuration

```json
{
  "mcpServers": {
    "cosmos": {
      "transport": {
        "type": "http",
        "url": "http://localhost:8765"
      }
    }
  }
}
```

If you already have other MCP servers configured, add the `cosmos` entry to the existing `mcpServers` object.

### 3. Restart Claude Code

Completely quit Claude Desktop and restart it for the configuration to take effect.

## Testing with Claude Code

Once Claude Code is restarted, open a new conversation and try these questions:

### Test 1: Discovery
```
What MCP servers are available?
```
Expected: Should list "cosmos" among available servers

### Test 2: Target List
```
What targets are configured in COSMOS?
```
Expected: Should list INST, INST2, EXAMPLE, TEMPLATED, SYSTEM

### Test 3: Command Definitions
```
Show me the command definitions for the INST target
```
Expected: Should display the raw cmd.txt file content

### Test 4: Telemetry Analysis
```
What telemetry packets does INST send?
```
Expected: Should parse tlm.txt and list packet names

### Test 5: Detailed Analysis
```
Explain the INST COLLECT command and its parameters in detail
```
Expected: Should parse the COLLECT command definition and explain each parameter

See `TESTING_CLAUDE_CODE.md` for 22 comprehensive test scenarios!

## Troubleshooting

### COSMOS Won't Start

**Check Docker:**
```bash
docker --version
docker compose version
```

**Check disk space:**
```bash
df -h
```

**Check logs:**
```bash
docker logs cosmos-openc3-operator-1
docker logs cosmos-openc3-cosmos-cmd-tlm-api-1
```

### MCP Server Won't Install

**Check Python:**
```bash
docker exec cosmos-openc3-operator-1 python3 --version
# Should be Python 3.9+
```

**Check Ruby:**
```bash
docker exec cosmos-openc3-operator-1 ruby --version
# Should be Ruby 3.x
```

**Manual installation:**
```bash
# Copy gem into container
docker cp openc3-cosmos-mcp-server-0.1.0.gem cosmos-openc3-operator-1:/tmp/

# Install via CLI
docker exec cosmos-openc3-operator-1 openc3cli load /tmp/openc3-cosmos-mcp-server-0.1.0.gem DEFAULT
```

### Claude Code Can't Connect

**Verify from host machine:**
```bash
curl http://localhost:8765/health
```

**Check Docker port mapping:**
```bash
docker ps | grep 8765
```

**Try telnet:**
```bash
telnet localhost 8765
```

**Check firewall:**
- Ensure localhost traffic is allowed
- On macOS: System Preferences → Security & Privacy → Firewall
- On Windows: Windows Defender Firewall

## Alternative: Remote COSMOS

If COSMOS is running on a different machine:

### Update MCP Config

```json
{
  "mcpServers": {
    "cosmos": {
      "transport": {
        "type": "http",
        "url": "http://192.168.1.100:8765"
      }
    }
  }
}
```

Replace `192.168.1.100` with your COSMOS machine's IP.

### Expose Port on COSMOS Machine

If using Docker on remote machine:

**Edit compose.yaml:**
```yaml
services:
  openc3-operator:
    ports:
      - "8765:8765"  # Add this line
```

**Restart COSMOS:**
```bash
./openc3.sh stop
./openc3.sh run
```

## Success Checklist

- ✅ Docker installed and running
- ✅ COSMOS project cloned
- ✅ COSMOS started (./openc3.sh run)
- ✅ Web UI accessible (http://localhost:2900)
- ✅ Demo plugin installed
- ✅ Targets visible in CmdTlmServer
- ✅ MCP server plugin installed
- ✅ MCP microservice running
- ✅ Health endpoint responds (curl http://localhost:8765/health)
- ✅ MCP resources accessible (curl test)
- ✅ Claude Code configured
- ✅ Claude Code restarted
- ✅ Claude can list targets
- ✅ Claude can read cmd/tlm files

## Quick Start Script

Save this as `start-cosmos-mcp.sh`:

```bash
#!/bin/bash

# Start COSMOS
cd ~/cosmos-test
./openc3.sh run

# Wait for COSMOS to be ready
echo "Waiting for COSMOS to start..."
sleep 30

# Check if COSMOS is running
curl -s http://localhost:2900 > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ COSMOS is running at http://localhost:2900"
else
    echo "✗ COSMOS is not responding"
    exit 1
fi

# Install MCP server if not already installed
echo "To install MCP server:"
echo "1. Go to http://localhost:2900/tools/admin"
echo "2. Upload openc3-cosmos-mcp-server-0.1.0.gem"
echo "3. Configure Claude Code MCP settings"
echo ""
echo "MCP Server Configuration:"
echo '{
  "mcpServers": {
    "cosmos": {
      "transport": {
        "type": "http",
        "url": "http://localhost:8765"
      }
    }
  }
}'
```

Run with:
```bash
chmod +x start-cosmos-mcp.sh
./start-cosmos-mcp.sh
```

## Next Steps

Once everything is working:

1. **Explore with Claude**: Ask questions about your target configurations
2. **Generate docs**: Have Claude create markdown docs from configs
3. **Validate configs**: Ask Claude to check for potential issues
4. **Compare targets**: Analyze differences between target structures
5. **Learn COSMOS**: Use Claude to understand COSMOS configuration format

Happy testing! 🚀
