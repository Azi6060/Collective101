# Collective 101 agent definitions

101 individually editable definitions: 1 Mission Director, 10 heads, 90 employees. Each JSON file has a distinct system prompt, job, responsibilities, reporting line, skills, legacy local capabilities and memory namespace. `registry.build_roster()` validates the organization at startup.

Definitions share `agent_harness.py`; they do not duplicate provider clients, permissions or persistence. A file is an agent configuration, not a trained model or evidence of competence.

| Department | Agents | Head |
| --- | ---: | --- |
| [Distribution & Coordination](distribution/README.md) | 8 | distribution-001 |
| [Research & Intelligence](research/README.md) | 10 | research-001 |
| [Strategy & Planning](strategy/README.md) | 8 | strategy-001 |
| [Engineering & Automation](engineering/README.md) | 16 | engineering-001 |
| [Data & Analytics](data/README.md) | 10 | data-001 |
| [Design & Media](design/README.md) | 8 | design-001 |
| [Operations & Delivery](operations/README.md) | 8 | operations-001 |
| [Communications & Documentation](communications/README.md) | 6 | communications-001 |
| [Tools & Infrastructure](platform/README.md) | 10 | platform-001 |
| [Verification & Evaluation](assurance/README.md) | 16 | assurance-001 |

[Mission Director](organization/director-001.json) owns selection, integration and improvement proposals.

Inspect an effective definition and prompt:

```powershell
python -m collective101 agent operations-001
python -m collective101 agent engineering-003
```

Current departmental execution capability: produce draft code/text artifacts and review supplied artifacts. The five historical event tools remain in the legacy demo runtime. MCP/network access, running arbitrary code, deployments, automatic promotions and measured learning are not provided by these definitions.

Do not add executable permissions by editing a title, skill name or prompt. Runtime capabilities and phase/communication policies remain authoritative.
