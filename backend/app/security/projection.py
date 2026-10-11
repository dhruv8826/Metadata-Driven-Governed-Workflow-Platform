from typing import Dict, Any, Tuple, List

class FieldProjector:
    @staticmethod
    def project_read_record(record_dict: Dict[str, Any], field_perms: Dict[str, Dict[str, bool]]) -> Dict[str, Any]:
        """
        Strips any field where read permission is False or omitted.
        Guarantees that unprivileged callers receive zero evidence of the hidden field.
        """
        raw_data = record_dict.get("data", {})
        projected_data = {}
        for field_name, value in raw_data.items():
            perm = field_perms.get(field_name, {})
            if perm.get("read", False) is True:
                projected_data[field_name] = value

        clean_record = record_dict.copy()
        clean_record["data"] = projected_data

        # If version history is attached, project each historical snapshot too!
        if "versions" in clean_record and isinstance(clean_record["versions"], list):
            clean_versions = []
            for v in clean_record["versions"]:
                v_copy = v.copy()
                v_data = v.get("data", {})
                v_copy["data"] = {k: val for k, val in v_data.items() if field_perms.get(k, {}).get("read", False) is True}
                clean_versions.append(v_copy)
            clean_record["versions"] = clean_versions

        return clean_record

    @staticmethod
    def validate_and_filter_write(
        input_data: Dict[str, Any],
        field_perms: Dict[str, Dict[str, bool]]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validates write payload against field edit permissions.
        Returns (sanitized_data, list_of_forbidden_fields).
        """
        sanitized = {}
        forbidden = []
        for field_name, value in input_data.items():
            perm = field_perms.get(field_name, {})
            if perm.get("edit", False) is True:
                sanitized[field_name] = value
            else:
                forbidden.append(field_name)

        return sanitized, forbidden

    @staticmethod
    def can_read_fields(field_names: List[str], field_perms: Dict[str, Dict[str, bool]]) -> bool:
        """
        Used by analytics / dashboard engine to ensure all fields participating in
        a metric calculation or grouping are fully readable by the persona.
        """
        for fn in field_names:
            if not fn:
                continue
            if not field_perms.get(fn, {}).get("read", False):
                return False
        return True
