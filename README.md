# claude-crossplay

Claude skill that takes a NYT Crossplay screenshot and provides the best moves.

## Project Structure

```
src/
  SKILL.md        # Skill manifest describing the skill's purpose, inputs, and outputs
  scripts/        # Skill scripts and logic
.github/
  workflows/
    release-skill.yml   # CI workflow to build and publish .skill releases
```

## Releasing

To create a new release:

1. Tag a commit with a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. The GitHub Actions workflow will automatically:
   - Zip everything inside `src/*` into `crossplay-solver.skill`
   - Create a GitHub Release for the tag
   - Attach `crossplay-solver.skill` as a release asset