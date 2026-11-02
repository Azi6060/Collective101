# Retained engineering skill library

User-selected source: https://github.com/addyosmani/agent-skills

Pinned commit: `8bfcc1f9916f2eea55494d8c1fa7f4bde867dd9e` (downloaded 31 October 2026, Asia/Kuala_Lumpur).
License: MIT; original license and attribution are retained in `agent-skills/LICENSE`.

The full local checkout is `third_party/agent-skills`. It includes skills, references, personas and native plugin manifests. It is ignored by the main Git repository to avoid accidentally tracking an embedded repository. No upstream scripts or hooks were executed, and no global plugin configuration was changed. The relevant Markdown workflows can be read and applied directly in this session. Keeping plugin manifests does not mean the host has registered them.

To reproduce the checkout from the main project directory:

```powershell
git clone https://github.com/addyosmani/agent-skills.git third_party/agent-skills
git -C third_party/agent-skills checkout 8bfcc1f9916f2eea55494d8c1fa7f4bde867dd9e
```

Applied for this implementation: `using-agent-skills`, `code-review-and-quality`, `test-driven-development`, `debugging-and-error-recovery`, and `documentation-and-adrs`. The skill pack was selected after implementation had begun; we do not claim that all earlier code was written test-first. A subsequently identified Windows-path collision was reproduced with a failing test before its fix. A deliberate role-policy mutation was detected by the tests and restored.

These are development workflows used while building Collective 101. They are not yet installed as callable capabilities inside the organization's worker harness. A skill document cannot grant network access, execution, deployment or MCP connectivity.
