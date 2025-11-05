#!/usr/bin/env python3
"""
OpenC3 COSMOS MCP Server

Model Context Protocol (MCP) server that provides read-only access to COSMOS
target configurations, command definitions, and telemetry definitions.

This server implements the MCP protocol over HTTP and uses a Ruby bridge to
access COSMOS internal APIs.
"""

import os
import sys
import json
import subprocess
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_server')

# Configuration from environment
MCP_PORT = int(os.environ.get('MCP_PORT', '8765'))
COSMOS_SCOPE = os.environ.get('COSMOS_SCOPE', 'DEFAULT')
RUBY_CLIENT_PATH = os.path.join(os.path.dirname(__file__), 'cosmos_client.rb')

app = FastAPI(title="COSMOS MCP Server", version="0.1.0")


# MCP Protocol Models
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class InitializeParams(BaseModel):
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]


class ResourceUri(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None


class ResourceContents(BaseModel):
    uri: str
    mimeType: str
    text: Optional[str] = None


# COSMOS Client Interface
class CosmosClient:
    """Interface to COSMOS Ruby APIs via subprocess"""

    def __init__(self, scope: str):
        self.scope = scope

    def call_ruby(self, method: str, *args) -> Any:
        """Call Ruby client method and return JSON result"""
        try:
            cmd = ['ruby', RUBY_CLIENT_PATH, method, self.scope] + list(args)
            logger.info(f"Calling Ruby client: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"Ruby client error: {result.stderr}")
                raise RuntimeError(f"Ruby client failed: {result.stderr}")

            # Parse JSON response from Ruby
            return json.loads(result.stdout)

        except subprocess.TimeoutExpired:
            logger.error("Ruby client timeout")
            raise RuntimeError("COSMOS API call timed out")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ruby response: {result.stdout}")
            raise RuntimeError(f"Invalid response from COSMOS: {e}")
        except Exception as e:
            logger.error(f"Ruby client exception: {e}")
            raise

    def get_target_names(self) -> List[str]:
        """Get list of all target names"""
        return self.call_ruby('get_target_names')

    def get_target_info(self, target_name: str) -> Dict[str, Any]:
        """Get target metadata"""
        return self.call_ruby('get_target_info', target_name)

    def get_target_file(self, target_name: str, filename: str) -> str:
        """Get raw content of a target configuration file"""
        result = self.call_ruby('get_target_file', target_name, filename)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result.get('content', '')

    def get_all_target_files(self, target_name: str) -> Dict[str, str]:
        """Get all configuration files for a target"""
        return self.call_ruby('get_all_target_files', target_name)


# Global COSMOS client
cosmos = CosmosClient(COSMOS_SCOPE)


# MCP Resource Handlers
class MCPResourceHandler:
    """Handles MCP resource requests"""

    @staticmethod
    def list_resources() -> List[ResourceUri]:
        """List all available MCP resources"""
        try:
            targets = cosmos.get_target_names()
            resources = [
                ResourceUri(
                    uri="cosmos://targets/list",
                    name="Target List",
                    description="List of all configured COSMOS targets",
                    mimeType="application/json"
                )
            ]

            # Add resources for each target
            for target in targets:
                resources.extend([
                    ResourceUri(
                        uri=f"cosmos://targets/{target}/info",
                        name=f"{target} Information",
                        description=f"Metadata for target {target}",
                        mimeType="application/json"
                    ),
                    ResourceUri(
                        uri=f"cosmos://targets/{target}/cmd_file",
                        name=f"{target} Commands",
                        description=f"Command definitions (cmd.txt) for {target}",
                        mimeType="text/plain"
                    ),
                    ResourceUri(
                        uri=f"cosmos://targets/{target}/tlm_file",
                        name=f"{target} Telemetry",
                        description=f"Telemetry definitions (tlm.txt) for {target}",
                        mimeType="text/plain"
                    ),
                    ResourceUri(
                        uri=f"cosmos://targets/{target}/all_files",
                        name=f"{target} All Files",
                        description=f"All configuration files for {target}",
                        mimeType="application/json"
                    )
                ])

            return resources
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            raise

    @staticmethod
    def read_resource(uri: str) -> ResourceContents:
        """Read a specific resource by URI"""
        try:
            logger.info(f"Reading resource: {uri}")

            if not uri.startswith("cosmos://"):
                raise ValueError(f"Invalid URI scheme: {uri}")

            path = uri.replace("cosmos://", "")
            parts = path.split("/")

            # cosmos://targets/list
            if path == "targets/list":
                targets = cosmos.get_target_names()
                return ResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=json.dumps(targets, indent=2)
                )

            # cosmos://targets/{target_name}/...
            if parts[0] == "targets" and len(parts) >= 2:
                target_name = parts[1]

                # cosmos://targets/{target_name}/info
                if len(parts) == 3 and parts[2] == "info":
                    info = cosmos.get_target_info(target_name)
                    return ResourceContents(
                        uri=uri,
                        mimeType="application/json",
                        text=json.dumps(info, indent=2)
                    )

                # cosmos://targets/{target_name}/cmd_file
                if len(parts) == 3 and parts[2] == "cmd_file":
                    content = cosmos.get_target_file(target_name, "cmd_tlm/cmd.txt")
                    return ResourceContents(
                        uri=uri,
                        mimeType="text/plain",
                        text=content
                    )

                # cosmos://targets/{target_name}/tlm_file
                if len(parts) == 3 and parts[2] == "tlm_file":
                    content = cosmos.get_target_file(target_name, "cmd_tlm/tlm.txt")
                    return ResourceContents(
                        uri=uri,
                        mimeType="text/plain",
                        text=content
                    )

                # cosmos://targets/{target_name}/all_files
                if len(parts) == 3 and parts[2] == "all_files":
                    files = cosmos.get_all_target_files(target_name)
                    return ResourceContents(
                        uri=uri,
                        mimeType="application/json",
                        text=json.dumps(files, indent=2)
                    )

                # cosmos://targets/{target_name}/files/{path...}
                if len(parts) >= 4 and parts[2] == "files":
                    file_path = "/".join(parts[3:])
                    content = cosmos.get_target_file(target_name, file_path)
                    return ResourceContents(
                        uri=uri,
                        mimeType="text/plain",
                        text=content
                    )

            raise ValueError(f"Unknown resource URI: {uri}")

        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise


# MCP Protocol Handlers
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test COSMOS connection
        targets = cosmos.get_target_names()
        return {
            "status": "ok",
            "cosmos_connected": True,
            "scope": COSMOS_SCOPE,
            "targets_count": len(targets)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "cosmos_connected": False,
                "error": str(e)
            }
        )


@app.post("/")
async def mcp_handler(request: Request):
    """Main MCP JSON-RPC 2.0 handler"""
    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)

        logger.info(f"MCP request: {rpc_request.method}")

        # Handle different MCP methods
        if rpc_request.method == "initialize":
            result = {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "resources": {
                        "list": True,
                        "read": True
                    }
                },
                "serverInfo": {
                    "name": "cosmos-mcp-server",
                    "version": "0.1.0"
                }
            }
            return JsonRpcResponse(
                id=rpc_request.id,
                result=result
            ).dict()

        elif rpc_request.method == "resources/list":
            resources = MCPResourceHandler.list_resources()
            return JsonRpcResponse(
                id=rpc_request.id,
                result={"resources": [r.dict() for r in resources]}
            ).dict()

        elif rpc_request.method == "resources/read":
            if not rpc_request.params or 'uri' not in rpc_request.params:
                raise ValueError("Missing 'uri' parameter")

            uri = rpc_request.params['uri']
            content = MCPResourceHandler.read_resource(uri)
            return JsonRpcResponse(
                id=rpc_request.id,
                result={"contents": [content.dict()]}
            ).dict()

        else:
            return JsonRpcResponse(
                id=rpc_request.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {rpc_request.method}"
                }
            ).dict()

    except Exception as e:
        logger.error(f"MCP handler error: {e}", exc_info=True)
        return JsonRpcResponse(
            id=getattr(rpc_request, 'id', None) if 'rpc_request' in locals() else None,
            error={
                "code": -32000,
                "message": str(e)
            }
        ).dict()


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting COSMOS MCP Server on port {MCP_PORT}")
    logger.info(f"COSMOS Scope: {COSMOS_SCOPE}")
    logger.info(f"Ruby Client: {RUBY_CLIENT_PATH}")

    # Install Python dependencies if needed
    logger.info("Ensuring Python dependencies are installed...")
    subprocess.run([
        sys.executable, '-m', 'pip', 'install', '-q', '-r',
        os.path.join(os.path.dirname(__file__), 'requirements.txt')
    ])

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=MCP_PORT,
        log_level="info"
    )
