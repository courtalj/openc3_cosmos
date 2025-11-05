#!/usr/bin/env ruby
# encoding: ascii-8bit

# OpenC3 COSMOS MCP Server - Ruby Client
#
# This script provides a command-line interface to COSMOS internal APIs.
# It's called by the Python MCP server via subprocess to access COSMOS data.
#
# Usage: ruby cosmos_client.rb <method> <scope> [args...]
# Output: JSON to stdout

require 'json'
require 'openc3'
require 'openc3/models/target_model'
require 'openc3/utilities/bucket'

# Helper to output JSON and exit
def output_json(data)
  puts JSON.generate(data)
  exit 0
end

def output_error(message)
  output_json({ 'error' => message })
end

# Parse command line arguments
if ARGV.length < 2
  STDERR.puts "Usage: #{$0} <method> <scope> [args...]"
  STDERR.puts "Methods: get_target_names, get_target_info, get_target_file, get_all_target_files"
  exit 1
end

method = ARGV[0]
scope = ARGV[1]
args = ARGV[2..-1] || []

begin
  # Initialize COSMOS environment
  OpenC3.setup_env unless ENV['OPENC3_NO_SETUP']

  case method
  when 'get_target_names'
    # Get list of all target names
    target_names = OpenC3::TargetModel.names(scope: scope)
    output_json(target_names)

  when 'get_target_info'
    # Get target metadata
    if args.length < 1
      output_error("Missing target_name argument")
    end

    target_name = args[0]
    target = OpenC3::TargetModel.get(name: target_name, scope: scope)

    if target.nil?
      output_error("Target not found: #{target_name}")
    end

    # Extract relevant information
    info = {
      'name' => target.name,
      'folder_name' => target.folder_name,
      'requires' => target.requires,
      'ignored_parameters' => target.ignored_parameters,
      'ignored_items' => target.ignored_items,
      'cmd_tlm_files' => target.cmd_tlm_files,
      'language' => target.language,
      'limits_groups' => target.limits_groups,
      'cmd_buffer_depth' => target.cmd_buffer_depth,
      'cmd_log_cycle_time' => target.cmd_log_cycle_time,
      'cmd_log_cycle_size' => target.cmd_log_cycle_size,
      'tlm_log_cycle_time' => target.tlm_log_cycle_time,
      'tlm_log_cycle_size' => target.tlm_log_cycle_size,
      'reduced_minute_log_retain_time' => target.reduced_minute_log_retain_time,
      'reduced_hour_log_retain_time' => target.reduced_hour_log_retain_time,
      'reduced_day_log_retain_time' => target.reduced_day_log_retain_time,
      'log_retain_time' => target.log_retain_time,
      'reducer_disable' => target.reducer_disable,
      'reducer_max_cpu_utilization' => target.reducer_max_cpu_utilization
    }

    # Get associated interfaces
    begin
      interfaces_hash = OpenC3::Store.hgetall("#{scope}__openc3_interfaces")
      interfaces = []
      interfaces_hash.each do |interface_name, interface_json|
        interface_data = JSON.parse(interface_json)
        # Check if this interface maps to this target
        if interface_data['cmd_target_names']&.include?(target_name) ||
           interface_data['tlm_target_names']&.include?(target_name) ||
           interface_data['target_names']&.include?(target_name)
          interfaces << interface_name
        end
      end
      info['interfaces'] = interfaces
    rescue => e
      STDERR.puts "Warning: Could not get interfaces: #{e.message}"
      info['interfaces'] = []
    end

    output_json(info)

  when 'get_target_file'
    # Get raw content of a target configuration file
    if args.length < 2
      output_error("Missing target_name and/or filename arguments")
    end

    target_name = args[0]
    filename = args[1]

    # Verify target exists
    target = OpenC3::TargetModel.get(name: target_name, scope: scope)
    if target.nil?
      output_error("Target not found: #{target_name}")
    end

    # Get file from bucket
    begin
      bucket = OpenC3::Bucket.getClient()

      # Try multiple possible paths
      possible_paths = [
        "#{scope}/targets/#{target_name}/#{filename}",
        "#{scope}/targets_modified/#{target_name}/#{filename}"
      ]

      content = nil
      found_path = nil

      possible_paths.each do |path|
        begin
          result = bucket.get_object(bucket: ENV['OPENC3_CONFIG_BUCKET'], key: path)
          content = result.body.read
          found_path = path
          break
        rescue => e
          # Try next path
          STDERR.puts "Path not found: #{path}"
        end
      end

      if content.nil?
        output_error("File not found: #{filename} for target #{target_name}")
      end

      output_json({
        'content' => content,
        'path' => found_path,
        'filename' => filename
      })

    rescue => e
      output_error("Error reading file: #{e.message}")
    end

  when 'get_all_target_files'
    # Get all configuration files for a target
    if args.length < 1
      output_error("Missing target_name argument")
    end

    target_name = args[0]

    # Verify target exists
    target = OpenC3::TargetModel.get(name: target_name, scope: scope)
    if target.nil?
      output_error("Target not found: #{target_name}")
    end

    begin
      bucket = OpenC3::Bucket.getClient()
      files = {}

      # Common file patterns to retrieve
      file_patterns = [
        'cmd_tlm/cmd.txt',
        'cmd_tlm/tlm.txt',
        'target.txt',
        'procedures/*.rb',
        'procedures/*.py',
        'lib/*.rb',
        'lib/*.py',
        'screens/*.txt'
      ]

      # List all files in target directory
      prefix = "#{scope}/targets/#{target_name}/"
      begin
        response = bucket.list_objects(
          bucket: ENV['OPENC3_CONFIG_BUCKET'],
          prefix: prefix
        )

        response.each do |object|
          # Get relative path
          relative_path = object.key.sub(prefix, '')
          next if relative_path.empty? || relative_path.end_with?('/')

          begin
            result = bucket.get_object(bucket: ENV['OPENC3_CONFIG_BUCKET'], key: object.key)
            content = result.body.read

            # Only include text files (skip binaries)
            if content.encoding == Encoding::ASCII_8BIT && !content.valid_encoding?
              # Skip binary files
              files[relative_path] = "<binary file>"
            else
              files[relative_path] = content
            end
          rescue => e
            STDERR.puts "Error reading #{object.key}: #{e.message}"
            files[relative_path] = "<error reading file>"
          end
        end
      rescue => e
        STDERR.puts "Error listing files: #{e.message}"
      end

      # Also check modified files
      modified_prefix = "#{scope}/targets_modified/#{target_name}/"
      begin
        response = bucket.list_objects(
          bucket: ENV['OPENC3_CONFIG_BUCKET'],
          prefix: modified_prefix
        )

        response.each do |object|
          relative_path = object.key.sub(modified_prefix, '')
          next if relative_path.empty? || relative_path.end_with?('/')

          # Mark as modified
          relative_path = "#{relative_path} (modified)"

          begin
            result = bucket.get_object(bucket: ENV['OPENC3_CONFIG_BUCKET'], key: object.key)
            content = result.body.read
            files[relative_path] = content
          rescue => e
            STDERR.puts "Error reading modified #{object.key}: #{e.message}"
          end
        end
      rescue => e
        # Modified directory might not exist
        STDERR.puts "No modified files: #{e.message}"
      end

      output_json(files)

    rescue => e
      output_error("Error getting target files: #{e.message}")
    end

  else
    output_error("Unknown method: #{method}")
  end

rescue => e
  STDERR.puts "Error: #{e.message}"
  STDERR.puts e.backtrace.join("\n")
  output_error("Internal error: #{e.message}")
end
