# Installation and Testing Guide

## Quick Start

This guide walks you through installing and testing the OpenC3 COSMOS MCP Server plugin with Claude Code.

## Prerequisites

1. **OpenC3 COSMOS Running**
   - COSMOS instance running locally or accessible
   - Demo plugin installed (for test targets)
   - Admin interface accessible at http://localhost:2900

2. **Claude Code**
   - Claude for Desktop installed (or compatible MCP client)
   - Ability to edit MCP server configuration

## Step 1: Install the Plugin

### Option A: Via Admin UI (Recommended)

1. Open COSMOS Admin: http://localhost:2900/tools/admin

2. Click on the **Plugins** tab

3. Click **"Upload Plugin"** button

4. Select `openc3-cosmos-mcp-server-0.1.0.gem` from this directory

5. Configure variables (or use defaults):
   - **mcp_server_port**: 8765
   - **mcp_microservice_name**: OPENC3_MCP_SERVER

6. Click **"Install"**

7. Wait for installation to complete (check status in Admin interface)

### Option B: Via CLI

```bash
# Copy gem to COSMOS project
cp openc3-cosmos-mcp-server-0.1.0.gem /path/to/cosmos-project/

# Install via CLI
cd /path/to/cosmos-project/
./openc3.sh cli load openc3-cosmos-mcp-server-0.1.0.gem DEFAULT
```

## Step 2: Verify Installation

### Check Microservice Status

1. Open **CmdTlmServer**: http://localhost:2900/tools/cmdtlmserver

2. Look for microservice named **OPENC3_MCP_SERVER** in the list

3. Status should show as **Running** (green)

### Test Health Endpoint

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

If this doesn't work:
- Check Docker port forwarding: `docker ps | grep 8765`
- Check logs: `docker logs cosmos-openc3-operator-1 | grep mcp_server`
- Try from inside container: `docker exec cosmos-openc3-operator-1 curl http://localhost:8765/health`

### Test MCP Protocol

```bash
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "resources/list",
    "params": {}
  }'
```

Expected: Long JSON response with list of resources

## Step 3: Configure Claude Code

### Find Configuration File

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Add MCP Server

Edit the config file and add:

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

If you already have other MCP servers, add the `cosmos` entry to the existing `mcpServers` object.

### Restart Claude Code

Completely quit and restart Claude Desktop for changes to take effect.

## Step 4: Test with Claude Code

### Test 1: Discover MCP Server

Start a new conversation and ask:

```
What MCP servers are available?
```

You should see "cosmos" in the list.

### Test 2: List Targets

Ask:

```
What targets are configured in COSMOS?
```

Expected response should include: INST, INST2, EXAMPLE, TEMPLATED, SYSTEM

### Test 3: Read Command Definitions

Ask:

```
Show me the command definitions for the INST target
```

Claude should retrieve and display the raw cmd.txt file content.

### Test 4: Analyze Configuration

Ask:

```
Analyze the INST target configuration and explain what commands and telemetry it provides
```

Claude should:
1. Read the cmd.txt and tlm.txt files
2. Parse the COSMOS configuration format
3. Provide a summary of commands and telemetry

### Test 5: Compare Targets

Ask:

```
Compare the command structures of INST and INST2. What are the differences?
```

Claude should retrieve both cmd.txt files and provide a comparison.

## Troubleshooting

### Plugin Won't Install

**Check logs:**
```bash
docker logs cosmos-openc3-operator-1 | tail -50
```

**Common issues:**
- Python not available: Should be included in COSMOS container
- Port conflict: Change mcp_server_port to different value (e.g., 8766)
- Permission issues: Check Docker has proper permissions

### Microservice Won't Start

**Check microservice logs:**
```bash
docker exec cosmos-openc3-operator-1 cat /plugins/DEFAULT/microservices/mcp_server/mcp_server.log
```

**Test Ruby client directly:**
```bash
docker exec cosmos-openc3-operator-1 ruby /plugins/DEFAULT/microservices/mcp_server/cosmos_client.rb get_target_names DEFAULT
```

Expected output: JSON array of target names

### Claude Code Can't Connect

**Verify health endpoint from your host:**
```bash
curl http://localhost:8765/health
```

**Check Docker port mapping:**
```bash
docker ps | grep cosmos-openc3-operator
```

Port 8765 should be mapped to host.

**Check firewall:**
- Ensure localhost traffic is allowed
- Try disabling firewall temporarily to test

**Verify config file:**
- Check JSON syntax is valid
- Ensure URL uses http:// not https://
- Ensure port matches what you configured

### No Data Returned

**Verify targets exist:**
```bash
docker exec cosmos-openc3-operator-1 ruby -e "require 'openc3'; puts OpenC3::TargetModel.names(scope: 'DEFAULT').inspect"
```

**Check bucket access:**
```bash
docker exec cosmos-openc3-operator-1 ruby -e "require 'openc3'; require 'openc3/utilities/bucket'; puts OpenC3::Bucket.getClient.list_objects(bucket: ENV['OPENC3_CONFIG_BUCKET'], prefix: 'DEFAULT/targets/').count"
```

## Advanced Testing

### Test All Resources

Create a test script to verify all resource types:

```bash
#!/bin/bash

# Test target list
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "cosmos://targets/list"}}'

# Test target info
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "cosmos://targets/INST/info"}}'

# Test cmd file
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "cosmos://targets/INST/cmd_file"}}'

# Test tlm file
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "cosmos://targets/INST/tlm_file"}}'

# Test all files
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "cosmos://targets/INST/all_files"}}'
```

### Performance Testing

Test response times:

```bash
time curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "cosmos://targets/list"}}'
```

Typical response times:
- Target list: < 100ms
- Target info: < 200ms
- Single file: < 500ms
- All files: < 2s

## Uninstalling

### Via Admin UI

1. Go to Admin → Plugins
2. Click trash icon next to openc3-cosmos-mcp-server
3. Confirm deletion

### Via CLI

```bash
cd /path/to/cosmos-project/
./openc3.sh cli unload openc3-cosmos-mcp-server DEFAULT
```

## Getting Help

If you encounter issues:

1. Check this troubleshooting guide first
2. Review logs from Docker containers
3. Test each component independently (health → Ruby client → MCP → Claude)
4. Create GitHub issue with:
   - COSMOS version
   - Error messages from logs
   - Steps to reproduce
   - Results of diagnostic commands

## Next Steps

Once everything is working:

1. Explore different types of questions to ask Claude
2. Try analyzing complex target configurations
3. Use Claude to generate documentation from configs
4. Ask Claude to identify potential issues in configurations
5. Experiment with comparing multiple targets

Enjoy using AI-assisted COSMOS configuration management!
