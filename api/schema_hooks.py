"""drf-spectacular postprocessing for the native API schema."""


def require_response_fields(result, generator, request, public):
    """Responses always include every field, but drf-spectacular only marks
    a field required when its serializer field is required -- so model
    fields with defaults (Workout.color, Exercise.reps_text...) came out
    optional and the app's generated types had to guess. Request bodies
    (``*Request`` components, split out by COMPONENT_SPLIT_REQUEST) keep
    their real optionality."""
    for name, schema in result.get("components", {}).get("schemas", {}).items():
        if name.endswith("Request") or "properties" not in schema:
            continue
        schema["required"] = sorted(set(schema.get("required", [])) | set(schema["properties"]))
    return result
