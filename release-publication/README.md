# Verified GitHub Release publication

After an immutable signed `folklore-mcp-v<version>` tag has successfully published to the Official MCP Registry, update `current.json` and its versioned release notes on `main`. The narrowly scoped GitHub Actions workflow creates a GitHub Release for that existing tag and attaches the tested companion Skill archive and checksum. It never creates, moves or edits a tag, and it preserves an existing published release.

The request pins the annotated tag object, peeled source commit, successful Official Registry workflow run, checked-in notes, archive path and SHA-256. Verification requires exact tagged `registry/server.json` identity/version/description/endpoint agreement with the active latest Official Registry record. The archive and checksum are extracted from the immutable tag, not rebuilt from the publication commit. The tagged commit must be an ancestor of the publishing checkout.

`python3 ops/publish_github_release.py --prepare-only` performs read-only verification. `--publish` additionally requires the publication job's scoped GitHub Actions token. Permissions are limited to `contents: write` and `actions: read` for that job; checkout does not persist credentials. The workflow is also manually runnable for a transient verification failure. No token is stored in the repository or retrieved from an operator's accounts.

This workflow verifies the pinned tag object and successful Registry publication; it does not assert that GitHub recognizes the tag signer's key. A Registry release and GitHub Release are separate publication events. Confirm the resulting release URL and assets, then observe any Zenodo DOI created by the configured archive integration before claiming it exists.

MCP Central remains governed by its separate Registry workflow. Biorouter bundles use the distinct signed `folklore-biorouter-v<version>` tag and its existing build-and-install verification workflow.
