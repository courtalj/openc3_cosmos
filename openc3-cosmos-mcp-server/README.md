# OpenC3 COSMOS MCP Server Plugin

Model Context Protocol (MCP) server for OpenC3 COSMOS. Enables AI assistants like Claude to read and understand COSMOS target configurations, command definitions, and telemetry definitions.

## Features

- **Read-only access** to COSMOS target information
- **MCP protocol** implementation over HTTP
- **Raw configuration files** accessible to AI assistants
- **Automatic discovery** of all targets and their resources
- **Plugin architecture** - installs and manages as COSMOS plugin

## What is MCP?

The Model Context Protocol (MCP) is a standard for connecting AI assistants to data sources. This plugin exposes COSMOS configuration data through MCP resources that AI assistants can read and understand.

## Installation

### Prerequisites

- OpenC3 COSMOS 5.x or later running
- Python 3.8+ available in COSMOS container (included by default)

### Install via Admin UI

1. Build the plugin gem:
   ```bash
   cd openc3-cosmos-mcp-server
   rake build VERSION=0.1.0
   ```

2. Open COSMOS Admin interface (http://localhost:2900/tools/admin)

3. Click "Plugins" tab

4. Click "Upload Plugin" and select `openc3-cosmos-mcp-server-0.1.0.gem`

5. Configure variables:
   - **mcp_server_port**: Port for MCP server (default: 8765)
   - **mcp_microservice_name**: Microservice name (default: OPENC3_MCP_SERVER)

6. Click "Install"

7. Verify in CmdTlmServer that the MCP microservice is running

### Verify Installation

Check that the server is running:

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

## MCP Resources

The plugin exposes the following MCP resources:

### Target List
- **URI**: `cosmos://targets/list`
- **Type**: JSON array
- **Description**: List of all configured target names

### Target Information
- **URI**: `cosmos://targets/{target_name}/info`
- **Type**: JSON object
- **Description**: Target metadata including language, files, interfaces, logging config

### Command Definitions
- **URI**: `cosmos://targets/{target_name}/cmd_file`
- **Type**: Plain text
- **Description**: Raw cmd.txt file content with all command definitions

### Telemetry Definitions
- **URI**: `cosmos://targets/{target_name}/tlm_file`
- **Type**: Plain text
- **Description**: Raw tlm.txt file content with all telemetry definitions

### All Configuration Files
- **URI**: `cosmos://targets/{target_name}/all_files`
- **Type**: JSON object
- **Description**: Dictionary of all target configuration files

### Specific File
- **URI**: `cosmos://targets/{target_name}/files/{path}`
- **Type**: Plain text
- **Description**: Any specific file in the target directory

## Usage with Claude Code

### Configuration

Add to your Claude Desktop config (or MCP client config):

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

### Example Interactions

Once configured, you can ask Claude:

- "What targets are configured in COSMOS?"
- "Show me the command definitions for INST"
- "What telemetry packets does INST2 send?"
- "Compare the command structures of INST and EXAMPLE"
- "Explain the INST target configuration"

Claude will automatically query the MCP server to retrieve the information.

## Testing

### Manual Testing

Test the MCP protocol directly:

```bash
# Initialize
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

# List resources
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "resources/list",
    "params": {}
  }'

# Read target list
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/list"}
  }'

# Read INST commands
curl -X POST http://localhost:8765/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "resources/read",
    "params": {"uri": "cosmos://targets/INST/cmd_file"}
  }'
```

### Troubleshooting

**Microservice won't start:**
- Check logs: `docker logs cosmos-openc3-operator-1 | grep mcp_server`
- Verify Python is available: `docker exec cosmos-openc3-operator-1 python3 --version`
- Check Ruby client: `docker exec cosmos-openc3-operator-1 ruby /plugins/DEFAULT/microservices/mcp_server/cosmos_client.rb get_target_names DEFAULT`

**Port already in use:**
- Change `mcp_server_port` when installing plugin
- Or find and stop conflicting service

**Cannot connect from Claude Code:**
- Verify health endpoint works: `curl http://localhost:8765/health`
- Check Docker port forwarding: `docker ps | grep 8765`
- Ensure Claude Desktop config uses correct URL

**Ruby client errors:**
- Check COSMOS is fully initialized
- Verify target exists: `docker exec cosmos-openc3-operator-1 ls /plugins/DEFAULT/targets/`
- Check bucket access: verify MinIO is running

## Architecture

```
Claude Code (AI Assistant)
    ↓ HTTP + MCP Protocol
Python FastAPI Server (mcp_server.py)
    ↓ Subprocess call
Ruby Client (cosmos_client.rb)
    ↓ Internal APIs
COSMOS (TargetModel, Bucket, Redis)
```

The plugin consists of:
1. **Python MCP Server**: FastAPI HTTP server implementing MCP protocol
2. **Ruby Client**: Bridge to COSMOS internal APIs
3. **COSMOS Microservice**: Managed by COSMOS operator

## Configuration

Plugin configuration is set via `plugin.txt`:

```
VARIABLE mcp_server_port 8765
VARIABLE mcp_microservice_name OPENC3_MCP_SERVER

MICROSERVICE MCP <%= mcp_microservice_name %>
  CMD python3 mcp_server.py
  WORK_DIR /plugins/DEFAULT/microservices/mcp_server
  ENV MCP_PORT <%= mcp_server_port %>
  ENV COSMOS_SCOPE DEFAULT
  ENV PYTHONUNBUFFERED 1
```

## Limitations

- **Read-only**: Cannot modify targets or definitions (by design)
- **Single scope**: Currently supports DEFAULT scope only
- **No authentication**: Assumes trusted network (same as COSMOS core)
- **No real-time telemetry**: Only configuration data, not live data
- **HTTP only**: No HTTPS (run behind reverse proxy if needed)

## Future Enhancements

Potential future features (not currently implemented):

- Write operations (add/modify targets)
- Multi-scope support
- Real-time telemetry streaming
- Command history queries
- Screen definitions in structured format
- Authentication/authorization
- WebSocket transport option

## Development

### Project Structure

```
openc3-cosmos-mcp-server/
├── plugin.txt                          # Plugin configuration
├── openc3-cosmos-mcp-server.gemspec   # Gem specification
├── Rakefile                            # Build tasks
├── README.md                           # This file
├── LICENSE.txt                         # License
├── microservices/
│   └── mcp_server/
│       ├── mcp_server.py              # FastAPI MCP server
│       ├── cosmos_client.rb           # Ruby COSMOS client
│       └── requirements.txt           # Python dependencies
└── targets/                            # Empty (no targets)
```

### Building

```bash
rake build VERSION=x.y.z
```

### Testing Locally

Run the Python server directly:

```bash
cd microservices/mcp_server
pip install -r requirements.txt
export MCP_PORT=8765
export COSMOS_SCOPE=DEFAULT
python3 mcp_server.py
```

Test Ruby client:

```bash
ruby cosmos_client.rb get_target_names DEFAULT
ruby cosmos_client.rb get_target_info DEFAULT INST
ruby cosmos_client.rb get_target_file DEFAULT INST cmd_tlm/cmd.txt
```

## License

Copyright 2024 OpenC3, Inc.

This plugin is licensed under the AGPLv3. See LICENSE.txt for details.

## Support

- GitHub Issues: https://github.com/OpenC3/cosmos/issues
- Documentation: https://docs.openc3.com
- Community: https://github.com/OpenC3/cosmos/discussions

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Version History

### 0.1.0 (Initial Release)
- Read-only MCP server
- Target list and info
- Command/telemetry file access
- All configuration files access
- HTTP transport
- COSMOS plugin packaging
