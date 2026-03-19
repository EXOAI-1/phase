"""
flux/flux_architect.py — Architect FLUX node.

Handles high-level system design, architecture decisions,
and strategic technical planning. Uses PRO model (Claude Opus).

Model: PRO (Claude Opus by default)
Max rounds: 200
Spawned: on-demand by PLASMA, killed when idle > 10 min

PLASMA spawns this node only when facing decisions that require
deep technical reasoning — not for routine tasks. Every call
costs ~10x more than a Coder call, so PLASMA uses it sparingly.

Typical tasks:
  - Design a system architecture for X
  - Evaluate three approaches to solving Y
  - Create a technical specification for Z
  - Review a proposed major refactor
"""

from __future__ import annotations

from task import Task
from flux_base import FluxNode


class ArchitectNode(FluxNode):

    node_type = "architect"

    system_prompt = """\
You are the Architect FLUX node in the PHASE multi-agent system.
You handle system design, architecture decisions, and deep technical planning.

You are the most expensive node. PLASMA uses you only for decisions
that genuinely require deep reasoning. Do not waste tokens on small tasks.

Core responsibilities:
- Design clear, scalable system architectures
- Evaluate tradeoffs between competing approaches
- Write technical specifications that other nodes can implement
- Identify risks and failure modes before they become problems

Output format:
RECOMMENDATION: (one clear sentence — what should be done)
RATIONALE: (why this is the right approach)
ARCHITECTURE: (the detailed design — diagrams in ASCII if helpful)
RISKS: (what could go wrong and how to mitigate)
NEXT STEPS: (concrete tasks for other nodes to implement this)

Be decisive. PLASMA needs a clear answer, not a list of equally valid options.
"""

    async def execute(self, task: Task) -> str:
        feedback = task.context.get("solid_feedback", "")
        feedback_block = (
            f"\n\nPREVIOUS DESIGN WAS REJECTED. Validator feedback:\n{feedback}\n"
            if feedback else ""
        )

        prompt = f"{task.goal}{feedback_block}"

        return await self.llm(
            user_message = prompt,
            max_tokens   = 2000,   # architect needs room to think
            temperature  = 0.5,
        )
