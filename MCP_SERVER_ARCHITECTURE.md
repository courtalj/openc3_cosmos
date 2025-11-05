# OpenC3 COSMOS MCP Server Architecture Plan

## Executive Summary

This document outlines an architecture for a Model Context Protocol (MCP) server that enables AI assistants to interact with OpenC3 COSMOS systems. The MCP server would expose COSMOS's plugin management, target configuration, and command/telemetry definition capabilities through a standardized interface.

## 1. Background: What is MCP?

The Model Context Protocol is a standard for connecting AI assistants to data sources and tools. An MCP server:
- Exposes **Resources** (data that can be read)
- Exposes **Tools** (actions that can be executed)
- Provides **Prompts** (reusable prompt templates)
- Uses JSON-RPC 2.0 over stdio or HTTP

## 2. COSMOS Architecture Overview (From Code Analysis)

### Current COSMOS API Structure

**Storage Layer:**
- **Redis**: Primary storage for all configuration, packet definitions, and current values
- **MinIO/S3**: Object storage for plugin gems, log files, and archived configurations
- **Redis Keys Structure**:
  - `{SCOPE}__openc3_plugins` - Plugin metadata
  - `{SCOPE}__openc3_targets` - Target metadata
  - `{SCOPE}__openc3cmd__{TARGET}` - Command packet definitions
  - `{SCOPE}__openc3tlm__{TARGET}` - Telemetry packet definitions

**API Layer:**
- Ruby on Rails REST API (`openc3-cosmos-cmd-tlm-api`)
- Authentication via `AuthModel` (token-based, sessions stored in Redis)
- Authorization via `Authorization` module (Core = simple token, Enterprise = Keycloak/RBAC)
- WebSocket streaming API via ActionCable

**Key APIs Discovered:**
1. **Plugin Management** (`/openc3/lib/openc3/models/plugin_model.rb`)
   - Two-phase installation (validate → install)
   - Background process execution via `openc3cli`
   - Microservice deployment/undeployment

2. **Target Management** (`/openc3/lib/openc3/models/target_model.rb`)
   - Full CRUD operations
   - Runtime modification via `dynamic_update()` method
   - Modified files tracked separately in S3

3. **Cmd/Tlm Definitions** (Redis storage as JSON)
   - Packet definitions stored as JSON in Redis
   - Can be modified at runtime
   - Microservices notified via pub/sub topics

### Authentication Flow

**COSMOS Core:**
```
User → Token (password) → AuthModel.verify() → Redis lookup → Allow/Deny
```

**COSMOS Enterprise:**
```
User → JWT Token → Keycloak validation → RBAC check → Allow/Deny
```

## 3. MCP Server Architecture

### 3.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Assistant (Claude)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ MCP Protocol (JSON-RPC)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  COSMOS MCP Server                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  MCP Protocol Handler (stdio/HTTP)                     │ │
│  └────────────────────┬───────────────────────────────────┘ │
│  ┌────────────────────▼───────────────────────────────────┐ │
│  │  Authentication Layer                                   │ │
│  │  - Token validation                                     │ │
│  │  - Session management                                   │ │
│  │  - Scope validation                                     │ │
│  └────────────────────┬───────────────────────────────────┘ │
│  ┌────────────────────▼───────────────────────────────────┐ │
│  │  Resource/Tool Handlers                                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │   Plugin     │  │   Target     │  │   Cmd/Tlm    │ │ │
│  │  │   Manager    │  │   Manager    │  │   Manager    │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  └────────────────────┬───────────────────────────────────┘ │
└───────────────────────┼─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                  COSMOS Internal APIs                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ PluginModel  │  │ TargetModel  │  │   Redis      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   GemModel   │  │  Interface   │  │   MinIO      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Implementation Approach

**Option 1: Standalone MCP Server (Recommended)**
- Separate Node.js/Python service
- Uses COSMOS REST APIs via HTTP
- Deployed as a Docker container alongside COSMOS
- Advantages:
  - Language flexibility (can use MCP SDK)
  - Doesn't modify COSMOS core
  - Easy to upgrade/maintain
  - Can be optional component

**Option 2: Embedded in COSMOS**
- Add MCP endpoints to `openc3-cosmos-cmd-tlm-api`
- Ruby implementation
- Advantages:
  - Direct access to internal APIs
  - No additional container
  - Shared authentication
- Disadvantages:
  - Requires COSMOS core modifications
  - Ruby MCP SDK less mature

**Recommendation: Option 1 (Standalone) for initial implementation**

### 3.3 Technology Stack

**Recommended Stack:**
```yaml
Language: Python 3.11+
MCP SDK: @modelcontextprotocol/sdk (Python)
HTTP Client: requests or httpx
Auth: Custom token manager
Container: Docker (Alpine-based)
Configuration: Environment variables
```

### 3.4 Directory Structure

```
openc3-cosmos-mcp-server/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── server.py                 # Main MCP server
│   ├── cosmos_client.py          # COSMOS REST API client
│   ├── auth.py                   # Authentication manager
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── plugins.py            # Plugin resources
│   │   ├── targets.py            # Target resources
│   │   └── packets.py            # Cmd/Tlm resources
│   └── tools/
│       ├── __init__.py
│       ├── plugin_tools.py       # Plugin management tools
│       ├── target_tools.py       # Target management tools
│       └── packet_tools.py       # Cmd/Tlm tools
├── config/
│   └── config.yaml
└── tests/
    ├── test_resources.py
    └── test_tools.py
```

## 4. MCP Resources (Read Operations)

### 4.1 Plugin Resources

```json
{
  "uri": "cosmos://plugins/list",
  "name": "List all installed plugins",
  "description": "Returns metadata for all installed plugins in the scope",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://plugins/{plugin_name}",
  "name": "Get plugin details",
  "description": "Returns full configuration for a specific plugin",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://plugin-store",
  "name": "Browse plugin store",
  "description": "Returns available plugins from the OpenC3 plugin store",
  "mimeType": "application/json"
}
```

**Implementation:**
```python
# GET /openc3-api/plugins
# GET /openc3-api/plugins/{plugin_name}
# GET /openc3-api/plugin_store
```

### 4.2 Target Resources

```json
{
  "uri": "cosmos://targets/list",
  "name": "List all targets",
  "description": "Returns names of all configured targets",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://targets/{target_name}",
  "name": "Get target configuration",
  "description": "Returns full target configuration including interfaces",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://targets/{target_name}/modified",
  "name": "Get target modified files",
  "description": "Returns list of modified configuration files for target",
  "mimeType": "application/json"
}
```

**Implementation:**
```python
# GET /openc3-api/targets
# GET /openc3-api/targets/{target_name}
# GET /openc3-api/targets/{target_name}/modified_files
```

### 4.3 Command/Telemetry Resources

```json
{
  "uri": "cosmos://commands/{target_name}",
  "name": "List target commands",
  "description": "Returns all command definitions for a target",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://commands/{target_name}/{command_name}",
  "name": "Get command definition",
  "description": "Returns detailed command packet definition",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://telemetry/{target_name}",
  "name": "List target telemetry",
  "description": "Returns all telemetry packet definitions for a target",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://telemetry/{target_name}/{packet_name}",
  "name": "Get telemetry packet definition",
  "description": "Returns detailed telemetry packet definition with items",
  "mimeType": "application/json"
}
```

**Implementation:**
```python
# Using COSMOS Scripting API internally:
# get_all_cmds(target_name)
# get_cmd(target_name, command_name)
# get_all_tlm(target_name)
# get_tlm(target_name, packet_name)
```

### 4.4 Interface Resources

```json
{
  "uri": "cosmos://interfaces/list",
  "name": "List all interfaces",
  "description": "Returns all interface configurations",
  "mimeType": "application/json"
}

{
  "uri": "cosmos://interfaces/{interface_name}",
  "name": "Get interface details",
  "description": "Returns interface configuration and status",
  "mimeType": "application/json"
}
```

## 5. MCP Tools (Write Operations)

### 5.1 Plugin Management Tools

#### Tool: `install_plugin`
```json
{
  "name": "install_plugin",
  "description": "Install a new COSMOS plugin from a gem file or plugin store",
  "inputSchema": {
    "type": "object",
    "properties": {
      "source": {
        "type": "string",
        "description": "Plugin source: 'store' or 'file'",
        "enum": ["store", "file"]
      },
      "plugin_name": {
        "type": "string",
        "description": "Plugin name (if from store)"
      },
      "gem_path": {
        "type": "string",
        "description": "Path to gem file (if from file)"
      },
      "variables": {
        "type": "object",
        "description": "Plugin configuration variables"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope (default: DEFAULT)"
      }
    },
    "required": ["source", "scope"]
  }
}
```

**Implementation:**
```python
def install_plugin(source, plugin_name=None, gem_path=None, variables=None, scope="DEFAULT"):
    if source == "store":
        # POST /openc3-api/plugins with plugin_name from store
        pass
    elif source == "file":
        # POST /openc3-api/plugins with multipart/form-data
        pass
    # Then POST /openc3-api/plugins/install/{id} with variables
```

#### Tool: `upgrade_plugin`
```json
{
  "name": "upgrade_plugin",
  "description": "Upgrade an existing plugin to a new version",
  "inputSchema": {
    "type": "object",
    "properties": {
      "plugin_name": {
        "type": "string",
        "description": "Current plugin name"
      },
      "version": {
        "type": "string",
        "description": "New version to install"
      },
      "variables": {
        "type": "object",
        "description": "Updated configuration variables"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["plugin_name", "scope"]
  }
}
```

**Implementation:**
```python
# PATCH /openc3-api/plugins/{plugin_name}
```

#### Tool: `uninstall_plugin`
```json
{
  "name": "uninstall_plugin",
  "description": "Uninstall a COSMOS plugin and cleanup resources",
  "inputSchema": {
    "type": "object",
    "properties": {
      "plugin_name": {
        "type": "string",
        "description": "Plugin name to uninstall"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["plugin_name", "scope"]
  }
}
```

**Implementation:**
```python
# DELETE /openc3-api/plugins/{plugin_name}
```

### 5.2 Target Management Tools

#### Tool: `create_target`
```json
{
  "name": "create_target",
  "description": "Create a new target with command/telemetry definitions",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {
        "type": "string",
        "description": "Name of the new target"
      },
      "config": {
        "type": "object",
        "description": "Target configuration",
        "properties": {
          "requires": {
            "type": "array",
            "items": {"type": "string"}
          },
          "language": {
            "type": "string",
            "enum": ["ruby", "python"]
          },
          "cmd_tlm_files": {
            "type": "array",
            "items": {"type": "string"}
          }
        }
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["target_name", "scope"]
  }
}
```

**Implementation:**
```python
# POST /openc3-api/targets
# Internally uses TargetModel.create()
```

#### Tool: `modify_target`
```json
{
  "name": "modify_target",
  "description": "Modify an existing target configuration",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {
        "type": "string",
        "description": "Target name to modify"
      },
      "updates": {
        "type": "object",
        "description": "Configuration updates"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["target_name", "updates", "scope"]
  }
}
```

**Implementation:**
```python
# PATCH /openc3-api/targets/{target_name}
```

#### Tool: `delete_target`
```json
{
  "name": "delete_target",
  "description": "Delete a target and all its definitions",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {
        "type": "string",
        "description": "Target name to delete"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["target_name", "scope"]
  }
}
```

**Implementation:**
```python
# DELETE /openc3-api/targets/{target_name}
# Internally uses TargetModel.destroy()
```

### 5.3 Command/Telemetry Definition Tools

#### Tool: `add_command_packet`
```json
{
  "name": "add_command_packet",
  "description": "Add a new command packet to a target (runtime)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {
        "type": "string",
        "description": "Target name"
      },
      "packet_definition": {
        "type": "string",
        "description": "Command packet definition in COSMOS format"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["target_name", "packet_definition", "scope"]
  }
}
```

**Example packet_definition:**
```
COMMAND INST CUSTOM_CMD BIG_ENDIAN "Custom command"
  APPEND_ID_PARAMETER CMD_ID 16 UINT 1 1 1 "Command ID"
  APPEND_PARAMETER VALUE 32 FLOAT 0.0 100.0 50.0 "Value parameter"
  APPEND_PARAMETER FLAG 8 UINT MIN MAX 0 "Flag"
    STATE OFF 0
    STATE ON 1
```

**Implementation:**
```python
# Uses TargetModel.dynamic_update() method
# Parse definition, create Packet object, call dynamic_update
# This updates Redis and notifies microservices
```

#### Tool: `add_telemetry_packet`
```json
{
  "name": "add_telemetry_packet",
  "description": "Add a new telemetry packet to a target (runtime)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {
        "type": "string",
        "description": "Target name"
      },
      "packet_definition": {
        "type": "string",
        "description": "Telemetry packet definition in COSMOS format"
      },
      "scope": {
        "type": "string",
        "description": "COSMOS scope"
      }
    },
    "required": ["target_name", "packet_definition", "scope"]
  }
}
```

**Implementation:**
```python
# Uses TargetModel.dynamic_update() method
# Similar to add_command_packet but for telemetry
```

#### Tool: `modify_packet_limits`
```json
{
  "name": "modify_packet_limits",
  "description": "Modify limits for a telemetry item",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {"type": "string"},
      "packet_name": {"type": "string"},
      "item_name": {"type": "string"},
      "limits": {
        "type": "object",
        "properties": {
          "red_low": {"type": "number"},
          "yellow_low": {"type": "number"},
          "yellow_high": {"type": "number"},
          "red_high": {"type": "number"}
        }
      },
      "limits_set": {
        "type": "string",
        "description": "Limits set name (e.g., DEFAULT, TVAC)"
      },
      "scope": {"type": "string"}
    },
    "required": ["target_name", "packet_name", "item_name", "limits", "scope"]
  }
}
```

**Implementation:**
```python
# Get packet definition from Redis
# Modify limits in JSON
# Update with TargetModel.set_packet()
```

#### Tool: `enable_disable_command`
```json
{
  "name": "enable_disable_command",
  "description": "Enable or disable a command packet",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_name": {"type": "string"},
      "command_name": {"type": "string"},
      "enable": {"type": "boolean"},
      "scope": {"type": "string"}
    },
    "required": ["target_name", "command_name", "enable", "scope"]
  }
}
```

**Implementation:**
```python
# Uses CmdAPI.enable_cmd() or CmdAPI.disable_cmd()
```

### 5.4 Interface Management Tools

#### Tool: `connect_interface`
```json
{
  "name": "connect_interface",
  "description": "Connect an interface to start communication",
  "inputSchema": {
    "type": "object",
    "properties": {
      "interface_name": {"type": "string"},
      "scope": {"type": "string"}
    },
    "required": ["interface_name", "scope"]
  }
}
```

**Implementation:**
```python
# POST /openc3-api/interfaces/{interface_name}/connect
```

#### Tool: `disconnect_interface`
```json
{
  "name": "disconnect_interface",
  "description": "Disconnect an interface to stop communication",
  "inputSchema": {
    "type": "object",
    "properties": {
      "interface_name": {"type": "string"},
      "scope": {"type": "string"}
    },
    "required": ["interface_name", "scope"]
  }
}
```

**Implementation:**
```python
# POST /openc3-api/interfaces/{interface_name}/disconnect
```

## 6. Authentication & Security

### 6.1 Token Management

**Configuration:**
```yaml
# config/config.yaml
cosmos:
  url: http://openc3-cosmos-cmd-tlm-api:2901
  scope: DEFAULT
  auth:
    mode: token  # or 'keycloak' for Enterprise
    token: ${COSMOS_PASSWORD}  # From environment
    service_password: ${COSMOS_SERVICE_PASSWORD}  # Optional
```

**Implementation:**
```python
class CosmosAuth:
    def __init__(self, base_url, password=None, service_password=None):
        self.base_url = base_url
        self.password = password
        self.service_password = service_password
        self.session_token = None
        self.session_expiry = None

    def authenticate(self):
        """Get session token from COSMOS"""
        response = requests.post(
            f"{self.base_url}/openc3-api/auth/verify",
            json={"token": self.password}
        )
        if response.status_code == 200:
            self.session_token = response.text
            self.session_expiry = time.time() + 3600  # 1 hour
            return self.session_token
        raise AuthenticationError("Failed to authenticate")

    def get_headers(self):
        """Get auth headers for requests"""
        if not self.session_token or time.time() > self.session_expiry:
            self.authenticate()
        return {"Authorization": self.session_token}
```

### 6.2 MCP Server Authentication

**Options:**

**Option A: Environment Variable (Simple)**
```bash
export COSMOS_PASSWORD="your_password"
export COSMOS_URL="http://localhost:2900"
mcp-server-cosmos
```

**Option B: Config File**
```yaml
# ~/.cosmos-mcp/config.yaml
cosmos:
  url: http://localhost:2900
  password: "your_password"
  scope: DEFAULT
```

**Option C: OAuth/Token Delegation (Enterprise)**
```python
# User authenticates via OAuth
# MCP server receives delegated token
# All requests use that token
```

### 6.3 Scope Isolation

```python
class ScopeValidator:
    def __init__(self, allowed_scopes):
        self.allowed_scopes = allowed_scopes

    def validate(self, scope):
        if scope not in self.allowed_scopes:
            raise ValueError(f"Scope {scope} not allowed")
        return scope
```

### 6.4 Permission Model

**For COSMOS Core:**
- If authenticated → full access
- No fine-grained permissions

**For COSMOS Enterprise:**
- Check permissions via `/openc3-api/authorization` endpoint
- Permissions: `admin`, `cmd`, `tlm`, `script`, `config`
- Target-level permissions available

## 7. Error Handling & Observability

### 7.1 Error Responses

```python
class CosmosError(Exception):
    def __init__(self, message, cosmos_response=None):
        self.message = message
        self.cosmos_response = cosmos_response
        super().__init__(self.message)

class MCP_ErrorHandler:
    def handle_cosmos_error(self, e: CosmosError):
        return {
            "error": {
                "code": -32000,  # MCP custom error
                "message": e.message,
                "data": {
                    "cosmos_response": e.cosmos_response
                }
            }
        }
```

### 7.2 Logging

```python
import logging
import structlog

logger = structlog.get_logger()

logger.info(
    "cosmos_api_call",
    method="POST",
    endpoint="/openc3-api/targets",
    target="INST",
    scope="DEFAULT"
)
```

### 7.3 Monitoring

**Metrics to Track:**
- API call latency
- Error rates by endpoint
- Authentication failures
- Tool usage statistics
- Resource access patterns

**Implementation:**
```python
from prometheus_client import Counter, Histogram

cosmos_api_calls = Counter('cosmos_api_calls_total', 'Total API calls', ['method', 'endpoint'])
cosmos_api_latency = Histogram('cosmos_api_latency_seconds', 'API latency', ['endpoint'])
```

## 8. Example Usage Scenarios

### 8.1 Scenario: Add a New Target via AI Assistant

**User:** "Add a new target called TEMP_SENSOR with a telemetry packet that has temperature and humidity readings"

**AI Flow:**
1. Check existing targets (resource: `cosmos://targets/list`)
2. Design packet structure
3. Call tool: `create_target` with configuration
4. Call tool: `add_telemetry_packet` with packet definition
5. Verify creation (resource: `cosmos://targets/TEMP_SENSOR`)

**MCP Interaction:**
```json
// Step 1: List resources
{"method": "resources/list"}

// Step 2: Create target
{
  "method": "tools/call",
  "params": {
    "name": "create_target",
    "arguments": {
      "target_name": "TEMP_SENSOR",
      "config": {
        "language": "python"
      },
      "scope": "DEFAULT"
    }
  }
}

// Step 3: Add telemetry packet
{
  "method": "tools/call",
  "params": {
    "name": "add_telemetry_packet",
    "arguments": {
      "target_name": "TEMP_SENSOR",
      "packet_definition": "TELEMETRY TEMP_SENSOR STATUS BIG_ENDIAN \"Sensor readings\"\n  APPEND_ID_ITEM ID 16 UINT 1 \"Packet ID\"\n  APPEND_ITEM TEMP 32 FLOAT \"Temperature C\"\n  APPEND_ITEM HUMIDITY 32 FLOAT \"Humidity %\"",
      "scope": "DEFAULT"
    }
  }
}
```

### 8.2 Scenario: Modify Command Limits

**User:** "Change the yellow high limit for INST HEALTH_STATUS TEMP1 to 55 degrees"

**AI Flow:**
1. Read current packet definition (resource: `cosmos://telemetry/INST/HEALTH_STATUS`)
2. Identify item `TEMP1`
3. Call tool: `modify_packet_limits` with new limits
4. Verify change

### 8.3 Scenario: Install Plugin from Store

**User:** "Install the latest version of the Arduino plugin"

**AI Flow:**
1. Browse plugin store (resource: `cosmos://plugin-store`)
2. Find Arduino plugin
3. Call tool: `install_plugin` with store reference
4. Monitor installation status

## 9. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create MCP server skeleton
- [ ] Implement COSMOS REST API client
- [ ] Implement authentication
- [ ] Basic resource listing (plugins, targets)
- [ ] Docker container setup

### Phase 2: Read Operations (Weeks 3-4)
- [ ] All resource implementations
- [ ] Comprehensive target information
- [ ] Command/telemetry definition reading
- [ ] Interface status reading

### Phase 3: Write Operations (Weeks 5-7)
- [ ] Plugin install/uninstall tools
- [ ] Target create/modify tools
- [ ] Command/telemetry modification tools
- [ ] Interface control tools

### Phase 4: Advanced Features (Weeks 8-10)
- [ ] Streaming telemetry via MCP notifications
- [ ] Batch operations
- [ ] Configuration templates
- [ ] Enhanced error handling
- [ ] Comprehensive documentation

### Phase 5: Testing & Hardening (Weeks 11-12)
- [ ] Integration tests with real COSMOS instance
- [ ] Security audit
- [ ] Performance optimization
- [ ] Documentation and examples

## 10. Configuration Example

### docker-compose.yml Addition
```yaml
services:
  openc3-mcp-server:
    build: ./openc3-cosmos-mcp-server
    container_name: cosmos-mcp-server
    environment:
      COSMOS_API_URL: http://openc3-cosmos-cmd-tlm-api:2901
      COSMOS_SCOPE: DEFAULT
      COSMOS_PASSWORD: ${OPENC3_PASSWORD}
      MCP_TRANSPORT: stdio
      LOG_LEVEL: info
    depends_on:
      - openc3-cosmos-cmd-tlm-api
    networks:
      - openc3-cosmos-network
    volumes:
      - ./cosmos-mcp-config:/config
```

### MCP Client Configuration (Claude Desktop)
```json
{
  "mcpServers": {
    "cosmos": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "cosmos-mcp-server",
        "python",
        "-m",
        "cosmos_mcp_server"
      ],
      "env": {
        "COSMOS_API_URL": "http://openc3-cosmos-cmd-tlm-api:2901",
        "COSMOS_PASSWORD": "your_password_here"
      }
    }
  }
}
```

## 11. Security Considerations

### 11.1 Threats
1. **Unauthorized Access**: AI could be manipulated to access COSMOS
2. **Configuration Corruption**: Malicious modifications to targets
3. **Resource Exhaustion**: Excessive API calls
4. **Data Exfiltration**: Sensitive telemetry exposure

### 11.2 Mitigations
1. **Authentication Required**: Always validate tokens
2. **Audit Logging**: Log all modifications with user context
3. **Rate Limiting**: Implement per-client rate limits
4. **Read-Only Mode**: Optional mode for investigation only
5. **Scope Restrictions**: Limit to specific scopes
6. **Operation Approval**: Require human approval for destructive operations

### 11.3 Audit Log Format
```json
{
  "timestamp": "2025-11-05T15:30:00Z",
  "user": "mcp-server-user",
  "scope": "DEFAULT",
  "operation": "add_telemetry_packet",
  "target": "INST",
  "packet": "NEW_PACKET",
  "success": true,
  "ai_assistant": "claude",
  "conversation_id": "conv_abc123"
}
```

## 12. Future Enhancements

### 12.1 Streaming Telemetry
```json
{
  "method": "notifications/telemetry",
  "params": {
    "target": "INST",
    "packet": "HEALTH_STATUS",
    "items": ["TEMP1", "TEMP2"]
  }
}
```

### 12.2 Script Generation
```json
{
  "name": "generate_test_script",
  "description": "Generate a COSMOS test script from natural language",
  "inputSchema": {
    "description": {"type": "string"},
    "language": {"enum": ["ruby", "python"]}
  }
}
```

### 12.3 Configuration Templates
```json
{
  "name": "apply_template",
  "description": "Apply a configuration template (e.g., CubeSat standard)",
  "inputSchema": {
    "template_name": {"type": "string"},
    "target_name": {"type": "string"}
  }
}
```

### 12.4 Batch Operations
```json
{
  "name": "batch_update_limits",
  "description": "Update limits for multiple items at once",
  "inputSchema": {
    "updates": {
      "type": "array",
      "items": {
        "target": "string",
        "packet": "string",
        "item": "string",
        "limits": "object"
      }
    }
  }
}
```

## 13. Testing Strategy

### 13.1 Unit Tests
- Test each MCP tool independently
- Mock COSMOS API responses
- Validate input schemas

### 13.2 Integration Tests
- Test against real COSMOS instance
- Verify end-to-end flows
- Test error handling

### 13.3 AI Assistant Tests
- Create test conversations
- Verify resource discovery
- Test complex multi-step operations

## 14. Documentation Requirements

1. **README.md**: Quick start guide
2. **API.md**: Complete tool and resource reference
3. **EXAMPLES.md**: Common usage scenarios
4. **SECURITY.md**: Security best practices
5. **DEPLOYMENT.md**: Production deployment guide

## 15. Success Metrics

- **Functionality**: All CRUD operations working
- **Performance**: < 500ms average response time
- **Reliability**: 99.9% uptime
- **Security**: Zero unauthorized access incidents
- **Usability**: AI can complete tasks with < 3 tool calls on average

## 16. Conclusion

This MCP server architecture provides a comprehensive interface for AI assistants to interact with OpenC3 COSMOS. By exposing the existing REST APIs through the standardized MCP protocol, we enable:

1. **Natural Language Configuration**: AI can understand and modify COSMOS setups
2. **Rapid Prototyping**: Quickly create new targets and definitions
3. **Intelligent Assistance**: AI can suggest configurations and detect issues
4. **Documentation Generation**: Automatically document configurations
5. **Testing Automation**: Generate test scripts from requirements

The implementation leverages COSMOS's existing capabilities while adding a thin MCP protocol layer, ensuring minimal impact on the core system and maximum flexibility for future enhancements.
