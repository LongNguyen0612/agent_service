from typing import Dict, Any, List
from libs.result import Result, Error, Return


class InputSpecValidator:
    """Service for validating task input specifications"""

    def validate(self, input_spec: Dict[str, Any]) -> Result[bool]:
        """
        Validate input specification for a task

        Args:
            input_spec: JSON object containing task input specification

        Returns:
            Result[bool]: Success if valid, error with details if invalid
        """
        errors: List[str] = []

        # Check if input_spec is a dictionary
        if not isinstance(input_spec, dict):
            return Return.err(
                Error(
                    code="INVALID_INPUT_SPEC",
                    message="input_spec must be a JSON object (dictionary)",
                )
            )

        # Check if input_spec is not empty
        if len(input_spec) == 0:
            return Return.err(
                Error(
                    code="INVALID_INPUT_SPEC",
                    message="input_spec cannot be empty",
                )
            )

        # Validate data types for common fields (extensible)
        for key, value in input_spec.items():
            # Check that keys are non-empty strings
            if not isinstance(key, str) or len(key.strip()) == 0:
                errors.append(f"Invalid key: '{key}' - keys must be non-empty strings")
                continue

            # Basic type validation - allow common JSON types
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                errors.append(
                    f"Invalid value type for key '{key}': {type(value).__name__} - "
                    "must be one of: string, number, boolean, list, dict, null"
                )

        if errors:
            return Return.err(
                Error(
                    code="INVALID_INPUT_SPEC",
                    message="input_spec validation failed",
                    reason="; ".join(errors),
                )
            )

        return Return.ok(True)
