# encoding: ascii-8bit

Gem::Specification.new do |s|
  s.name = 'openc3-cosmos-mcp-server'
  s.summary = 'OpenC3 COSMOS MCP Server Plugin'
  s.description = <<-EOF
    Model Context Protocol (MCP) server for OpenC3 COSMOS.
    Allows AI assistants to query target configurations, command definitions,
    and telemetry definitions through a standardized protocol.
  EOF
  s.authors = ['OpenC3 Community']
  s.email = ['support@openc3.com']
  s.homepage = 'https://github.com/OpenC3/cosmos'
  s.license = 'AGPL-3.0-only'

  s.platform = Gem::Platform::RUBY

  if ENV['VERSION']
    s.version = ENV['VERSION'].dup
  else
    time = Time.now.strftime("%Y%m%d%H%M%S")
    s.version = '0.0.0' + ".#{time}"
  end
  s.files = Dir.glob("{targets,microservices,tools,lib}/**/*") + %w(Rakefile LICENSE.txt README.md plugin.txt)
end
