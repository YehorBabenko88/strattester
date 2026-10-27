"""Pure mathematical point-in-time dependency closure oracle."""
def validate_dependency_closure(nodes, edges, cutoff_ns):
    if type(cutoff_ns) is not int or cutoff_ns < 0:
        raise ValueError("invalid cutoff")
    if not isinstance(nodes, dict) or not isinstance(edges, (tuple,list)):
        raise ValueError("invalid dependency graph")
    for name, available in nodes.items():
        if not isinstance(name,str) or not name or type(available) is not int or available < 0:
            raise ValueError("invalid dependency node")
    parents = {name: [] for name in nodes}
    for child, parent in edges:
        if child not in nodes or parent not in nodes:
            raise ValueError("unknown dependency")
        parents[child].append(parent)
    active = set()
    complete = {}
    def latest(node):
        if node in active:
            raise ValueError("cyclic dependency")
        if node in complete:
            return complete[node]
        active.add(node)
        timestamp = max([nodes[node]] + [latest(parent) for parent in parents[node]])
        active.remove(node)
        complete[node] = timestamp
        return timestamp
    result = {name: latest(name) for name in nodes}
    if any(t > cutoff_ns for t in result.values()):
        raise ValueError("future dependency")
    return result
