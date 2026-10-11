import operator
from datetime import datetime, date
from typing import Dict, Any, List, Tuple

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda a, b: a in b if b else False,
    "not_in": lambda a, b: a not in b if b else True,
}

class RuleEvaluator:
    @staticmethod
    def evaluate(expression: Dict[str, Any], context_data: Dict[str, Any]) -> bool:
        """
        Evaluates declarative JSON rule expressions against context data:
        1. Simple rule: {"field": "amount", "operator": ">", "value": 5000}
        2. Cross-field: {"field": "scheduled_end", "operator": ">=", "field_compare": "scheduled_start"}
        3. Logical compound: {"and": [...]}, {"or": [...]}
        """
        if not expression:
            return True

        if "and" in expression:
            return all(RuleEvaluator.evaluate(sub, context_data) for sub in expression["and"])
        if "or" in expression:
            return any(RuleEvaluator.evaluate(sub, context_data) for sub in expression["or"])

        field = expression.get("field")
        op_str = expression.get("operator")
        op_func = OPERATORS.get(op_str)

        if not op_func:
            raise ValueError(f"Unsupported rule operator: '{op_str}'")

        left_val = context_data.get(field)

        if "field_compare" in expression:
            right_val = context_data.get(expression["field_compare"])
        else:
            right_val = expression.get("value")

        # Missing values handling
        if left_val is None or right_val is None:
            return False

        # Type normalization: date comparison
        if isinstance(left_val, str) and isinstance(right_val, str):
            try:
                # Try parsing as ISO dates if both look like YYYY-MM-DD
                d_left = date.fromisoformat(left_val)
                d_right = date.fromisoformat(right_val)
                return op_func(d_left, d_right)
            except (ValueError, TypeError):
                pass

        # Numeric conversions if one is number and other is string
        if isinstance(right_val, (int, float)) and isinstance(left_val, (str, int, float)):
            try:
                return op_func(float(left_val), float(right_val))
            except (ValueError, TypeError):
                pass

        try:
            return op_func(left_val, right_val)
        except Exception:
            return False

    @staticmethod
    def validate_record_rules(
        validation_rules: List[Dict[str, Any]],
        record_data: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluates all cross-field validation rules declared on an object.
        Returns list of validation error messages for failed rules.
        """
        errors = []
        for rule in validation_rules:
            expr = rule.get("expression", {})
            error_msg = rule.get("error_message", f"Validation rule '{rule.get('rule_name', 'custom')}' failed.")
            passed = RuleEvaluator.evaluate(expr, record_data)
            if not passed:
                errors.append(error_msg)
        return errors
