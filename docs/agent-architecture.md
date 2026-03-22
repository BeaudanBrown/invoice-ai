# Agent Architecture

## User-Facing Model

The system exposes one primary conversational agent.

That agent is responsible for:

- understanding operator intent
- selecting the correct workflow
- invoking the right subagent/toolpack
- returning a coherent result back to the operator

## Delegated Subagents

The delegated subagents are not independent products. They are organized instruction packs and tool contracts behind the main agent.

### Intake Agent

Responsibilities:

- classify incoming files, links, text, and notes
- determine whether the input is for ingestion, retrieval, quote drafting, invoice drafting, or memory update
- route the request to the correct downstream toolset

### ERP Agent

Responsibilities:

- plan and execute ERPNext API interactions
- prefer native ERPNext document models and flows
- distinguish allowed writes from approval-gated actions

### Drafting Agent

Responsibilities:

- assemble quote or invoice drafts from ERP-backed context
- explain line-item choices
- produce structured intermediates and PDF-oriented outputs

### Memory Agent

Responsibilities:

- maintain natural-language memory files
- record operator instructions, client-specific exceptions, and job-specific preferences
- avoid duplicating structured ERP facts that already belong in ERPNext

### Review Agent

Responsibilities:

- generate structured summaries and diffs
- explain why a proposed ERP mutation or quote draft was produced
- present approval-relevant details in chat and artifact form

## Instruction Surface

A major deliverable of this repo will be markdown instruction scaffolding and skills for these delegated agents.

The system should be designed so that:

- each subagent has a narrow, explicit responsibility
- tool permissions are constrained by role
- ERP operations are centrally auditable
- prompt logic is organized in durable docs rather than buried in chat history
