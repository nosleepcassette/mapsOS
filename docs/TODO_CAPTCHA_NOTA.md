# maps-os TODO: Intelligent Nota Parsing for Capture

## Status
Pending implementation

## Problem
When capture/vent parsing extracts action items, they need to be intelligently routed to nota. Current behavior: no automatic routing, risk of duplication.

## Requirements

### Deduplication
- Cross-reference extracted items against existing nota tasks
- Match on partial names, aliases, context (e.g., "respond to b" matches "respond to brennan")
- Don't create new tasks for items already tracked

### Smart Extraction
- Distinguish between new action items and updates to existing tasks
- Preserve priority indicators from capture text (!, !!, !!!!)
- Detect deadlines and due dates from natural language

### Context Awareness
- Route to appropriate scope (self, comms, house, work, readings)
- Link related tasks when capture mentions multiple connected items
- Flag high-pressure items (phone bill, critical deadlines) distinctly

## Implementation Notes
- Claude was originally supposed to implement this
- Needs integration with capture parser in `bin/maps`
- Consider adding `--dry-run` flag to preview extractions before committing

## Related
- See also: TODO_CAPTURE_FIDELITY.md (schema compression vs full fidelity)
