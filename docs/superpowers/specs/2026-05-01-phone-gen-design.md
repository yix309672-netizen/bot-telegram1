# Phase 2 Design: Bot-to-Converter Integration

- Scope: Implement a structured integration path after the backup phase that calls converter_client.to_tdata, merges the resulting tdata with the backup, and sends the payload to the backend import endpoint. All actions are logged for auditability.
- Objective: Provide a clean, testable, and auditable off-ramp from backup data to backend import, without modifying core backend logic.

## 1) Architecture Overview
- Bot (local-deploy/bot-telegram/bot.py) triggers the post-backup orchestration.
- Converter service: /to-tdata endpoint accessed via converter_client.to_tdata(payload).
- Import endpoint: POST to /import-tdata on the backend (default http://localhost:8003/import-tdata).
- Logging: Persist an audit log at logs/tdata_response.json including payload, tdata, import response, and timestamps.

## 2) Data Flow
- Step 1: Backup completes and yields payload.
- Step 2: Call converter_client.to_tdata(payload) asynchronously to obtain tdata.
- Step 3: Create composite payload: { backup: payload, tdata: tdata }.
- Step 4: POST to IMPORT_ENDPOINT, capture response.
- Step 5: Write audit to logs/tdata_response.json.

## 3) Interfaces
- converter_client.to_tdata(payload) -> Dict[str, Any]
- post_import(composite_payload) -> Dict[str, Any]
- log_tdata_process(payload, tdata, imp_res) -> None

## 4) Error Handling & Reliability
- Timeouts, HTTP errors, and non-JSON responses from converter; import endpoint errors must be surfaced in structured error objects and logged.
- The orchestration should not crash backup flow; errors surface to caller for visibility while preserving backup artifact.

## 5) Testing Strategy
- Unit tests for to_tdata integration wrapper with mocked converter responses.
- Integration-like tests for failure modes: timeout, HTTP errors, invalid JSON, and successful end-to-end micro-flow when possible.

## 6) Rollback & Safeguards
- If import endpoint is unavailable or returns error, the system should log and flag the import result while keeping the backup artifact intact.

## 7) Acceptance Criteria (Patch 3)
- Patch 3 adds a structured integration path (converter call + import call) with logging.
- tdata_response.json exists and contains fields for payload, tdata, import result, and timestamps.
- The system gracefully handles timeouts and HTTP errors from both converter and import calls.

## 8) Follow-up
- Patch 4: Lock httpx version in requirements.
- Patch 5: Add unit tests for converter invocation and error scenarios.
- Patch 6: Document the design in this file and commit.
