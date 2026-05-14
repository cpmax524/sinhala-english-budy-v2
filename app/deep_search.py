import datetime
import logging
import os
import re
from typing import Literal

from google.adk.agents import BaseAgent, LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.genai import types as genai_types
from pydantic import BaseModel, Field

# Configure the LLM based on environment
_use_vertex = (
    os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper() == "TRUE"
)
WORKER_MODEL = (
    "gemini-2.5-pro"  # General research/writing
    if _use_vertex
    else "gemini-2.5-pro"
)


# --- Structured Output Models ---
class SearchQuery(BaseModel):
    """Model representing a specific search query for web search."""

    search_query: str = Field(
        description="A highly specific and targeted query for web search."
    )


class Feedback(BaseModel):
    """Model for providing evaluation feedback on research quality."""

    grade: Literal["pass", "fail"] = Field(
        description="Evaluation result. 'pass' if the research is sufficient, 'fail' if it needs revision."
    )
    comment: str = Field(
        description="Detailed explanation of the evaluation, highlighting strengths and/or weaknesses of the research."
    )
    follow_up_queries: list[SearchQuery] | None = Field(
        default=None,
        description="A list of specific, targeted follow-up search queries needed to fix research gaps. This should be null or empty if the grade is 'pass'.",
    )


# --- Callbacks ---
def collect_research_sources_callback(callback_context: CallbackContext) -> None:
    session = callback_context._invocation_context.session
    url_to_short_id = callback_context.state.get("url_to_short_id", {})
    sources = callback_context.state.get("sources", {})
    id_counter = len(url_to_short_id) + 1

    for event in session.events:
        if not (event.grounding_metadata and event.grounding_metadata.grounding_chunks):
            continue
        chunks_info = {}
        for idx, chunk in enumerate(event.grounding_metadata.grounding_chunks):
            if not chunk.web:
                continue
            url = chunk.web.uri
            title = (
                chunk.web.title
                if chunk.web.title != chunk.web.domain
                else chunk.web.domain
            )
            if url not in url_to_short_id:
                short_id = f"src-{id_counter}"
                url_to_short_id[url] = short_id
                sources[short_id] = {
                    "short_id": short_id,
                    "title": title,
                    "url": url,
                    "domain": chunk.web.domain,
                    "supported_claims": [],
                }
                id_counter += 1
            chunks_info[idx] = url_to_short_id[url]

        if event.grounding_metadata.grounding_supports:
            for support in event.grounding_metadata.grounding_supports:
                confidence_scores = support.confidence_scores or []
                chunk_indices = support.grounding_chunk_indices or []
                for i, chunk_idx in enumerate(chunk_indices):
                    if chunk_idx in chunks_info:
                        short_id = chunks_info[chunk_idx]
                        confidence = (
                            confidence_scores[i] if i < len(confidence_scores) else 0.5
                        )
                        text_segment = support.segment.text if support.segment else ""
                        sources[short_id]["supported_claims"].append(
                            {
                                "text_segment": text_segment,
                                "confidence": confidence,
                            }
                        )

    callback_context.state["url_to_short_id"] = url_to_short_id
    callback_context.state["sources"] = sources


def citation_replacement_callback(
    callback_context: CallbackContext,
) -> genai_types.Content:
    final_report = callback_context.state.get("final_cited_report", "")
    sources = callback_context.state.get("sources", {})

    def tag_replacer(match: re.Match) -> str:
        short_id = match.group(1)
        if not (source_info := sources.get(short_id)):
            logging.warning(f"Invalid citation tag found and removed: {match.group(0)}")
            return ""
        display_text = source_info.get("title", source_info.get("domain", short_id))
        return f" [{display_text}]({source_info['url']})"

    processed_report = re.sub(
        r'<cite\s+source\s*=\s*["\']?\s*(src-\d+)\s*["\']?\s*/>',
        tag_replacer,
        final_report,
    )
    processed_report = re.sub(r"\s+([.,;:])", r"\1", processed_report)
    callback_context.state["final_report_with_citations"] = processed_report
    return genai_types.Content(parts=[genai_types.Part(text=processed_report)])


# --- Escalation Checker Agent ---
class EscalationChecker(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            logging.info(
                f"[{self.name}] Research evaluation passed. Escalating to stop loop."
            )
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            logging.info(
                f"[{self.name}] Research evaluation failed or not found. Loop will continue."
            )
            yield Event(author=self.name)


# --- Plan Generator Agent ---
plan_generator = LlmAgent(
    model=WORKER_MODEL,
    name="plan_generator",
    description="Generates a 5 line action-oriented research plan based on the user's topic.",
    instruction=f"""
    You are a research strategist. Your job is to create a high-level RESEARCH PLAN for the requested topic.

    **GENERAL INSTRUCTION: CLASSIFY TASK TYPES**
    Your plan must clearly classify each goal for downstream execution. Each bullet point should start with a task type prefix:
    - **`[RESEARCH]`**: For goals that primarily involve information gathering, investigation, analysis, or data collection.
    - **`[DELIVERABLE]`**: For goals that involve synthesizing collected information, creating structured outputs, or compiling final output artifacts.

    **INITIAL RULE: Your initial output MUST start with a bulleted list of 5 action-oriented research goals or key questions, followed by any *inherently implied* deliverables.**
    - All initial 5 goals will be classified as `[RESEARCH]` tasks.
    - A good goal for `[RESEARCH]` starts with a verb like "Analyze," "Identify," "Investigate."
    - **Proactive Implied Deliverables:** If any of your initial 5 `[RESEARCH]` goals inherently imply a standard output, you MUST add these as additional distinct goals immediately after the initial 5, prefixing with `[DELIVERABLE][IMPLIED]`.

    Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}
    """,
    tools=[],
    output_key="research_plan",
)

# --- Section Planner Agent ---
section_planner = LlmAgent(
    model=WORKER_MODEL,
    name="section_planner",
    description="Breaks down the research plan into a structured markdown outline of report sections.",
    instruction="""
    You are an expert report architect. Using the research plan from the 'research_plan' state key, design a logical structure for the final report.
    Note: Ignore all the tag names ([MODIFIED], [NEW], [RESEARCH], [DELIVERABLE]) in the research plan.
    Your task is to create a markdown outline with 4-6 distinct sections that cover the topic comprehensively without overlap.
    Do not include a "References" or "Sources" section in your outline. Citations will be handled in-line.
    """,
    output_key="report_sections",
)

# --- Section Researcher Agent ---
section_researcher = LlmAgent(
    model=WORKER_MODEL,
    name="section_researcher",
    description="Performs the crucial first pass of web research.",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="""
    You are a highly capable and diligent research and synthesis agent.
    Execute the research plan in `research_plan` state key with absolute fidelity.

    1. Gather information via `google_search` for every `[RESEARCH]` goal.
    2. Then produce artifacts for `[DELIVERABLE]` goals based only on gathered data.
    """,
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

# --- Research Evaluator Agent ---
research_evaluator = LlmAgent(
    model=WORKER_MODEL,
    name="research_evaluator",
    description="Critically evaluates research and generates follow-up queries.",
    instruction=f"""
    You are a meticulous quality assurance analyst evaluating the research findings in 'section_research_findings'.
    Be very critical about the QUALITY of research. If you find significant gaps, assign a grade of "fail",
    write a detailed comment about what's missing, and generate 5-7 specific follow-up queries.
    If the research thoroughly covers the topic, grade "pass".
    Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}
    Your response must be a single, raw JSON object validating against the 'Feedback' schema.
    """,
    output_schema=Feedback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_key="research_evaluation",
)

# --- Enhanced Search Executor Agent ---
enhanced_search_executor = LlmAgent(
    model=WORKER_MODEL,
    name="enhanced_search_executor",
    description="Executes follow-up searches and integrates new findings.",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="""
    You are a specialist researcher executing a refinement pass.
    1. Review the 'research_evaluation' state key to understand the feedback and required fixes.
    2. Execute EVERY query listed in 'follow_up_queries' using the 'google_search' tool.
    3. Synthesize the new findings and COMBINE them with the existing information in 'section_research_findings'.
    4. Your output MUST be the new, complete, and improved set of research findings.
    """,
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

# --- Report Composer Agent ---
report_composer = LlmAgent(
    model=WORKER_MODEL,
    name="report_composer_with_citations",
    include_contents="none",
    description="Transforms research data and a markdown outline into a final, cited report.",
    instruction="""
    Transform the provided data into a polished, professional, and meticulously cited research report.

    ---
    ### INPUT DATA
    *   Research Plan: `{research_plan}`
    *   Research Findings: `{section_research_findings}`
    *   Citation Sources: `{sources}`
    *   Report Structure: `{report_sections}`

    ---
    ### CRITICAL: Citation System
    To cite a source, you MUST insert a special citation tag directly after the claim it supports.
    **The only correct format is:** `<cite source="src-ID_NUMBER" />`

    Generate a comprehensive report using ONLY the `<cite source="src-ID_NUMBER" />` tag system for all citations.
    The final report must strictly follow the structure provided in the **Report Structure** markdown outline.
    Do not include a "References" or "Sources" section; all citations must be in-line.
    """,
    output_key="final_cited_report",
    after_agent_callback=citation_replacement_callback,
)

# --- Research Pipeline (Execution Phase) ---
research_pipeline = SequentialAgent(
    name="research_pipeline",
    description="Executes a pre-approved research plan. Performs iterative research, evaluation, and composes a final, cited report.",
    sub_agents=[
        section_planner,
        section_researcher,
        LoopAgent(
            name="iterative_refinement_loop",
            max_iterations=3,
            sub_agents=[
                research_evaluator,
                EscalationChecker(name="escalation_checker"),
                enhanced_search_executor,
            ],
        ),
        report_composer,
    ],
)
