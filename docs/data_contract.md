# Data Contract (Draft)

This document describes the canonical fields expected in processed outputs. It's a living document;
the canonical mapping is defined in `src/schema/field_mappings.json`.

Minimal recommended canonical fields per record/table:
- `date`: ISO date representing the event/day
- `activity_id`: stable identifier for an activity
- `device_id`: identifier of the source device
- `user_id`: athlete identifier

Keep both raw and canonical column names during a transition period to preserve backward compatibility.
