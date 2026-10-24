"""Independent event/ingest/availability ordering oracle."""
def validate_event_clock(rows, cutoff_ns):
    if type(cutoff_ns) is not int or cutoff_ns < 0 or not rows:
        raise ValueError("invalid cutoff or empty observations")
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid event")
        required=('event_id','event_ns','ingest_ns','available_ns')
        if any(k not in row for k in required):
            raise ValueError("missing event clock field")
        event_id=row['event_id']
        event,ingest,available=(row[k] for k in required[1:])
        if (not isinstance(event_id,str) or not event_id or event_id in seen
            or any(type(x) is not int or x < 0 for x in (event,ingest,available))
            or not event <= ingest <= available <= cutoff_ns):
            raise ValueError("duplicate, late or noncausal event")
        seen.add(event_id)
    return True
