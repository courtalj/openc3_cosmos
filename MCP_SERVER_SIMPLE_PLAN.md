# OpenC3 COSMOS MCP Server - Simplified Implementation Plan

## Overview

A minimal, read-only MCP (Model Context Protocol) server for retrieving OpenC3 COSMOS target information, including command/telemetry definitions and configuration files. Implemented as a COSMOS plugin with an HTTP-based MCP server.

## Goals

1. **Read-only access** to target information
2. **Retrieve raw configuration files** (cmd.txt, tlm.txt, etc.)
3. **List and inspect** targets and their components
4. **Start small and iterate** - get it working first, enhance later
5. **Package as COSMOS plugin** for easy installation

## Architecture Decision: HTTP vs stdio

**Choice: HTTP Transport**

**Reasoning:**
- **Large data transfer**: Target config files can be 10KB-100KB+, HTTP handles this better
- **Async operations**: Can fetch multiple resources in parallel
- **Standard tooling**: Easy to debug with curl/Postman
- **Better for Claude Code**: HTTP servers integrate cleanly with MCP
- **Future-proof**: Easy to add authentication, rate limiting, etc.

**Trade-off:**
- stdio is simpler for desktop apps
- HTTP requires port management
- But HTTP is worth it for data size and flexibility

## High-Level Architecture

```
┌─────────────────────────────────────────────┐
│         Claude Code / AI Assistant          │
└────────────────┬────────────────────────────┘
                 │ MCP over HTTP
                 │ (JSON-RPC 2.0)
┌────────────────▼────────────────────────────┐
│    MCP Server (Python Flask/FastAPI)        │
│    Port: 8765 (configurable)                │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  MCP Resources (Read-Only)             │ │
│  │  - cosmos://targets/list               │ │
│  │  - cosmos://targets/{name}/info        │ │
│  │  - cosmos://targets/{name}/cmd_file    │ │
│  │  - cosmos://targets/{name}/tlm_file    │ │
│  │  - cosmos://targets/{name}/all_files   │ │
│  └────────────────────────────────────────┘ │
└────────────────┬────────────────────────────┘
                 │ COSMOS Internal APIs
┌────────────────▼────────────────────────────┐
│        COSMOS Core Components               │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ TargetModel  │  │    Redis     │        │
│  │   (Ruby)     │  │  (Config)    │        │
│  └──────────────┘  └──────────────┘        │
│  ┌──────────────┐  ┌──────────────┐        │
│  │    Bucket    │  │   System     │        │
│  │  (MinIO/S3)  │  │   Config     │        │
│  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────┘
```

## Plugin Structure

```
openc3-cosmos-mcp-server/
├── plugin.txt                          # Plugin configuration
├── openc3-cosmos-mcp-server.gemspec   # Gem specification
├── Rakefile                            # Build tasks
├── README.md                           # Documentation
├── microservices/
│   └── mcp_server/
│       ├── mcp_server.py              # Main MCP HTTP server
│       ├── cosmos_client.rb           # Ruby client for COSMOS APIs
│       ├── requirements.txt           # Python dependencies
│       └── Gemfile                    # Ruby dependencies (if needed)
└── targets/                            # Empty (no targets in this plugin)
```

## Implementation Details

### 1. Plugin Configuration (plugin.txt)

**Purpose**: Define the MCP server as a COSMOS microservice

**Key elements**:
- VARIABLE for port configuration
- MICROSERVICE declaration
- CMD to run Python server
- WORK_DIR to set proper working directory
- ENV variables for COSMOS connection

### 2. MCP Server (mcp_server.py)

**Purpose**: HTTP server implementing MCP protocol

**Framework**: FastAPI (lightweight, async, good for JSON APIs)

**Key responsibilities**:
- Handle MCP protocol methods (initialize, resources/list, resources/read)
- Connect to COSMOS internal APIs
- Retrieve target information from Redis
- Fetch config files from bucket storage
- Format responses according to MCP spec

**Why this file**: Core functionality of the MCP server

### 3. COSMOS Client (cosmos_client.rb)

**Purpose**: Interface with COSMOS internal Ruby APIs

**Key responsibilities**:
- Use TargetModel to list and retrieve target data
- Access bucket storage for config files
- Query Redis for packet definitions
- Return data as JSON for Python to consume

**Why this file**: Python can't directly call Ruby COSMOS APIs, need a bridge

**Alternative approach**: Could use COSMOS REST API instead, but internal APIs are more direct and efficient for a plugin

### 4. Gemspec and Dependencies

**Purpose**: Package plugin for COSMOS installation

**Why this file**: Required for all COSMOS plugins to be installed via Admin interface

## MCP Resources Exposed

### Resource 1: Target List
```
URI: cosmos://targets/list
Returns: JSON array of target names
Example: ["INST", "INST2", "EXAMPLE"]
```

### Resource 2: Target Info
```
URI: cosmos://targets/{target_name}/info
Returns: JSON with target metadata
Example:
{
  "name": "INST",
  "folder_name": "INST",
  "requires": [],
  "ignored_parameters": [],
  "ignored_items": [],
  "cmd_tlm_files": ["cmd.txt", "tlm.txt"],
  "language": "ruby",
  "limits_groups": [],
  "interfaces": ["INST_INT"]
}
```

### Resource 3: Command File
```
URI: cosmos://targets/{target_name}/cmd_file
Returns: Raw text content of cmd.txt (or specified file)
Example:
COMMAND INST ABORT BIG_ENDIAN "Abort collect"
  APPEND_ID_PARAMETER PKT_ID 16 UINT 1 1 1 "Packet ID"
  APPEND_PARAMETER DESC_ID 16 UINT MIN MAX 1 "Descriptor ID"
...
```

### Resource 4: Telemetry File
```
URI: cosmos://targets/{target_name}/tlm_file
Returns: Raw text content of tlm.txt (or specified file)
```

### Resource 5: All Files
```
URI: cosmos://targets/{target_name}/all_files
Returns: JSON with all config files
Example:
{
  "cmd.txt": "COMMAND INST ABORT...",
  "tlm.txt": "TELEMETRY INST HEALTH_STATUS...",
  "target.txt": "LANGUAGE ruby\nREQUIRE..."
}
```

### Resource 6: Specific Config File
```
URI: cosmos://targets/{target_name}/files/{filename}
Returns: Raw text of specified file
Example: cosmos://targets/INST/files/screens/status.txt
```

## Files to Create/Modify

### New Files to Create

#### 1. `plugin.txt`
**Why**: Defines the plugin structure and microservice configuration
**What it does**:
- Declares MICROSERVICE with Python command
- Sets environment variables for COSMOS connection
- Configures port for MCP server
- Sets working directory for microservice

#### 2. `openc3-cosmos-mcp-server.gemspec`
**Why**: Required for COSMOS plugin installation
**What it does**:
- Defines plugin name, version, authors
- Lists files to include in gem
- Declares dependencies (if any)

#### 3. `Rakefile`
**Why**: Build automation for creating plugin gem
**What it does**:
- Provides `rake build VERSION=x.y.z` task
- Packages plugin into .gem file

#### 4. `microservices/mcp_server/mcp_server.py`
**Why**: Core MCP server implementation
**What it does**:
- Implements FastAPI HTTP server
- Handles MCP JSON-RPC 2.0 protocol
- Routes to appropriate resource handlers
- Calls COSMOS client to fetch data
- Returns MCP-formatted responses

**Key endpoints**:
- POST / (all MCP methods via JSON-RPC)
- GET /health (health check)

#### 5. `microservices/mcp_server/cosmos_client.rb`
**Why**: Bridge between Python and COSMOS Ruby APIs
**What it does**:
- Loads COSMOS internal libraries
- Provides methods to query targets, config files
- Returns JSON that Python can parse
- Called via subprocess from Python

**Key methods**:
- get_target_names()
- get_target_info(target_name)
- get_target_file(target_name, filename)
- get_all_target_files(target_name)

#### 6. `microservices/mcp_server/requirements.txt`
**Why**: Python dependencies for MCP server
**What it does**:
- Lists FastAPI, uvicorn for HTTP server
- Includes httpx for async HTTP
- Any other needed packages

#### 7. `README.md`
**Why**: Documentation for users and developers
**What it does**:
- Explains what the plugin does
- Installation instructions
- Configuration options
- Usage examples with Claude Code
- Troubleshooting tips

### Files NOT Modified

**COSMOS Core**: No changes to existing COSMOS code
**Other Plugins**: No dependencies on other plugins
**Database Schema**: No new tables or migrations

## Data Flow Example

**User asks Claude**: "What telemetry packets does INST have?"

**Flow**:
1. Claude Code calls MCP resource: `cosmos://targets/INST/tlm_file`
2. MCP server receives JSON-RPC request over HTTP
3. Python server calls `cosmos_client.rb get_target_file INST tlm.txt`
4. Ruby client queries COSMOS bucket storage: `bucket.get_object("DEFAULT/targets/INST/cmd_tlm/tlm.txt")`
5. Ruby returns raw text file content as JSON
6. Python parses JSON and formats as MCP resource response
7. Claude Code receives raw telemetry file content
8. Claude parses the COSMOS config format and answers user

**Data path**: Bucket → Ruby → JSON → Python → HTTP → MCP → Claude

## Testing Plan

### Prerequisites

1. **Local COSMOS Running**
   ```bash
   cd cosmos-project
   ./openc3.sh run
   # Wait for COSMOS to be available at http://localhost:2900
   # Install demo plugin via Admin interface
   ```

2. **Claude Code with MCP Support**
   - Claude for Desktop (or compatible MCP client)
   - Ability to add custom MCP servers

### Phase 1: Manual HTTP Testing

**Test 1: Health Check**
```bash
curl http://localhost:8765/health
# Expected: {"status": "ok", "cosmos_connected": true}
```

**Test 2: MCP Initialize**
```bash
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "0.1.0",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
# Expected: Server capabilities response
```

**Test 3: List Resources**
```bash
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "resources/list",
    "params": {}
  }'
# Expected: Array of resource URIs
```

**Test 4: Read Target List**
```bash
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/list"}
  }'
# Expected: ["INST", "INST2", "EXAMPLE", "TEMPLATED", "SYSTEM"]
```

**Test 5: Read Target Config**
```bash
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/INST/cmd_file"}
  }'
# Expected: Raw cmd.txt content
```

### Phase 2: Claude Code Integration Testing

**Test 1: Configure MCP Server in Claude Code**

Edit Claude Desktop config (or equivalent):
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

**Test 2: Basic Discovery**
- Start conversation in Claude Code
- Ask: "What MCP servers are available?"
- Verify: "cosmos" server appears
- Ask: "What resources does the cosmos server provide?"
- Verify: List of cosmos:// URIs shown

**Test 3: Target Listing**
- Ask: "What targets are configured in COSMOS?"
- Claude should query `cosmos://targets/list`
- Verify: Response includes INST, INST2, EXAMPLE, etc.

**Test 4: Command Definition Inspection**
- Ask: "Show me the command definitions for the INST target"
- Claude should query `cosmos://targets/INST/cmd_file`
- Verify: Raw cmd.txt content displayed
- Claude should be able to parse and explain commands

**Test 5: Telemetry Definition Inspection**
- Ask: "What telemetry packets does INST2 send?"
- Claude should query `cosmos://targets/INST2/tlm_file`
- Verify: Raw tlm.txt content retrieved
- Claude should list packet names

**Test 6: Target Information**
- Ask: "Tell me about the EXAMPLE target configuration"
- Claude should query `cosmos://targets/EXAMPLE/info`
- Verify: JSON metadata shown
- Claude should explain interfaces, language, files

**Test 7: Multiple Targets**
- Ask: "Compare the command structures of INST and INST2"
- Claude should query both cmd files
- Verify: Both files retrieved
- Claude should provide comparison

**Test 8: Screen/Config Files**
- Ask: "Show me the screens defined for INST"
- Claude should query `cosmos://targets/INST/files/screens/hs.txt` (or similar)
- Verify: Screen config file content

**Test 9: Error Handling**
- Ask: "Show me the config for target NONEXISTENT"
- Verify: Graceful error message
- Claude explains target doesn't exist

**Test 10: Large File Handling**
- Ask: "Show me all configuration files for INST"
- Claude queries `cosmos://targets/INST/all_files`
- Verify: Multiple files returned in single response
- No truncation or errors

### Phase 3: Integration Testing in COSMOS

**Test 1: Plugin Installation**
```bash
# Build plugin
cd openc3-cosmos-mcp-server
openc3.sh cli rake build VERSION=0.1.0

# Install via Admin UI
# Upload openc3-cosmos-mcp-server-0.1.0.gem
# Verify microservice starts in CmdTlmServer
```

**Test 2: Microservice Health**
```bash
# Check microservice is running
docker exec -it cosmos-openc3-operator-1 ps aux | grep mcp_server

# Check logs
docker logs cosmos-openc3-operator-1 | grep mcp_server
```

**Test 3: Port Accessibility**
```bash
# From host machine
curl http://localhost:8765/health

# From within COSMOS network
docker exec -it cosmos-openc3-operator-1 curl http://localhost:8765/health
```

**Test 4: COSMOS API Access**
```bash
# Test Ruby client can access COSMOS
docker exec -it cosmos-openc3-operator-1 \
  ruby /plugins/DEFAULT/microservices/mcp_server/cosmos_client.rb get_target_names

# Should output: ["INST", "INST2", ...]
```

### Phase 4: Performance Testing

**Test 1: Response Time**
```bash
# Measure latency for different resource types
time curl -X POST http://localhost:8765/ -d '{"method":"resources/read",...}'

# Targets:
# - Target list: < 100ms
# - Target info: < 200ms
# - Small file (cmd.txt): < 500ms
# - Large file (all files): < 2s
```

**Test 2: Concurrent Requests**
```bash
# Use Apache Bench or similar
ab -n 100 -c 10 -p request.json http://localhost:8765/

# Verify: No errors, consistent response times
```

**Test 3: Memory Usage**
```bash
# Monitor microservice memory
docker stats cosmos-openc3-operator-1

# Should stay under 100MB for normal usage
```

### Test Success Criteria

✅ **Must Have**:
1. Plugin installs without errors
2. Microservice starts and stays running
3. HTTP server responds to health checks
4. All MCP protocol methods implemented correctly
5. Can list all targets
6. Can retrieve target info and files
7. Claude Code can discover and use resources
8. Raw config files retrieved correctly
9. Handles missing targets gracefully
10. No COSMOS core errors in logs

✅ **Nice to Have**:
1. Response times under targets
2. Handles 10+ concurrent requests
3. Memory usage stable over time
4. Detailed error messages
5. Logs useful for debugging

## Alternative Implementation: Using COSMOS REST API

**Current plan**: Direct access to COSMOS internal APIs (TargetModel, Bucket)

**Alternative**: Use COSMOS REST API (`http://localhost:2901/openc3-api/...`)

**Pros**:
- No Ruby bridge needed (pure Python)
- More stable API contract
- Better isolation from COSMOS internals

**Cons**:
- Need authentication token
- Some APIs may not exist for raw file access
- Extra HTTP hop (Python → REST API → COSMOS)
- May not have direct bucket access

**Recommendation**: Start with internal APIs (current plan), consider REST API if authentication/isolation becomes important

## Plugin as Microservice: Advantages

**Why COSMOS plugin vs standalone service?**

1. **Lifecycle Management**: COSMOS manages start/stop/restart
2. **Discovery**: Listed in CmdTlmServer, visible to users
3. **Packaging**: Single .gem file for easy distribution
4. **Versioning**: Follows COSMOS plugin versioning
5. **Environment**: Runs in COSMOS container with all dependencies
6. **Network**: Automatic Docker network access
7. **Configuration**: Uses COSMOS ENV variables
8. **Logs**: Integrated with COSMOS logging

**Trade-offs**:
- More complex setup than standalone server
- Requires understanding COSMOS plugin structure
- Debugging is harder (need Docker access)

**For initial development**: Could start as standalone, then package as plugin

## Development Workflow

### Initial Development (Standalone)
1. Write Python MCP server
2. Write Ruby client for COSMOS APIs
3. Test with local COSMOS via port forwarding
4. Test with Claude Code
5. Fix bugs and iterate

### Packaging as Plugin
1. Create plugin structure
2. Add plugin.txt and gemspec
3. Test microservice startup
4. Test from within COSMOS network
5. Build gem and install via Admin UI

### Iteration
1. Make changes to Python/Ruby code
2. Rebuild plugin gem
3. Upgrade plugin in COSMOS
4. Test changes
5. Repeat

## Next Steps

1. **Create basic plugin structure** (directories, plugin.txt)
2. **Implement minimal MCP server** (just initialize + resources/list)
3. **Create Ruby client** (just get_target_names)
4. **Test locally** with curl
5. **Add target info resource**
6. **Add file reading resources**
7. **Test with Claude Code**
8. **Package and test as plugin**
9. **Document and iterate**

## Estimated Effort

- **Plugin structure**: 1-2 hours
- **Basic MCP server**: 4-6 hours
- **Ruby client**: 2-4 hours
- **Testing and debugging**: 4-8 hours
- **Documentation**: 2-3 hours
- **Total**: 2-3 days for working prototype

## Success Metrics

- ✅ Plugin installs in COSMOS
- ✅ Microservice runs without crashing
- ✅ Claude Code can discover server
- ✅ Can list all targets
- ✅ Can read raw config files
- ✅ Response time < 1s for typical queries
- ✅ No errors in COSMOS logs
- ✅ Can answer "What commands does INST have?"

## Future Enhancements (Out of Scope)

- Write operations (add/modify targets)
- Real-time telemetry streaming
- Command history queries
- Log file access
- Screen definitions in structured format
- Protocol analyzer
- Limit definitions
- State information

**Keep it simple, get it working, iterate based on usage!**
