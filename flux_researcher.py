"""
flux/flux_researcher.py — Researcher FLUX node.

Handles research, summarisation, web context, and fact-finding.
Uses web search when available (OPENAI_API_KEY for search tool).

Model: NANO (Gemini Flash by default)
Max rounds: 20
Always spawned: yes
"""

from __future__ import annotations

import os

from task import Task
from flux_base import FluxNode


class ResearcherNode(FluxNode):

    node_type = "researcher"

    system_prompt = """\
You are the Researcher FLUX node in the PHASE multi-agent system.
You find, summarise, and synthesise information.

Core responsibilities:
- Research topics thoroughly using your training knowledge
- Summarise long documents into key points
- Find relevant context for coding or planning tasks
- Identify gaps, risks, or important considerations

Output format:
- Clear structured summary
- Key findings as bullet points
- Sources or caveats noted
- Relevance to the task explained

Be concise. PLASMA and other nodes read your output — every word counts.
"""

    async def execute(self, task: Task) -> str:
        feedback = task.context.get("solid_feedback", "")
        feedback_block = (
            f"\n\nPREVIOUS ATTEMPT REJECTED. Validator feedback:\n{feedback}\n"
            if feedback else ""
        )

        prompt = f"Research the following:\n\n{task.goal}{feedback_block}"

        return await self.llm(
            user_message = prompt,
            max_tokens   = 800,
            temperature  = 0.4,
        )
