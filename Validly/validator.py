import json
import os
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import re

# ==============================================================================
# Custom Validator and Module Loading
# ==============================================================================
def _load_custom_validators(file_path: str) -> Dict[str, Callable]:
    """
    Safely loads a Python module from a given file path and returns its
    callable methods. This prevents the security risks associated with eval().
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Custom validator file not found at: {file_path}")

    spec = importlib.util.spec_from_file_location("custom_validators_module", file_path)
    if spec is None:
        raise ImportError(f"Could not load module specification from {file_path}")
        
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_validators_module"] = module
    spec.loader.exec_module(module)
    
    validators = {
        name: func for name, func in module.__dict__.items() if callable(func)
    }
    return validators

# ==============================================================================
# The Core json_difference Function and Helpers
# ==============================================================================

def json_difference(
    expected: Any,
    actual: Any,
    path: str = "",
    errors: Optional[List[Dict[str, Any]]] = None,
    options: Optional[Dict[str, Any]] = None,
    root_actual: Optional[Any] = None
) -> Dict[str, Union[bool, List[Dict[str, Any]]]]:
    """
    A powerful JSON validator that returns a structured dictionary of results.
    
    Args:
        expected (Any): The expected JSON object or value.
        actual (Any): The actual JSON object or value to compare.
        path (str): The current JSON path.
        errors (Optional[List[Dict[str, Any]]]): List to collect error dictionaries.
        options (Optional[Dict[str, Any]]): A dictionary of comparison options.
        root_actual (Optional[Any]): Reference to the original actual data for referencing.
    
    Returns:
        Dict[str, Union[bool, List[Dict[str, Any]]]]:
            - 'result': True if no errors, False otherwise.
            - 'errors': A list of error dictionaries.
    """
    if errors is None:
        errors = []
    if options is None:
        options = {}
    if root_actual is None:
        root_actual = actual

    if options.get("custom_validator_path") and not hasattr(json_difference, "_validators"):
        try:
            json_difference._validators = _load_custom_validators(options["custom_validator_path"])
        except Exception as e:
            errors.append({"field": None, "jsonpath": None, "message": f"Custom validator loading failed: {e}"})
            json_difference._validators = {}

    def _add_error(field: str, jsonpath: str, message: str):
        errors.append({"field": field, "jsonpath": jsonpath, "message": message})

    def get_leaf_key(current_path: str) -> str:
        if ']' in current_path:
            return current_path.split(']')[-1].strip('.')
        return current_path.split('.')[-1]

    def is_in_options(current_path: str, option_list: List[str]) -> bool:
        if not option_list:
            return False
        leaf_key = get_leaf_key(current_path)
        return any(
            opt == current_path or opt == leaf_key or current_path.endswith(f".{opt}")
            for opt in option_list
        )
    
    def is_in_numeric_options(current_path: str, option_dict: Dict[str, Any]) -> bool:
        if not option_dict:
            return False
        leaf_key = get_leaf_key(current_path)
        return any(
            opt == current_path or opt == leaf_key or current_path.endswith(f".{opt}")
            for opt in option_dict.keys()
        )

    def _is_numeric_valid(actual_value: Any, rule: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            actual_num = float(actual_value)
            expected_num = float(rule["value"])
            operator = rule["operator"]
            
            if operator == "gt":
                if actual_num > expected_num: return True, ""
                return False, f"Value is not greater than {expected_num}"
            if operator == "lt":
                if actual_num < expected_num: return True, ""
                return False, f"Value is not less than {expected_num}"
            if operator == "ge":
                if actual_num >= expected_num: return True, ""
                return False, f"Value is not greater than or equal to {expected_num}"
            if operator == "le":
                if actual_num <= expected_num: return True, ""
                return False, f"Value is not less than or equal to {expected_num}"
                
            return False, f"Invalid operator: {operator}"
        except (ValueError, TypeError):
            return False, "Value is not a valid number for comparison"

    def is_custom_validator(current_path: str) -> Optional[Callable]:
        validators = getattr(json_difference, "_validators", {})
        method_name = options.get("custom_validators", {}).get(current_path)
        if method_name:
            return validators.get(method_name)
        return None

    def _resolve_reference(expected_value: Any) -> Tuple[bool, Any]:
        if not isinstance(expected_value, str):
            return True, expected_value
        
        match = re.fullmatch(r"\{ACTUAL_VALUE:([a-zA-Z0-9_.-]+)\}", expected_value)
        if not match:
            return True, expected_value
        
        ref_path = match.group(1)
        
        try:
            current_ref_value = root_actual
            for part in ref_path.split('.'):
                if isinstance(current_ref_value, dict) and part in current_ref_value:
                    current_ref_value = current_ref_value[part]
                else:
                    return False, f"Reference path not found in actual data: {ref_path}"
            return True, current_ref_value
        except Exception:
            return False, f"Error resolving reference path: {ref_path}"

    def compare_dicts(expected_dict: Dict[str, Any], actual_dict: Dict[str, Any], current_path: str):
        all_keys = set(expected_dict.keys()).union(set(actual_dict.keys()))
        for key in sorted(list(all_keys)):
            key_path = f"{current_path}.{key}" if current_path else key
            field_name = get_leaf_key(key_path)
            is_skippable = is_in_options(key_path, options.get("skip_keys", []))
            should_validate = not is_skippable and (not options.get("validate_only_keys") or is_in_options(key_path, options.get("validate_only_keys", [])))
            if not should_validate: continue
            if key not in actual_dict:
                if is_in_options(key_path, options.get("presence_keys", [])): _add_error(field_name, key_path, f"Required key missing in actual: {key_path}")
                else: _add_error(field_name, key_path, f"Missing key in actual: {key_path}")
            elif key not in expected_dict: _add_error(field_name, key_path, f"Extra key in actual: {key_path}")
            else:
                if is_in_options(key_path, options.get("presence_keys", [])): continue
                custom_validator = is_custom_validator(key_path)
                if custom_validator:
                    try:
                        result, msg = custom_validator(expected_dict[key], actual_dict[key]);
                        if not result: _add_error(field_name, key_path, f"Custom validation failed: {msg}")
                    except Exception as e: _add_error(field_name, key_path, f"Custom validator raised an error: {e}")
                    continue
                json_difference(expected_dict[key], actual_dict[key], key_path, errors, options, root_actual)

    def compare_lists_symmetric(expected_list: List[Any], actual_list: List[Any], current_path: str):
        field_name = get_leaf_key(current_path)
        if len(expected_list) != len(actual_list):
            _add_error(field_name, current_path, f"List length mismatch: expected {len(expected_list)}, got {len(actual_list)}")
        min_len = min(len(expected_list), len(actual_list));
        for i in range(min_len):
            json_difference(expected_list[i], actual_list[i], f"{current_path}[{i}]", errors, options, root_actual)

    def compare_lists_unordered(expected_list: List[Any], actual_list: List[Any], current_path: str):
        field_name = get_leaf_key(current_path)
        if not all(isinstance(x, dict) for x in expected_list + actual_list):
            return compare_lists_symmetric(expected_list, actual_list, current_path)
        matching_keys = ["name", "id", "qId", "chanUid", "hubId"]
        match_key = None
        for key in matching_keys:
            if all(key in item for item in expected_list) and all(key in item for item in actual_list): match_key = key; break
        if match_key:
            expected_map = {item[match_key]: item for item in expected_list}
            actual_map = {item[match_key]: item for item in actual_list}
            all_keys = set(expected_map.keys()).union(set(actual_map.keys()))
            for item_key in sorted(list(all_keys)):
                item_path = f"{current_path}[{match_key}={item_key}]"
                item_field_name = get_leaf_key(item_path)
                if item_key in expected_map and item_key in actual_map: json_difference(expected_map[item_key], actual_map[item_key], item_path, errors, options, root_actual)
                elif item_key in expected_map: _add_error(item_field_name, item_path, f"Missing item in actual list at {item_path}")
                elif item_key in actual_map: _add_error(item_field_name, item_path, f"Extra item in actual list at {item_path}")
        else:
            if len(expected_list) != len(actual_list): _add_error(field_name, current_path, f"List length mismatch: expected {len(expected_list)}, got {len(actual_list)}")
            min_len = min(len(expected_list), len(actual_list));
            for i in range(min_len): json_difference(expected_list[i], actual_list[i], f"{current_path}[{i}]", errors, options, root_actual)

    if isinstance(expected, dict) and isinstance(actual, dict):
        compare_dicts(expected, actual, path)
    elif isinstance(expected, list) and isinstance(actual, list):
        list_type = options.get("list_validation_type", "unordered")
        if list_type == "symmetric":
            compare_lists_symmetric(expected, actual, path)
        else:
            compare_lists_unordered(expected, actual, path)
    elif not (isinstance(expected, (dict, list)) or isinstance(actual, (dict, list))):
        field_name = get_leaf_key(path)
        resolved, resolved_expected = _resolve_reference(expected)
        if not resolved: _add_error(field_name, path, f"Reference resolution failed: {resolved_expected}"); return {"result": False, "errors": errors}
        is_custom = is_custom_validator(path)
        if is_custom:
            try:
                result, msg = is_custom(resolved_expected, actual);
                if not result: _add_error(field_name, path, f"Custom validation failed: {msg}")
            except Exception as e: _add_error(field_name, path, f"Custom validator raised an error: {e}")
        elif is_in_options(path, options.get("wildcard_keys", [])): return {"result": True, "errors": errors}
        elif is_in_numeric_options(path, options.get("numeric_validations", {})):
            rule = options["numeric_validations"][path]; result, msg = _is_numeric_valid(actual, rule)
            if not result: _add_error(field_name, path, f"Numeric validation failed: {msg}")
        elif is_in_options(path, options.get("is_uuid_keys", [])):
            uuid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
            if not isinstance(actual, str) or not uuid_pattern.match(actual): _add_error(field_name, path, f"UUID format mismatch: expected valid UUID, got '{actual}'")
        elif is_in_options(path, options.get("is_base64_keys", [])):
            base64_pattern = re.compile(r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")
            if not isinstance(actual, str) or not base64_pattern.match(actual): _add_error(field_name, path, f"Base64 format mismatch: expected valid Base64 string, got '{actual}'")
        elif is_in_options(path, options.get("is_pan_keys", [])):
            pan_pattern = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
            if not isinstance(actual, str) or not pan_pattern.match(actual): _add_error(field_name, path, f"PAN format mismatch: expected valid PAN, got '{actual}'")
        elif is_in_options(path, options.get("is_aadhar_keys", [])):
            aadhar_pattern = re.compile(r"^[0-9]{4}[0-9]{4}[0-9]{4}$")
            if not isinstance(actual, str) or not aadhar_pattern.match(actual): _add_error(field_name, path, f"Aadhaar format mismatch: expected valid Aadhaar, got '{actual}'")
        elif options.get("regex_keys", {}).get(path) is not None:
            regex_pattern = options["regex_keys"][path]
            if not isinstance(actual, str) or not re.fullmatch(regex_pattern, actual): _add_error(field_name, path, f"Regex mismatch: expected pattern '{regex_pattern}', got '{actual}'")
        elif is_in_options(path, options.get("not_equal_keys", [])):
            if resolved_expected == actual: _add_error(field_name, path, f"Value should not be equal: value is '{resolved_expected}'")
        elif resolved_expected != actual: _add_error(field_name, path, f"Value mismatch: expected '{resolved_expected}', got '{actual}'")
            
    return {"result": len(errors) == 0, "errors": errors}