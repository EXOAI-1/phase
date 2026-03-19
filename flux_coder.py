"""
flux/flux_coder.py — Coder FLUX node.

Handles all code-related tasks: writing, editing, debugging,
refactoring, and explaining code.

Model: MID (Claude Sonnet by default)
Max rounds: 80
Always spawned: yes

When SOLID rejects output, the feedback is injected into the
next attempt so the node can correct its mistake.
"""

from __future__ import annotations

from task import Task
from flux_base import FluxNode


class CoderNode(FluxNode):

    node_type = "coder"

    system_prompt = """\
You are the Coder FLUX node in the PHASE multi-agent system.
You write, edit, debug, and explain code.

Core responsibilities:
- Write clean, well-commented, working code
- Follow the language's best practices
- Include error handling where appropriate
- Explain your implementation briefly at the end

When given feedback from previous validation (SOLID_FEEDBACK),
address it specifically in your revised output.

Output format:
- If writing code: include the code in a code block, then a brief explanation
- If explaining code: clear prose with examples
- If debugging: identify the issue, show the fix, explain why
"""

    async def execute(self, task: Task) -> str:
        feedback = task.context.get("solid_feedback", "")
        feedback_block = (
            f"\n\nPREVIOUS ATTEMPT WAS REJECTED. Validator feedback:\n{feedback}\n"
            f"Address this specifically in your response.\n"
            if feedback else ""
        )

        prompt = f"{task.goal}{feedback_block}"

        return await self.llm(
            user_message  = prompt,
            max_tokens    = 1500,
            temperature   = 0.3,   # low temp for code
            extra_context = (
                f"Additional context: {task.context}"
                if task.context and task.context != {"solid_feedback": feedback}
                else ""
            ),
        )
