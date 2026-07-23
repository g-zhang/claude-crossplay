require "yaml"

ALLOWED_KEYS = %w[
  name description license allowed-tools metadata compatibility
].freeze

SKILLS = {
  "src/SKILL.md" => "crossplay-solver",
  "core/SKILL.md" => "crossplay-solver-core",
}.freeze

SKILLS.each do |path, expected_name|
  content = File.read(path, encoding: "UTF-8")
  match = content.match(/\A---\r?\n(.*?)\r?\n---(?:\r?\n|\z)/m)
  abort "#{path}: invalid YAML frontmatter" unless match

  frontmatter = YAML.safe_load(match[1], aliases: false)
  unless frontmatter.is_a?(Hash)
    abort "#{path}: frontmatter must be a mapping"
  end

  unexpected = frontmatter.keys - ALLOWED_KEYS
  unless unexpected.empty?
    abort "#{path}: unexpected frontmatter keys: #{unexpected.sort.join(', ')}"
  end

  name = frontmatter["name"]
  abort "#{path}: expected name #{expected_name}" unless name == expected_name
  unless name.match?(/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/) && name.length <= 64
    abort "#{path}: name must be kebab-case and at most 64 characters"
  end

  description = frontmatter["description"]
  unless description.is_a?(String) && !description.strip.empty?
    abort "#{path}: description must be a non-empty string"
  end
  if description.length > 1024 ||
      description.include?("<") ||
      description.include?(">")
    abort "#{path}: description violates skill metadata limits"
  end

  compatibility = frontmatter["compatibility"]
  if compatibility &&
      (!compatibility.is_a?(String) || compatibility.length > 500)
    abort "#{path}: compatibility must be a string of at most 500 characters"
  end

  puts "#{path}: valid"
end
