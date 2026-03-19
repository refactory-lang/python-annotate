---
name: spec-from-issue
description: Create a speckit specification from a GitHub issue. Fetches the issue,
  extracts context, and runs speckit.specify with the issue content as the feature
  description. Use when an issue is labeled 'spec-ready' or when manually converting
  an issue to a spec.
compatibility: Requires spec-kit project structure with .specify/ directory and gh CLI
metadata:
  author: refactory-lang
  version: 1.0.0
---

# Spec from Issue

## User Input

```text
$ARGUMENTS
```

## Instructions

This skill converts a GitHub issue into a speckit specification by:
1. Fetching the issue content from GitHub
2. Extracting the feature description and context
3. Running `/speckit.specify` with the issue as context
4. Linking the resulting spec back to the issue

### Step 1: Parse Input

The user input should be one of:
- A GitHub issue URL: `https://github.com/org/repo/issues/123`
- A short reference: `#123` (uses current repo)
- A repo + number: `org/repo#123`

If the input is empty, check for issues labeled `spec-ready` in the current repo:
```bash
gh issue list --label "spec-ready" --state open --json number,title,url
```
Present the list and ask the user which issue to specify.

### Step 2: Fetch Issue Content

```bash
gh issue view <number> --repo <repo> --json title,body,labels,number,url
```

### Step 3: Extract Spec Context

From the issue body, extract:
- **Feature description**: The `## Overview` or `## Summary` section, or the full body if no sections
- **Scope**: The `## Scope` section if present
- **Success criteria**: The `## Success Criteria` section if present
- **Dependencies**: The `## Context` or `## Dependencies` section if present
- **Suggested specify command**: Look for a fenced code block starting with `/speckit.specify` — if found, use that as the feature description

### Step 4: Run speckit.specify

Invoke the `speckit-specify` skill with the extracted feature description. The description should be constructed as:

```
<issue title>. <overview/description from issue body>. <any scope details>. <any dependencies>. GitHub Issue: <issue URL>
```

If the issue contains a suggested `/speckit.specify` command in a code block, use that command text instead (but append `GitHub Issue: <issue URL>` to it).

### Step 5: Link Back to Issue

After the spec is created successfully:

1. **Comment on the issue** with a link to the spec:
```bash
gh issue comment <number> --repo <repo> --body "Specification created: \`specs/<branch-name>/spec.md\` on branch \`<branch-name>\`

Created via \`/spec-from-issue\`. Review the spec and proceed with \`/speckit.plan\` when ready."
```

2. **Update issue labels** — remove `needs-spec` and `spec-ready`, add `has-spec`:
```bash
gh issue edit <number> --repo <repo> --remove-label "needs-spec" --remove-label "spec-ready" --add-label "has-spec"
```
(Create the `has-spec` label first if it doesn't exist)

3. **Update the GitHub Project item** — if the issue is in the "Refactory Phase Tracker" project, update its Status to "In Progress":
```bash
# This is informational — the project field update may require GraphQL
```

### Step 6: Report

Output:
- Issue URL
- Spec file path
- Branch name
- Confirmation that issue was updated
