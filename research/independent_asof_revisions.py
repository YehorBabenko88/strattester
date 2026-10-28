"""Independent arrival-time cutoff oracle for late revisions."""
def select_asof_revisions(rows, cutoff_ns):
    """rows: (event_id, revision, event_ns, available_ns, payload_digest)."""
    if type(cutoff_ns) is not int or cutoff_ns < 0:
        raise ValueError("invalid cutoff")
    selected={}
    seen=set()
    for event_id, revision, event_ns, available_ns, digest in rows:
        if (not isinstance(event_id,str) or not event_id
            or type(revision) is not int or revision < 0
            or any(type(t) is not int or t < 0 for t in (event_ns,available_ns))
            or event_ns > available_ns
            or not isinstance(digest,str) or len(digest)!=64
            or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError("invalid revision")
        key=(event_id,revision)
        if key in seen:
            raise ValueError("duplicate revision")
        seen.add(key)
        if available_ns > cutoff_ns:
            continue
        old=selected.get(event_id)
        if old is None or revision > old[0]:
            selected[event_id]=(revision,event_ns,available_ns,digest)
    return selected
