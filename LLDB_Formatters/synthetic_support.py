def create_synthetic_child(container_valobj, child_name, child_address, child_value):
    """
    Tries to create a synthetic child with a stable index-style name.
    Falls back to the resolved child value when address-based creation is
    unavailable in the current LLDB environment.
    """
    if not child_value or not child_value.IsValid():
        return None

    create_value = getattr(container_valobj, "CreateValueFromAddress", None)
    if callable(create_value):
        try:
            synthetic_child = create_value(child_name, child_address, child_value.GetType())
            if synthetic_child and synthetic_child.IsValid():
                return synthetic_child
        except Exception:
            pass

    return child_value


def parse_synthetic_child_index(name):
    if not name:
        return -1

    token = name.strip()
    if token.startswith("[") and token.endswith("]"):
        token = token[1:-1]

    if not token.isdigit():
        return -1
    return int(token)
