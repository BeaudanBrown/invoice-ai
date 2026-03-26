# Operator UI

This document defines the first user-facing UI for `invoice-ai`.

## Product Goal

Let an operator take out their phone, speak or type a short request, and receive a usable quote or invoice artifact without interacting directly with the `ERPNext` UI.

Typical flow:

1. the operator opens an installable app on their phone
2. the operator speaks or types a request such as:
   - `Quote Acme for 3 hours onsite and travel`
   - `Turn that quote into an invoice`
   - `Make the labour 4 hours and separate travel clearly`
3. the UI sends plain text plus session context to the control plane
4. the control plane creates or revises the relevant draft in `ERPNext`
5. the UI shows:
   - a short natural-language summary
   - the current draft PDF
   - approvals if needed
   - ERP references and supporting files when useful

## Design Decisions

### 1. Chat-Style UI, Not A General Chatbot

The UI should feel like a very small chat app with operational result cards.

It is not intended to be:

- a full dashboard
- a general-purpose assistant
- a long-lived multi-thread conversation archive

The purpose of the chat metaphor is:

- fast input
- easy revision follow-up
- clear display of the current draft state

### 2. Voice Is First-Class Input, But Not Multimodal

Voice is an input method only.

The browser should:

- record speech
- transcribe it to text
- let the user review/edit the transcript if needed
- submit plain text to the backend

The backend should continue to accept text only.

The UI should not try to send raw audio to the current planner/orchestrator path.

The first implementation should use browser-native speech recognition where available.

Reason:

- it is the fastest path to a usable phone-first prototype
- it keeps the backend text-only
- it avoids adding another hosted dependency before the UI loop is proven

Known limitation:

- recognition quality and availability will vary by browser and platform
- a self-hosted STT path may still be needed later for consistency and offline/privacy guarantees

### 3. Session History Is Shallow

The UI should keep one active drafting session, not a durable multi-week chat archive.

The session should preserve:

- visible operator turns for the current page/app session
- active quote context
- active invoice context
- visible approvals and generated artifacts for the current session

The system should not depend on persistent chat history for business recovery.

Recovery should come from:

- `ERPNext` draft documents
- local revision metadata
- control-plane request/review/artifact records

### 4. Natural-Language Responses Are Presentation, Not Core Truth

The backend currently produces structured operator results. The UI should render those into short natural-language summaries.

For v1, the summary should be deterministic and template-driven, not model-generated.

Examples:

- `Created a draft quotation for Acme and generated a preview PDF.`
- `Updated the current quote and generated a new preview.`
- `I need approval before creating a new supplier record.`

This keeps the product usable without depending on a second conversational response model.

### 5. Artifacts Are First-Class Results

The main user-facing output is often a generated file, especially a PDF.

The UI should treat these as primary result objects:

- current quote preview PDF
- current invoice preview PDF
- review summary files
- structured exports when relevant

This implies a supporting backend requirement:

- the operator service needs stable artifact viewing and download endpoints

Filesystem paths alone are not an acceptable UI-facing contract.

### 6. Installable PWA Is The Right Delivery Shape

The first UI should be a small installable progressive web app.

Reasons:

- works on phone and desktop
- easy home-screen installation
- no native mobile app required
- fits the narrow chat-and-artifact workflow

The PWA should include:

- manifest
- service worker
- install metadata and icons

Offline operation is not the goal, but installability is.

### 7. Authentication Starts Simple

The first UI should reuse the existing bearer-token operator auth.

Reason:

- the service already supports it
- it is enough for initial local and NAS-hosted use
- it avoids delaying the PWA on account/session plumbing

Friendlier login/session UX can be layered on later without changing the first operator contract.

### 8. Artifact Handling Should Prefer Browser/System Viewers

Generated PDFs and review files do not need an elaborate in-app document viewer in v1.

The UI should:

- show the current artifact clearly
- offer open/preview and download actions
- allow the browser or system viewer to handle the actual file display

This keeps the PWA simple while still supporting the phone-first “say something, get a PDF” loop.

## Intended User Experience

## Main Screen

The UI should be one screen with four visible regions:

1. top bar
   - app name
   - connection status
   - current draft badge when present
2. conversation area
   - operator turns
   - assistant summary cards
   - review cards
   - artifact cards
3. pinned current result area
   - latest PDF preview or artifact
   - current quote or invoice label
4. composer
   - text input
   - microphone button
   - send button

## Conversation Model

The conversation pane should show only the current session by default.

The important state is:

- current active quote
- current active invoice
- latest generated artifact
- pending reviews

The UI should keep follow-up turns grounded in that active state so the operator does not need to repeat document ids.

## Voice Input Model

The voice interaction should be:

1. tap microphone
2. speak
3. stop recording
4. transcript appears in the input box
5. user may edit it
6. send as normal text

This avoids hidden transcription surprises and keeps the operator in control.

## Result Cards

Every backend response should be rendered into one or more cards.

### Summary Card

Contains:

- short summary sentence
- stage label
- timestamp

### Artifact Card

Contains:

- artifact kind
- preview button
- download button
- `make this the current draft` semantics when relevant

### Review Card

Contains:

- review summary
- why review is needed
- accept button when allowed
- reject button when allowed
- link to details/diff files

### ERP Reference Card

Contains:

- doctype
- name
- optional open-in-ERP link

## Current Session State

The frontend session store should keep:

- operator token
- request ids for the current visible session
- current active quote context
- current active invoice context
- latest visible artifact refs

This may live in:

- memory only for the first pass
- optionally browser session storage for refresh survival

It should not become a full durable chat-history database in v1.

## Supporting Backend Requirements

The current backend already supports:

- free-form operator turns through `planner.handle_turn`
- quote drafting and revision
- sales-invoice drafting and revision
- review queue inspection and action flows
- artifact persistence

The UI requires several additional backend/API capabilities.

### Required

1. artifact serving
   - view/download current PDFs and review files over HTTP
2. a session-friendly response envelope
   - easy extraction of:
     - summary
     - stage
     - current active quote/invoice
    - artifact refs
    - review refs
3. PWA static asset serving
   - HTML
   - JS/CSS
   - manifest
   - icons

Current implementation progress:

- `POST /api/ui/turn` now provides a UI-facing turn endpoint over `planner.handle_turn`
- `GET /api/artifacts/file/{relative_path}` now provides authenticated artifact viewing/download for files under the runtime state tree
- the UI response is now deterministic and presenter-backed rather than exposing raw tool payloads directly
- the FastAPI service now serves a first installable PWA shell with a current-session chat surface, token setup, review cards, and artifact open/download actions
- browser-native speech recognition is now the first implemented voice input path where the client platform exposes it

### Recommended

1. a UI-oriented response presenter layer
   - deterministic summaries from structured tool/orchestrator responses
2. an explicit current-artifact API
   - useful for restoring the latest draft preview after refresh
3. review detail/action endpoints suitable for UI cards

## UI Architecture

The recommended frontend architecture is deliberately small.

### Frontend

- one static web app served by the `invoice-ai` FastAPI service
- plain browser APIs for speech recognition when available
- minimal client-side state
- no external frontend backend-for-frontend layer

### Backend

- keep the existing planner/orchestrator stack as the execution path
- add presentation-friendly HTTP endpoints where needed
- do not add a second conversational backend just for the UI

## Delivery Phases

### Phase 1

- static single-page chat UI
- text input
- speech-to-text input
- current session history
- result cards
- artifact preview/download
- installable PWA shell

### Phase 2

- better session restoration after refresh
- richer review diff rendering
- better operator-facing summaries

### Deliberate Deferrals

- long-lived chat history across weeks
- multiple concurrent threads
- desktop-dashboard complexity
- raw audio upload to the planner
- image/audio multimodal prompting

## Open Questions

These decisions still need explicit user input before implementation:

1. speech-to-text provider
   - browser-native Web Speech API first
   - or a self-hosted/local STT path from day one
2. authentication UX
   - raw bearer token entry is fine for development
   - but the installable app should likely have a friendlier login/session mechanism
3. artifact preview behavior
   - inline PDF preview in the page
   - or open/download only

## Initial Recommendation

The first UI should be:

- a single-page installable PWA
- chat-style but tightly scoped
- voice-first with editable transcript
- powered by `planner.handle_turn`
- rendering deterministic summaries and artifact cards
- storing only current-session conversational state

That is enough to deliver the phone-first workflow without overbuilding a general chat product.
