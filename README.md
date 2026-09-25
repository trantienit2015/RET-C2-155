# RET-C2-155 — Retail Warehouse Physical AI Operations & Exception Handling Q&A Agent

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: RET

## Overview

Answers a warehouse operator's plain-text question about a robot exception (AMR, picking or
sorting robot). The input is the question itself as a string of up to 2,000 characters; an empty
question is rejected. All nodes require a verified-external caller except the final output node.

The question is classified by keywords into one of four types (exception code, SOP lookup,
escalation, safety) and a robot vendor is picked out of the text where named (Geek+, MiR,
GreyOrange, Mujin). Known exception codes are looked up in a small built-in table (three sample
codes: an emergency stop, a local stop and a low-battery warning); an unmatched question gets the
class `NONE`. SOP passages are retrieved by keyword overlap from a knowledge base passed in the
graph config as `kb` (a list of manual sections tagged by robot model); the bundled HTTP entry
point supplies no knowledge base, so it answers "No matching SOP found in the knowledge base."
until you provide one.

An emergency-stop class always carries a fixed, hard-coded safety warning, and the output node
rejects any response for that class that has lost the warning. The escalation decision comes
from a fixed table for the three known classes. For an unmatched question a language model, when
one is configured, picks one of `full_evacuation`, `local_stop`, `no_escalation` or
`manual_review`; a failed or unrecognised reply ends the run with an error. Without a model the
decision is `manual_review`. The bundled HTTP entry point supplies an Anthropic client only when
`ANTHROPIC_API_KEY` is available.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | 3.11 or later |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the exception-code table and keyword rules in `src/services/service.py`, and pass your own manual sections as `kb` in the graph config.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
