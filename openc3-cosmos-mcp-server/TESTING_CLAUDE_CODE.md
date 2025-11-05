# Testing the MCP Server with Claude Code

This guide provides example questions and interactions to test the MCP server with Claude Code after installation.

## Setup Verification

Before starting, ensure:
1. ✅ Plugin installed in COSMOS (Admin → Plugins shows openc3-cosmos-mcp-server)
2. ✅ Microservice running (CmdTlmServer shows OPENC3_MCP_SERVER as Running)
3. ✅ Health check passes: `curl http://localhost:8765/health`
4. ✅ Claude Code configured with MCP server (see INSTALLATION.md)
5. ✅ Claude Code restarted after config change

## Test Scenarios

### Level 1: Basic Discovery

**Question 1: MCP Server Discovery**
```
What MCP servers are available?
```
**Expected**: Claude lists "cosmos" among available servers

**Question 2: Resource Discovery**
```
What resources does the cosmos MCP server provide?
```
**Expected**: Claude lists the available resource URIs (cosmos://targets/list, etc.)

---

### Level 2: Target Information

**Question 3: List Targets**
```
What targets are configured in COSMOS?
```
**Expected**:
- Claude queries `cosmos://targets/list`
- Returns: INST, INST2, EXAMPLE, TEMPLATED, SYSTEM

**Question 4: Target Details**
```
Tell me about the INST target
```
**Expected**:
- Claude queries `cosmos://targets/INST/info`
- Describes language (Ruby), interfaces, log settings, etc.

**Question 5: All Targets Overview**
```
Give me an overview of all configured targets including their interfaces
```
**Expected**:
- Claude queries info for each target
- Provides summary table or list with key details

---

### Level 3: Command Definitions

**Question 6: List Commands**
```
What commands does the INST target support?
```
**Expected**:
- Claude reads `cosmos://targets/INST/cmd_file`
- Parses COMMAND definitions from cmd.txt
- Lists: ABORT, ARYCMD, ASCIICMD, CLEAR, COLLECT, COSMOS_ERROR_HANDLE, etc.

**Question 7: Command Details**
```
Explain the INST COLLECT command in detail
```
**Expected**:
- Claude finds COLLECT command in cmd.txt
- Describes parameters: TYPE, DURATION, TEMP
- Explains parameter types, ranges, defaults
- Describes states (NORMAL, SPECIAL)

**Question 8: Command Parameters**
```
What are all the parameters for the INST ARYCMD command?
```
**Expected**:
- Parses ARYCMD definition
- Lists: CRC, ARRAY parameters
- Shows data types, sizes, arrays

---

### Level 4: Telemetry Definitions

**Question 9: List Telemetry**
```
What telemetry packets does INST send?
```
**Expected**:
- Claude reads `cosmos://targets/INST/tlm_file`
- Lists packets: ADCS, HEALTH_STATUS, IMAGE, MECH, PARAMS, etc.

**Question 10: Telemetry Details**
```
Show me the structure of the INST HEALTH_STATUS packet
```
**Expected**:
- Parses HEALTH_STATUS definition from tlm.txt
- Lists items: CCSDSVER, CCSDSTYPE, CCSDSSHF, etc.
- Shows data types, sizes, conversions

**Question 11: Telemetry Limits**
```
What are the limits for TEMP1 in the INST HEALTH_STATUS packet?
```
**Expected**:
- Finds TEMP1 item in HEALTH_STATUS
- Shows RED_LOW, YELLOW_LOW, YELLOW_HIGH, RED_HIGH values
- May show multiple limits sets if defined

---

### Level 5: Comparative Analysis

**Question 12: Compare Targets**
```
Compare the command sets of INST and INST2. What are the differences?
```
**Expected**:
- Reads both cmd.txt files
- Identifies common commands
- Identifies unique commands in each
- Highlights any parameter differences

**Question 13: Telemetry Comparison**
```
Do INST and INST2 have the same telemetry structure?
```
**Expected**:
- Reads both tlm.txt files
- Compares packet names and structures
- Notes similarities and differences

---

### Level 6: Configuration Files

**Question 14: List All Files**
```
What configuration files are available for the EXAMPLE target?
```
**Expected**:
- Queries `cosmos://targets/EXAMPLE/all_files`
- Lists: cmd.txt, tlm.txt, target.txt, procedures, lib files, screens

**Question 15: Screen Definitions**
```
Show me the screen definitions for INST
```
**Expected**:
- Queries files in screens/ directory
- Shows screen configuration (SCREEN keyword, widgets, etc.)

**Question 16: Procedure Files**
```
What test procedures are defined for INST?
```
**Expected**:
- Lists files in procedures/ directory
- Shows Ruby/Python scripts

---

### Level 7: Advanced Analysis

**Question 17: Data Type Analysis**
```
What types of conversions are used in INST telemetry?
```
**Expected**:
- Parses tlm.txt for conversion keywords
- Identifies: STATE, POLY_READ_CONVERSION, etc.
- Explains what each does

**Question 18: Hazardous Commands**
```
Which INST commands are marked as hazardous?
```
**Expected**:
- Parses cmd.txt for HAZARDOUS keyword
- Lists commands with hazardous flag
- Shows hazardous descriptions

**Question 19: Configuration Validation**
```
Are there any potential issues with the INST configuration?
```
**Expected**:
- Claude analyzes configurations
- Looks for: overlapping bit offsets, missing IDs, limit ordering issues
- May suggest improvements

**Question 20: Documentation Generation**
```
Generate a markdown document describing all INST commands with their parameters
```
**Expected**:
- Parses cmd.txt thoroughly
- Creates formatted markdown table
- Includes command names, descriptions, parameters

---

### Level 8: Cross-Target Analysis

**Question 21: Interface Mapping**
```
Which interfaces connect to which targets?
```
**Expected**:
- Queries info for all targets
- Creates mapping of interfaces to targets
- Shows which targets share interfaces

**Question 22: Target Dependencies**
```
Are there any dependencies between targets?
```
**Expected**:
- Examines REQUIRE statements in target.txt files
- Checks for shared libraries
- Notes interdependencies

---

## Expected Behaviors

### What Claude SHOULD Do:
- ✅ Query appropriate MCP resources
- ✅ Parse COSMOS configuration syntax correctly
- ✅ Provide accurate information from configs
- ✅ Handle missing targets/files gracefully
- ✅ Combine information from multiple resources
- ✅ Generate clear, structured responses

### What Claude CANNOT Do (by design):
- ❌ Modify configurations (read-only)
- ❌ Access real-time telemetry values
- ❌ Send commands to targets
- ❌ View command history
- ❌ Access log files

## Troubleshooting Test Issues

### Claude says "I cannot access that resource"

**Check:**
```bash
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "cosmos://targets/list"}}'
```

If this fails, MCP server has an issue.

### Claude returns empty or error responses

**Verify target exists:**
```bash
docker exec cosmos-openc3-operator-1 ruby -e "require 'openc3'; puts OpenC3::TargetModel.names(scope: 'DEFAULT').inspect"
```

### Claude gives incorrect information

**Manually verify the config file:**
```bash
curl -X POST http://localhost:8765/ -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "cosmos://targets/INST/cmd_file"}}' | jq -r '.result.contents[0].text'
```

Compare Claude's response to actual file content.

## Performance Expectations

| Query Type | Expected Response Time |
|-----------|----------------------|
| Target list | < 1 second |
| Target info | < 2 seconds |
| Single file (cmd/tlm) | < 3 seconds |
| All files | < 5 seconds |
| Analysis questions | 5-15 seconds |
| Complex comparisons | 10-30 seconds |

Response time includes:
- MCP query time (< 1s)
- Claude processing time (variable)
- Response generation time (variable)

## Success Criteria

The MCP server is working correctly if:

1. ✅ Claude can list all targets
2. ✅ Claude can read and parse cmd.txt files
3. ✅ Claude can read and parse tlm.txt files
4. ✅ Claude provides accurate command descriptions
5. ✅ Claude provides accurate telemetry descriptions
6. ✅ Claude can compare multiple targets
7. ✅ Claude handles errors gracefully
8. ✅ Response times are reasonable
9. ✅ No COSMOS errors in logs
10. ✅ Claude can answer complex analysis questions

## Tips for Best Results

1. **Be specific**: "Show INST commands" is better than "Show commands"
2. **One target at a time**: Start simple, then compare
3. **Use exact names**: "INST" not "inst" or "Inst"
4. **Ask follow-ups**: Build on previous questions
5. **Verify responses**: Check a few manually to build confidence

## Advanced Use Cases

Once basic testing passes, try:

- **Generate documentation** from configurations
- **Validate configurations** against standards
- **Create comparison reports** between targets
- **Identify patterns** in command/telemetry design
- **Suggest improvements** to configurations
- **Generate test scripts** based on commands
- **Create interface diagrams** from target info

## Reporting Issues

If you find issues, report with:

1. Exact question asked
2. Claude's response
3. Expected response
4. Output from manual curl test
5. Relevant logs from Docker

Happy testing!
