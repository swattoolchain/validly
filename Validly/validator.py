import json
import os
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
import re
from pathlib import Path

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


# ==============================================================================
# JSON Filtering Functions
# ==============================================================================

def _should_keep_value(key: str, value: Any, value_filters: Dict[str, Any]) -> bool:
    """
    Determines if a key-value pair should be kept based on value filters.
    
    Args:
        key (str): The key of the key-value pair.
        value (Any): The value to check.
        value_filters (Dict[str, Any]): Value-based filters to apply.
        
    Returns:
        bool: True if the key-value pair should be kept, False if it should be filtered out.
    """
    if not value_filters:
        return True
    
    # Check for null values
    if value_filters.get("null_values", False) and value is None:
        return False
    
    # Check for empty strings
    if value_filters.get("empty_strings", False) and value == "":
        return False
    
    # Check conditions
    conditions = value_filters.get("conditions", [])
    for condition in conditions:
        condition_key = condition.get("key", "*")
        operator = condition.get("operator")
        condition_value = condition.get("value")
        
        # Skip if this condition doesn't apply to this key
        if condition_key != "*" and condition_key != key:
            continue
            
        # Skip if we don't have a valid operator or value
        if not operator or condition_value is None:
            continue
        
        # Apply the condition based on the operator
        try:
            # Array operators
            if isinstance(value, list):
                if operator == "contains" and condition_value in value:
                    return False
                elif operator == "not_contains" and condition_value not in value:
                    return False
                elif operator == "empty" and len(value) == 0 and condition_value is True:
                    return False
                elif operator == "not_empty" and len(value) > 0 and condition_value is True:
                    return False
                elif operator == "length_eq" and len(value) == condition_value:
                    return False
                elif operator == "length_gt" and len(value) > condition_value:
                    return False
                elif operator == "length_lt" and len(value) < condition_value:
                    return False
                elif operator == "length_ge" and len(value) >= condition_value:
                    return False
                elif operator == "length_le" and len(value) <= condition_value:
                    return False
                # Skip other operators for arrays
                continue
                
            # Dictionary key check operators
            if isinstance(value, dict):
                if operator == "has_key" and condition_value in value:
                    return False
                elif operator == "not_has_key" and condition_value not in value:
                    return False
                elif operator == "empty" and len(value) == 0 and condition_value is True:
                    return False
                elif operator == "not_empty" and len(value) > 0 and condition_value is True:
                    return False
                elif operator == "keys_contain" and any(k.find(condition_value) >= 0 for k in value.keys()):
                    return False
                elif operator == "keys_not_contain" and not any(k.find(condition_value) >= 0 for k in value.keys()):
                    return False
                elif operator == "keys_count_eq" and len(value) == condition_value:
                    return False
                elif operator == "keys_count_gt" and len(value) > condition_value:
                    return False
                elif operator == "keys_count_lt" and len(value) < condition_value:
                    return False
                # Skip other operators for dictionaries
                continue
                
            # Only apply numeric comparisons to numeric values
            if not isinstance(value, (int, float)) and operator in ["gt", "lt", "ge", "le"]:
                continue
                
            # Standard operators for primitive types
            if operator == "eq" and value == condition_value:
                return False
            elif operator == "ne" and value != condition_value:
                return False
            elif operator == "gt" and value > condition_value:
                return False
            elif operator == "lt" and value < condition_value:
                return False
            elif operator == "ge" and value >= condition_value:
                return False
            elif operator == "le" and value <= condition_value:
                return False
            # String-specific operators
            elif isinstance(value, str):
                if operator == "contains" and condition_value in value:
                    return False
                elif operator == "not_contains" and condition_value not in value:
                    return False
                elif operator == "starts_with" and value.startswith(condition_value):
                    return False
                elif operator == "ends_with" and value.endswith(condition_value):
                    return False
                elif operator == "matches" and re.search(condition_value, value):
                    return False
                elif operator == "length_eq" and len(value) == condition_value:
                    return False
                elif operator == "length_gt" and len(value) > condition_value:
                    return False
                elif operator == "length_lt" and len(value) < condition_value:
                    return False
        except (TypeError, ValueError):
            # If comparison fails, we'll just continue
            pass
    
    # If we've made it this far, the value passes all filters
    return True

def jsonfilter(data: Any, options: Dict[str, Any]) -> Any:
    """
    Filters a JSON object based on specified options.
    
    Args:
        data (Any): The JSON data to filter (as a Python dict/list).
        options (Dict[str, Any]): Filtering options with the following possible keys:
            - jsonpath (List[str]): List of JSON paths to filter (supports wildcards).
            - regex (str or List[str]): Filter keys containing this text pattern.
            - keys (List[str]): List of exact keys to filter across any level in the JSON structure.
                When used with filter_type="include", only the specified keys will be kept at any level.
                When used with filter_type="exclude", the specified keys will be removed from all levels.
            - filter_type (str): Either "include" (default) or "exclude" to specify whether to include or exclude the matched paths.
            - value_filters (Dict[str, Any]): Value-based filters to apply. Supported filters include:
                - null_values (bool): If True, removes keys with null values.
                - empty_strings (bool): If True, removes keys with empty string values.
                - conditions (List[Dict]): List of conditions to filter values by. Each condition has:
                    - key (str): The key to match (can be a specific key or "*" for all keys).
                    - operator (str): One of "eq", "ne", "gt", "lt", "ge", "le".
                    - value (Any): The value to compare against.
    
    Returns:
        Any: The filtered JSON data.
    """
    if not options:
        return data
    
    # Set default filter_type to "include" if not specified
    if "filter_type" not in options:
        options["filter_type"] = "include"
    
    # Validate filter_type
    if options["filter_type"] not in ["include", "exclude"]:
        raise ValueError("filter_type must be either 'include' or 'exclude'")
    
    # Special handling for keys option with exclude filter_type
    keys_list = options.get("keys", [])
    if keys_list and options["filter_type"] == "exclude":
        # Use recursive approach to exclude keys at all levels
        # Pass value_filters if they exist
        value_filters = options.get("value_filters")
        return _recursive_exclude_keys(data, keys_list, value_filters)
    
    # Handle different data types
    if isinstance(data, dict):
        return _filter_dict(data, options, "")
    elif isinstance(data, list):
        return _filter_list(data, options, "")
    else:
        # Primitive types are returned as is
        return data


def _recursive_exclude_keys(data: Any, keys_to_exclude: List[str], value_filters: Dict[str, Any] = None) -> Any:
    """
    Recursively exclude keys from a JSON structure and apply value-based filtering.
    
    Args:
        data: The data to process
        keys_to_exclude: List of keys to exclude
        value_filters: Optional dictionary of value-based filters to apply
        
    Returns:
        The filtered data
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in keys_to_exclude:
                continue  # Skip this key
            
            # Apply value-based filtering if provided
            if value_filters and not _should_keep_value(key, value, value_filters):
                continue  # Skip based on value filters
            
            # Recursively process nested structures
            if isinstance(value, (dict, list)):
                filtered_value = _recursive_exclude_keys(value, keys_to_exclude, value_filters)
                result[key] = filtered_value
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        result = []
        for item in data:
            if isinstance(item, dict):
                # For dictionaries in a list, check each key-value pair against value filters
                skip_item = False
                if value_filters:
                    for key, value in item.items():
                        if not _should_keep_value(key, value, value_filters):
                            skip_item = True
                            break
                
                if not skip_item:
                    filtered_item = _recursive_exclude_keys(item, keys_to_exclude, value_filters)
                    if filtered_item:  # Only add non-empty items
                        result.append(filtered_item)
            elif isinstance(item, list):
                filtered_item = _recursive_exclude_keys(item, keys_to_exclude, value_filters)
                if filtered_item:  # Only add non-empty items
                    result.append(filtered_item)
            else:
                # For primitive values, we can't apply key-based value filters
                # since there's no key, so we just include them
                result.append(item)
        return result
    else:
        return data


def jsonfilter_file(file_path: str, options: Dict[str, Any]) -> Any:
    """
    Reads a JSON file and filters its content based on specified options.
    
    Args:
        file_path (str): Path to the JSON file.
        options (Dict[str, Any]): Filtering options with the following possible keys:
            - jsonpath (List[str]): List of JSON paths to include (supports wildcards).
            - regex (str): Include keys containing this text pattern.
    
    Returns:
        Any: The filtered JSON data.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found at: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return jsonfilter(data, options)


def _filter_dict(data: Dict[str, Any], options: Dict[str, Any], current_path: str) -> Dict[str, Any]:
    """
    Helper function to filter dictionary objects.
    """
    result = {}
    jsonpaths = options.get("jsonpath", [])
    regex_pattern = options.get("regex")
    keys_list = options.get("keys", [])
    filter_type = options.get("filter_type", "include")
    value_filters = options.get("value_filters", {})
    
    # If no filtering options provided, return the data as is
    if not jsonpaths and not regex_pattern and not keys_list and not value_filters:
        return data
    
    # If only value filters are provided and no path/key filters, we need to apply value filters
    # but keep the structure intact for keys that pass the filter
    only_value_filters = bool(value_filters) and not (jsonpaths or regex_pattern or keys_list)
    
    for key, value in data.items():
        # Build the current JSON path
        key_path = f"{current_path}.{key}" if current_path else key
        
        # Apply value-based filtering for primitive values
        value_filter_passed = _should_keep_value(key, value, value_filters)
        
        # If only using value filters and this is a primitive value that doesn't pass, skip it
        if only_value_filters and not isinstance(value, (dict, list)) and not value_filter_passed:
            continue
        
        # Check if this key or its children should be included/excluded
        path_matched = False
        
        # Check if key is in the keys list (exact match at any level)
        if keys_list and key in keys_list:
            path_matched = True
        
        # Check jsonpath patterns
        if not path_matched and jsonpaths:
            # Direct match with the current path
            if key_path in jsonpaths:
                path_matched = True
            
            # Check for wildcard matches
            for path in jsonpaths:
                # Exact path match
                if path == key_path:
                    path_matched = True
                    break
                
                # Wildcard match (e.g., "user.*" matches "user.name", "user.age", etc.)
                if path.endswith(".*"):
                    base_path = path[:-2]  # Remove the ".*"
                    if key_path == base_path or key_path.startswith(f"{base_path}."):
                        path_matched = True
                        break
                
                # Parent path match (include all children of a specified path)
                if path == current_path or (not current_path and path == ""):
                    path_matched = True
                    break
                
                # Include if this key is part of a path that should be included
                if key_path.startswith(f"{path}.") or path.startswith(f"{key_path}."):
                    path_matched = True
                    break
        
        # Check regex pattern(s)
        if not path_matched and regex_pattern:
            if isinstance(regex_pattern, list):
                # Handle list of regex patterns
                for pattern in regex_pattern:
                    if re.search(pattern, key):
                        path_matched = True
                        break
            else:
                # Handle single regex pattern
                if re.search(regex_pattern, key):
                    path_matched = True
        
        # Determine whether to include this key based on filter_type
        # If we're only using value filters, include_key is always True
        include_key = only_value_filters or (path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude")
        
        # Special handling for exclude with keys option
        if filter_type == "exclude" and keys_list and key in keys_list:
            # Skip this key entirely when it's in the exclude keys list
            continue
            
        if include_key:
            # For nested structures, recursively filter
            if isinstance(value, dict):
                filtered_dict = _filter_dict(value, options, key_path)
                if filtered_dict:  # Only add non-empty dictionaries
                    result[key] = filtered_dict
            elif isinstance(value, list):
                filtered_list = _filter_list(value, options, key_path)
                if filtered_list:  # Only add non-empty lists
                    result[key] = filtered_list
            else:
                # For primitive values, apply value filtering
                if value_filter_passed:
                    result[key] = value
        elif isinstance(value, dict):
            # Even if this key isn't included, check if any of its children should be
            filtered_dict = _filter_dict(value, options, key_path)
            if filtered_dict:  # Only add non-empty dictionaries
                result[key] = filtered_dict
        elif isinstance(value, list):
            # Even if this key isn't included, check if any of its children should be
            filtered_list = _filter_list(value, options, key_path)
            if filtered_list:  # Only add non-empty lists
                result[key] = filtered_list
    
    return result


def _filter_list(data: List[Any], options: Dict[str, Any], current_path: str) -> List[Any]:
    """
    Helper function to filter list objects.
    """
    # If no filtering options provided, return the list as is
    jsonpaths = options.get("jsonpath", [])
    regex_pattern = options.get("regex")
    keys_list = options.get("keys", [])
    filter_type = options.get("filter_type", "include")
    value_filters = options.get("value_filters", {})
    
    if not jsonpaths and not regex_pattern and not keys_list and not value_filters:
        return data
    
    # If only value filters are provided and no path/key filters, we need to apply value filters
    # but keep the structure intact for items that pass the filter
    only_value_filters = bool(value_filters) and not (jsonpaths or regex_pattern or keys_list)
    
    # Check if the entire list path is in the jsonpaths
    path_matched = current_path in jsonpaths
    
    # Check if parent path with wildcard includes this list
    if not path_matched:
        for path in jsonpaths:
            if path.endswith(".*"):
                base_path = path[:-2]  # Remove the ".*"
                if current_path == base_path or current_path.startswith(f"{base_path}."):
                    path_matched = True
                    break
    
    # If the entire list matches and we're in include mode, or it doesn't match and we're in exclude mode, return the whole list
    # But still apply value filters if they exist
    if ((path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude")) and not value_filters:
        return data
    
    result = []
    
    for i, item in enumerate(data):
        item_path = f"{current_path}[{i}]"
        
        # For dictionaries, we need to check if any of the keys should be excluded
        if isinstance(item, dict):
            # Apply value-based filtering for dictionary items only if we're only using value filters
            if only_value_filters:
                # We'll check each key-value pair in the dictionary
                skip_item = False
                for key, value in item.items():
                    if not _should_keep_value(key, value, value_filters):
                        skip_item = True
                        break
                        
                if skip_item:
                    continue
                
            # Special handling for exclude with keys option
            if filter_type == "exclude" and keys_list:
                # Check if any key in the dictionary is in the exclude keys list
                exclude_item = False
                for key in item.keys():
                    if key in keys_list:
                        exclude_item = True
                        break
                        
                if exclude_item:
                    # Skip this item if any key should be excluded
                    continue
                    
            filtered_item = _filter_dict(item, options, item_path)
            if filtered_item:  # Only add non-empty dictionaries
                result.append(filtered_item)
        elif isinstance(item, list):
            filtered_item = _filter_list(item, options, item_path)
            if filtered_item:  # Only add non-empty lists
                result.append(filtered_item)
        else:
            # For primitive types, check if the parent path is included
            # and also apply value-based filtering
            value_filter_passed = _should_keep_value(str(i), item, value_filters)
            
            # If only using value filters and this value doesn't pass, skip it
            if only_value_filters and not value_filter_passed:
                continue
                
            path_matched = False
            
            for path in jsonpaths:
                if path == current_path or current_path.startswith(f"{path}."):
                    path_matched = True
                    break
            
            # Check regex pattern(s) for the index (as a string)
            if regex_pattern:
                if isinstance(regex_pattern, list):
                    # Handle list of regex patterns
                    for pattern in regex_pattern:
                        if re.search(pattern, str(i)):
                            path_matched = True
                            break
                else:
                    # Handle single regex pattern
                    if re.search(regex_pattern, str(i)):
                        path_matched = True
            
            # Determine whether to include this item based on filter_type
            include_item = only_value_filters or (path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude")
            
            if include_item and value_filter_passed:
                result.append(item)
    
    return result


# ==============================================================================
# OpenAPI Schema Loading and Parsing Functions
# ==============================================================================

import json
import requests
from pathlib import Path
from urllib.parse import urlparse

def load_openapi_schema(source: str) -> Dict[str, Any]:
    """
    Load an OpenAPI schema from a file path or URL.
    
    Args:
        source (str): File path or URL to the OpenAPI schema.
    
    Returns:
        Dict[str, Any]: The loaded OpenAPI schema.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        requests.RequestException: If there's an error fetching the URL.
        json.JSONDecodeError: If the content is not valid JSON.
    """
    # Check if source is a URL
    parsed_url = urlparse(source)
    if parsed_url.scheme in ['http', 'https']:
        # Load from URL
        response = requests.get(source)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    else:
        # Load from file
        file_path = Path(source)
        if not file_path.exists():
            raise FileNotFoundError(f"OpenAPI schema file not found at: {source}")
        
        with open(file_path, 'r') as f:
            return json.load(f)


def parse_openapi_schema(schema: Dict[str, Any], resolve_refs: bool = True) -> Dict[str, Any]:
    """
    Parse an OpenAPI schema and convert it to a format that can be used with json_validate.
    
    Args:
        schema (Dict[str, Any]): The OpenAPI schema to parse.
        resolve_refs (bool): Whether to resolve $ref references in the schema.
    
    Returns:
        Dict[str, Any]: A contract schema that can be used with json_validate.
    """
    # Store the full schema for reference resolution
    if resolve_refs:
        parse_openapi_schema._full_schema = schema
    
    # Check if this is a complete OpenAPI spec or just a schema component
    if "openapi" in schema and "paths" in schema:
        # This is a complete OpenAPI spec, extract components/schemas
        if "components" in schema and "schemas" in schema["components"]:
            schemas = schema["components"]["schemas"]
        else:
            schemas = {}
            
        # Extract path schemas
        path_schemas = {}
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    operation_id = operation.get("operationId", f"{method}_{path}")
                    
                    # Extract request body schema
                    if "requestBody" in operation and "content" in operation["requestBody"]:
                        for content_type, content_schema in operation["requestBody"]["content"].items():
                            if "schema" in content_schema:
                                path_schemas[f"{operation_id}_request"] = content_schema["schema"]
                    
                    # Extract response schemas
                    if "responses" in operation:
                        for status_code, response in operation["responses"].items():
                            if "content" in response:
                                for content_type, content_schema in response["content"].items():
                                    if "schema" in content_schema:
                                        path_schemas[f"{operation_id}_response_{status_code}"] = content_schema["schema"]
        
        # Combine schemas
        schemas.update(path_schemas)
        return _convert_openapi_schemas_to_contract(schemas, resolve_refs)
    
    # This is just a schema component
    return _convert_openapi_schema_to_contract(schema, resolve_refs)


def _convert_openapi_schemas_to_contract(schemas: Dict[str, Any], resolve_refs: bool = True) -> Dict[str, Any]:
    """
    Convert multiple OpenAPI schemas to a contract schema.
    
    Args:
        schemas (Dict[str, Any]): Dictionary of OpenAPI schemas.
        resolve_refs (bool): Whether to resolve $ref references in the schema.
    
    Returns:
        Dict[str, Any]: A contract schema that can be used with json_validate.
    """
    # First pass: convert all schemas without resolving references
    contract = {}
    for name, schema in schemas.items():
        contract[name] = _convert_openapi_schema_to_contract(schema, False)
    
    # Second pass: resolve references if needed
    if resolve_refs:
        # Store the schemas for reference resolution
        _convert_openapi_schema_to_contract._schemas = schemas
        
        # Resolve references in all schemas
        for name, schema in contract.items():
            contract[name] = _resolve_references(schema, schemas)
    
    return contract


def _convert_openapi_schema_to_contract(schema: Dict[str, Any], resolve_refs: bool = True) -> Any:
    """
    Convert an OpenAPI schema to a contract schema.
    
    Args:
        schema (Dict[str, Any]): The OpenAPI schema to convert.
        resolve_refs (bool): Whether to resolve $ref references in the schema.
    
    Returns:
        Any: A contract schema that can be used with json_validate.
    """
    # Handle references
    if isinstance(schema, dict) and "$ref" in schema:
        ref_path = schema["$ref"]
        if resolve_refs:
            # Resolve the reference
            return _resolve_ref(ref_path, getattr(_convert_openapi_schema_to_contract, "_schemas", {}))
        else:
            # Just return a reference placeholder
            if ref_path.startswith("#/components/schemas/"):
                schema_name = ref_path.split("/")[-1]
                return {"$ref": schema_name}
            else:
                return {"$ref": ref_path}
    
    # Handle different types
    if not isinstance(schema, dict):
        return schema
    
    schema_type = schema.get("type")
    
    if schema_type == "object":
        result = {}
        for prop_name, prop_schema in schema.get("properties", {}).items():
            result[prop_name] = _convert_openapi_schema_to_contract(prop_schema, resolve_refs)
        return result
    
    elif schema_type == "array":
        items_schema = schema.get("items", {})
        return [_convert_openapi_schema_to_contract(items_schema, resolve_refs)]
    
    elif schema_type == "string":
        return ""
    
    elif schema_type == "integer" or schema_type == "number":
        return 0
    
    elif schema_type == "boolean":
        return False
    
    elif schema_type == "null":
        return None
    
    # Handle oneOf, anyOf, allOf
    if "oneOf" in schema:
        # Use the first schema as a representative
        return _convert_openapi_schema_to_contract(schema["oneOf"][0], resolve_refs)
    
    if "anyOf" in schema:
        # Use the first schema as a representative
        return _convert_openapi_schema_to_contract(schema["anyOf"][0], resolve_refs)
    
    if "allOf" in schema:
        # Merge all schemas
        result = {}
        for sub_schema in schema["allOf"]:
            sub_result = _convert_openapi_schema_to_contract(sub_schema, resolve_refs)
            if isinstance(sub_result, dict):
                result.update(sub_result)
        return result
    
    # Default
    return {}


def _resolve_references(schema: Any, schemas: Dict[str, Any]) -> Any:
    """
    Resolve all references in a schema.
    
    Args:
        schema (Any): The schema to resolve references in.
        schemas (Dict[str, Any]): Dictionary of all available schemas.
    
    Returns:
        Any: The schema with all references resolved.
    """
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_name = schema["$ref"]
            if ref_name in schemas:
                # Resolve the reference
                resolved = _convert_openapi_schema_to_contract(schemas[ref_name], False)
                # Recursively resolve any nested references
                return _resolve_references(resolved, schemas)
            else:
                # Reference not found, return as is
                return schema
        else:
            # Recursively resolve references in all properties
            result = {}
            for key, value in schema.items():
                result[key] = _resolve_references(value, schemas)
            return result
    elif isinstance(schema, list):
        # Recursively resolve references in all items
        return [_resolve_references(item, schemas) for item in schema]
    else:
        # Primitive value, return as is
        return schema


def _resolve_ref(ref_path: str, schemas: Dict[str, Any]) -> Any:
    """
    Resolve a reference path to its schema.
    
    Args:
        ref_path (str): The reference path to resolve.
        schemas (Dict[str, Any]): Dictionary of all available schemas.
    
    Returns:
        Any: The resolved schema.
    """
    if ref_path.startswith("#/components/schemas/"):
        schema_name = ref_path.split("/")[-1]
        if schema_name in schemas:
            return _convert_openapi_schema_to_contract(schemas[schema_name], True)
    
    # Reference not found or not supported
    return {"$ref": ref_path}


def _extract_openapi_validations(schema: Dict[str, Any], path: str = "") -> Dict[str, Any]:
    """
    Extract validation rules from an OpenAPI schema.
    
    Args:
        schema (Dict[str, Any]): The OpenAPI schema to extract validations from.
        path (str): The current JSON path.
    
    Returns:
        Dict[str, Any]: Validation options that can be used with json_validate.
    """
    validations = {
        "type_validations": {},
        "required_keys": [],
        "regex_keys": {},
        "numeric_validations": {}
    }
    
    # Handle references
    if "$ref" in schema:
        return validations
    
    # Extract type validations
    schema_type = schema.get("type")
    if schema_type and path:
        type_map = {
            "string": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
            "array": "array",
            "object": "object"
        }
        validations["type_validations"][path] = type_map.get(schema_type, "any")
    
    # Extract format validations
    schema_format = schema.get("format")
    if schema_format and path:
        if schema_format == "uuid":
            validations.setdefault("is_uuid_keys", []).append(path)
        elif schema_format == "email":
            validations["regex_keys"][path] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        elif schema_format == "uri":
            validations["regex_keys"][path] = r"^(https?|ftp)://[^\s/$.?#].[^\s]*$"
        elif schema_format == "date":
            validations["regex_keys"][path] = r"^\d{4}-\d{2}-\d{2}$"
        elif schema_format == "date-time":
            validations["regex_keys"][path] = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
    
    # Extract required keys
    if schema_type == "object" and "required" in schema:
        for prop_name in schema["required"]:
            prop_path = f"{path}.{prop_name}" if path else prop_name
            validations["required_keys"].append(prop_path)
    
    # Extract numeric validations
    if schema_type in ["integer", "number"] and path:
        if "minimum" in schema:
            validations["numeric_validations"][path] = {"operator": "ge", "value": schema["minimum"]}
        elif "exclusiveMinimum" in schema:
            validations["numeric_validations"][path] = {"operator": "gt", "value": schema["exclusiveMinimum"]}
        
        if "maximum" in schema:
            validations["numeric_validations"][path] = {"operator": "le", "value": schema["maximum"]}
        elif "exclusiveMaximum" in schema:
            validations["numeric_validations"][path] = {"operator": "lt", "value": schema["exclusiveMaximum"]}
    
    # Extract string validations
    if schema_type == "string" and path:
        if "pattern" in schema:
            validations["regex_keys"][path] = schema["pattern"]
        
        if "minLength" in schema:
            # We'll handle this with a custom validator
            pass
        
        if "maxLength" in schema:
            # We'll handle this with a custom validator
            pass
    
    # Extract array validations
    if schema_type == "array" and path:
        if "minItems" in schema:
            # We'll handle this with a custom validator
            pass
        
        if "maxItems" in schema:
            # We'll handle this with a custom validator
            pass
        
        if "uniqueItems" in schema and schema["uniqueItems"]:
            # We'll handle this with a custom validator
            pass
    
    # Recursively extract validations from nested schemas
    if schema_type == "object" and "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            prop_path = f"{path}.{prop_name}" if path else prop_name
            nested_validations = _extract_openapi_validations(prop_schema, prop_path)
            
            # Merge validations
            for key, value in nested_validations.items():
                if isinstance(value, dict):
                    validations.setdefault(key, {}).update(value)
                elif isinstance(value, list):
                    validations.setdefault(key, []).extend(value)
    
    if schema_type == "array" and "items" in schema:
        items_schema = schema["items"]
        # For arrays, we can't easily validate individual items without knowing their indices
        # So we'll just extract validations for the array type itself
    
    return validations


def validate_openapi(data: Any, schema: Union[Dict[str, Any], str], options: Optional[Dict[str, Any]] = None) -> Dict[str, Union[bool, List[Dict[str, Any]]]]:
    """
    Validate data against an OpenAPI schema.
    
    Args:
        data (Any): The data to validate.
        schema (Union[Dict[str, Any], str]): The OpenAPI schema to validate against.
            This can be a dictionary containing the schema, a file path, or a URL.
        options (Optional[Dict[str, Any]]): Additional validation options.
    
    Returns:
        Dict[str, Union[bool, List[Dict[str, Any]]]]: Validation results.
    """
    # Load schema if it's a file path or URL
    if isinstance(schema, str):
        schema = load_openapi_schema(schema)
    
    # Convert OpenAPI schema to contract
    contract = parse_openapi_schema(schema)
    
    # Extract validations from OpenAPI schema
    schema_validations = _extract_openapi_validations(schema)
    
    # Merge with user-provided options
    merged_options = schema_validations.copy()
    if options:
        for key, value in options.items():
            if isinstance(value, dict):
                merged_options.setdefault(key, {}).update(value)
            elif isinstance(value, list):
                merged_options.setdefault(key, []).extend(value)
            else:
                merged_options[key] = value
    
    # Validate using json_validate
    return json_validate(data, contract, merged_options)


def validate_openapi_file(data: Any, schema_file: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Union[bool, List[Dict[str, Any]]]]:
    """
    Validate data against an OpenAPI schema loaded from a file.
    
    Args:
        data (Any): The data to validate.
        schema_file (str): Path to the OpenAPI schema file.
        options (Optional[Dict[str, Any]]): Additional validation options.
    
    Returns:
        Dict[str, Union[bool, List[Dict[str, Any]]]]: Validation results.
    """
    return validate_openapi(data, schema_file, options)


def validate_openapi_url(data: Any, schema_url: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Union[bool, List[Dict[str, Any]]]]:
    """
    Validate data against an OpenAPI schema loaded from a URL.
    
    Args:
        data (Any): The data to validate.
        schema_url (str): URL to the OpenAPI schema.
        options (Optional[Dict[str, Any]]): Additional validation options.
    
    Returns:
        Dict[str, Union[bool, List[Dict[str, Any]]]]: Validation results.
    """
    return validate_openapi(data, schema_url, options)


# ==============================================================================
# JSON Validation Function
# ==============================================================================

def json_validate(data: Any, contract: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Union[bool, List[Dict[str, Any]]]]:
    """
    Validates a single JSON object against an API contract.
    
    Args:
        data (Any): The JSON data to validate (as a Python dict/list).
        contract (Dict[str, Any]): The contract schema to validate against.
        options (Optional[Dict[str, Any]]): Validation options with the following possible keys:
            - custom_validators (Dict[str, str]): A dictionary mapping JSON paths to custom validator function names.
            - custom_validator_path (str): Path to a Python file with custom validator functions.
            - wildcard_keys (List[str]): List of keys where exact value matching is not required.
            - numeric_validations (Dict[str, Dict]): Dictionary of numeric validation rules.
            - is_uuid_keys (List[str]): List of keys that should contain valid UUIDs.
            - is_pan_keys (List[str]): List of keys that should contain valid PAN numbers.
            - is_aadhar_keys (List[str]): List of keys that should contain valid Aadhaar numbers.
            - regex_keys (Dict[str, str]): Dictionary mapping keys to regex patterns they should match.
            - required_keys (List[str]): List of keys that must be present in the data.
            - type_validations (Dict[str, str]): Dictionary mapping keys to expected types.
    
    Returns:
        Dict[str, Union[bool, List[Dict[str, Any]]]]:
            - 'result': True if validation passes, False otherwise.
            - 'errors': A list of error dictionaries.
    """
    if options is None:
        options = {}
    
    errors = []
    
    # Load custom validators if specified
    if options.get("custom_validator_path") and not hasattr(json_validate, "_validators"):
        try:
            json_validate._validators = _load_custom_validators(options["custom_validator_path"])
        except Exception as e:
            errors.append({"field": None, "jsonpath": None, "message": f"Custom validator loading failed: {e}"})
            json_validate._validators = {}
    
    # Helper function to add validation errors
    def _add_error(field: str, jsonpath: str, message: str):
        errors.append({"field": field, "jsonpath": jsonpath, "message": message})
    
    # Helper function to get the leaf key from a path
    def get_leaf_key(current_path: str) -> str:
        if ']' in current_path:
            return current_path.split(']')[-1].strip('.')
        return current_path.split('.')[-1]
    
    # Helper function to check if a path is in a list of option paths
    def is_in_options(current_path: str, option_list: List[str]) -> bool:
        if not option_list:
            return False
        leaf_key = get_leaf_key(current_path)
        return any(
            opt == current_path or opt == leaf_key or current_path.endswith(f".{opt}")
            for opt in option_list
        )
    
    # Helper function to validate a field against the contract
    def validate_field(data_value: Any, contract_value: Any, path: str):
        field_name = get_leaf_key(path)
        
        # Check if this field has a custom validator
        custom_validator = None
        if options.get("custom_validators", {}).get(path):
            method_name = options["custom_validators"][path]
            validators = getattr(json_validate, "_validators", {})
            custom_validator = validators.get(method_name)
        
        # If there's a custom validator, use it
        if custom_validator:
            try:
                result, msg = custom_validator(contract_value, data_value)
                if not result:
                    _add_error(field_name, path, f"Custom validation failed: {msg}")
                return
            except Exception as e:
                _add_error(field_name, path, f"Custom validator raised an error: {e}")
                return
        
        # Check type validation
        if options.get("type_validations", {}).get(path):
            expected_type = options["type_validations"][path]
            
            # Handle special case for integers vs floats
            if expected_type == "number":
                if not isinstance(data_value, (int, float)):
                    _add_error(field_name, path, f"Type mismatch: expected number, got {type(data_value).__name__}")
            # Handle special case for strings
            elif expected_type == "string":
                if not isinstance(data_value, str):
                    _add_error(field_name, path, f"Type mismatch: expected string, got {type(data_value).__name__}")
            # Handle special case for booleans
            elif expected_type == "boolean":
                if not isinstance(data_value, bool):
                    _add_error(field_name, path, f"Type mismatch: expected boolean, got {type(data_value).__name__}")
            # Handle special case for arrays
            elif expected_type == "array":
                if not isinstance(data_value, list):
                    _add_error(field_name, path, f"Type mismatch: expected array, got {type(data_value).__name__}")
            # Handle special case for objects
            elif expected_type == "object":
                if not isinstance(data_value, dict):
                    _add_error(field_name, path, f"Type mismatch: expected object, got {type(data_value).__name__}")
            # Handle general case
            elif expected_type != "any":
                type_map = {
                    "str": "string",
                    "int": "number",
                    "float": "number",
                    "bool": "boolean",
                    "list": "array",
                    "dict": "object"
                }
                actual_type = type(data_value).__name__
                mapped_type = type_map.get(actual_type, actual_type)
                if mapped_type != expected_type:
                    _add_error(field_name, path, f"Type mismatch: expected {expected_type}, got {mapped_type}")
        
        # Check if this is a wildcard key (value doesn't matter)
        if is_in_options(path, options.get("wildcard_keys", [])):
            return
        
        # Check UUID format
        if is_in_options(path, options.get("is_uuid_keys", [])):
            uuid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
            if not isinstance(data_value, str) or not uuid_pattern.match(data_value):
                _add_error(field_name, path, f"UUID format mismatch: expected valid UUID, got '{data_value}'")
            return
        
        # Check PAN format
        if is_in_options(path, options.get("is_pan_keys", [])):
            pan_pattern = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
            if not isinstance(data_value, str) or not pan_pattern.match(data_value):
                _add_error(field_name, path, f"PAN format mismatch: expected valid PAN, got '{data_value}'")
            return
        
        # Check Aadhaar format
        if is_in_options(path, options.get("is_aadhar_keys", [])):
            aadhar_pattern = re.compile(r"^[0-9]{4}[0-9]{4}[0-9]{4}$")
            if not isinstance(data_value, str) or not aadhar_pattern.match(data_value):
                _add_error(field_name, path, f"Aadhaar format mismatch: expected valid Aadhaar, got '{data_value}'")
            return
        
        # Check regex pattern
        if options.get("regex_keys", {}).get(path):
            regex_pattern = options["regex_keys"][path]
            if not isinstance(data_value, str) or not re.fullmatch(regex_pattern, data_value):
                _add_error(field_name, path, f"Regex mismatch: expected pattern '{regex_pattern}', got '{data_value}'")
            return
        
        # Check enum validations
        if options.get("enum_validations", {}).get(path):
            allowed_values = options["enum_validations"][path]
            if data_value not in allowed_values:
                _add_error(field_name, path, f"Enum validation failed: Value '{data_value}' is not in allowed values: {allowed_values}")
            return
            
        # Check numeric validations
        if options.get("numeric_validations", {}).get(path):
            rule = options["numeric_validations"][path]
            try:
                actual_num = float(data_value)
                expected_num = float(rule["value"])
                operator = rule["operator"]
                
                if operator == "gt" and not (actual_num > expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is not greater than {expected_num}")
                elif operator == "lt" and not (actual_num < expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is not less than {expected_num}")
                elif operator == "ge" and not (actual_num >= expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is not greater than or equal to {expected_num}")
                elif operator == "le" and not (actual_num <= expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is not less than or equal to {expected_num}")
                elif operator == "eq" and not (actual_num == expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is not equal to {expected_num}")
                elif operator == "ne" and not (actual_num != expected_num):
                    _add_error(field_name, path, f"Numeric validation failed: Value is equal to {expected_num}")
            except (ValueError, TypeError):
                _add_error(field_name, path, f"Numeric validation failed: Value '{data_value}' is not a valid number")
            return
    
    # Helper function to validate a dictionary against the contract
    def validate_dict(data_dict: Dict[str, Any], contract_dict: Dict[str, Any], current_path: str):
        # Check required keys
        for key, value in contract_dict.items():
            key_path = f"{current_path}.{key}" if current_path else key
            
            # Check if key is required and missing
            if key not in data_dict:
                if is_in_options(key_path, options.get("required_keys", [])):
                    _add_error(key, key_path, f"Required key missing: {key_path}")
                continue
            
            # Validate nested structures
            if isinstance(value, dict) and isinstance(data_dict[key], dict):
                validate_dict(data_dict[key], value, key_path)
            elif isinstance(value, list) and isinstance(data_dict[key], list):
                validate_list(data_dict[key], value, key_path)
            else:
                validate_field(data_dict[key], value, key_path)
        
        # Check for extra keys if strict mode is enabled
        if options.get("strict_mode", False):
            for key in data_dict:
                if key not in contract_dict:
                    key_path = f"{current_path}.{key}" if current_path else key
                    _add_error(key, key_path, f"Extra key not in contract: {key_path}")
    
    # Helper function to validate a list against the contract
    def validate_list(data_list: List[Any], contract_list: List[Any], current_path: str):
        # If contract list is empty, we can't validate the items
        if not contract_list:
            return
        
        # Get the first item in the contract list as the template
        template_item = contract_list[0]
        
        # Validate each item in the data list against the template
        for i, item in enumerate(data_list):
            item_path = f"{current_path}[{i}]"
            
            if isinstance(template_item, dict) and isinstance(item, dict):
                validate_dict(item, template_item, item_path)
            elif isinstance(template_item, list) and isinstance(item, list):
                validate_list(item, template_item, item_path)
            else:
                validate_field(item, template_item, item_path)
    
    # Start validation based on the root types
    if isinstance(data, dict) and isinstance(contract, dict):
        validate_dict(data, contract, "")
    elif isinstance(data, list) and isinstance(contract, list):
        validate_list(data, contract, "")
    else:
        validate_field(data, contract, "")
    
    return {"result": len(errors) == 0, "errors": errors}


# ==============================================================================
# JSON Transform Functions
# ==============================================================================

def json_transform(data: Any, options: Dict[str, Any]) -> Any:
    """
    Transforms a JSON object based on specified options.
    
    Args:
        data (Any): The JSON data to transform (as a Python dict/list).
        options (Dict[str, Any]): Transformation options with the following possible keys:
            - transforms (Dict[str, Dict]): A dictionary mapping JSON paths to transformation options.
                Each transformation option can have:
                - method (str): The name of the transformation method to apply.
                - args (Dict): Additional arguments for the transformation method.
            - custom_transform_path (str): Path to a Python file with custom transformation functions.
            - add_fields (Dict[str, Dict]): A dictionary mapping new field paths to their values and parent paths.
                Each add_field option should have:
                - value (Any): The value to set for the new field.
                - parent (str): The parent path where the new field should be added.
    
    Returns:
        Any: The transformed JSON data.
    """
    if not options:
        return data
    
    # Load custom transformers if specified
    if options.get("custom_transform_path") and not hasattr(json_transform, "_transformers"):
        try:
            json_transform._transformers = _load_custom_transformers(options["custom_transform_path"])
        except Exception as e:
            raise ValueError(f"Failed to load custom transformers: {e}")
    
    # Handle different data types
    if isinstance(data, dict):
        return _transform_dict(data, options, "", data)
    elif isinstance(data, list):
        return _transform_list(data, options, "", data)
    else:
        # Primitive types are returned as is unless specifically targeted
        return _apply_transform(data, "", options, data)


def json_transform_file(file_path: str, options: Dict[str, Any]) -> Any:
    """
    Reads a JSON file and transforms its content based on specified options.
    
    Args:
        file_path (str): Path to the JSON file.
        options (Dict[str, Any]): Transformation options with the following possible keys:
            - transforms (Dict[str, Dict]): A dictionary mapping JSON paths to transformation options.
            - custom_transform_path (str): Path to a Python file with custom transformation functions.
            - add_fields (Dict[str, Dict]): A dictionary mapping new field paths to their values and parent paths.
    
    Returns:
        Any: The transformed JSON data.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found at: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return json_transform(data, options)


def _load_custom_transformers(file_path: str) -> Dict[str, Callable]:
    """
    Safely loads a Python module from a given file path and returns its
    callable methods for transformations.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Custom transformer file not found at: {file_path}")

    spec = importlib.util.spec_from_file_location("custom_transformers_module", file_path)
    if spec is None:
        raise ImportError(f"Could not load module specification from {file_path}")
        
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_transformers_module"] = module
    spec.loader.exec_module(module)
    
    transformers = {
        name: func for name, func in module.__dict__.items() if callable(func)
    }
    return transformers


def _transform_dict(data: Dict[str, Any], options: Dict[str, Any], current_path: str, root_data: Any) -> Dict[str, Any]:
    """
    Helper function to transform dictionary objects.
    """
    result = {}
    transforms = options.get("transforms", {})
    add_fields = options.get("add_fields", {})
    
    # First, apply transformations to existing fields
    for key, value in data.items():
        # Build the current JSON path
        key_path = f"{current_path}.{key}" if current_path else key
        
        # Apply transformations to this field if specified
        transformed_value = _apply_transform(value, key_path, options, root_data)
        
        # For nested structures, recursively transform
        if isinstance(transformed_value, dict):
            result[key] = _transform_dict(transformed_value, options, key_path, root_data)
        elif isinstance(transformed_value, list):
            result[key] = _transform_list(transformed_value, options, key_path, root_data)
        else:
            result[key] = transformed_value
    
    # Then, add new fields if this is the parent path for any add_fields
    for field_path, field_info in add_fields.items():
        parent_path = field_info.get("parent", "")
        if parent_path == current_path:
            field_name = field_path.split(".")[-1] if "." in field_path else field_path
            result[field_name] = field_info.get("value")
    
    return result


def _transform_list(data: List[Any], options: Dict[str, Any], current_path: str, root_data: Any) -> List[Any]:
    """
    Helper function to transform list objects.
    """
    result = []
    
    for i, item in enumerate(data):
        item_path = f"{current_path}[{i}]"
        
        # Apply transformations to this item if specified
        transformed_item = _apply_transform(item, item_path, options, root_data)
        
        if isinstance(transformed_item, dict):
            result.append(_transform_dict(transformed_item, options, item_path, root_data))
        elif isinstance(transformed_item, list):
            result.append(_transform_list(transformed_item, options, item_path, root_data))
        else:
            result.append(transformed_item)
    
    return result


def _apply_transform(value: Any, path: str, options: Dict[str, Any], root_data: Any) -> Any:
    """
    Apply transformation to a value if specified in the options.
    """
    transforms = options.get("transforms", {})
    
    # Check if there's a transformation for this path
    if path in transforms:
        transform_info = transforms[path]
        method_name = transform_info.get("method")
        args = transform_info.get("args", {})
        
        # Built-in transformers
        if method_name == "to_string":
            return str(value)
        elif method_name == "to_int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        elif method_name == "to_float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif method_name == "to_bool":
            return bool(value)
        elif method_name == "format":
            format_str = args.get("format", "{}")
            try:
                return format_str.format(value)
            except Exception:
                return value
        elif method_name == "default":
            default_value = args.get("value")
            return default_value if value is None else value
        elif method_name == "multiply":
            factor = args.get("factor", 1)
            try:
                return value * factor
            except (TypeError, ValueError):
                return value
        elif method_name == "add":
            amount = args.get("amount", 0)
            try:
                return value + amount
            except (TypeError, ValueError):
                return value
        elif method_name == "replace":
            old = args.get("old", "")
            new = args.get("new", "")
            if isinstance(value, str):
                return value.replace(old, new)
            return value
        # Custom transformers
        elif hasattr(json_transform, "_transformers") and method_name in json_transform._transformers:
            try:
                return json_transform._transformers[method_name](value, args, root_data)
            except Exception as e:
                raise ValueError(f"Error applying custom transformer '{method_name}': {e}")
    
    return value


# ==============================================================================
# JSON Extend Functions
# ==============================================================================

def json_extend(data: Any, key: Union[str, Dict[str, Any]], value: Any = None, jsonpath: str = "") -> Any:
    """
    Adds key-value pair(s) to a JSON object at the specified jsonpath.
    
    Args:
        data (Any): The JSON data to extend (as a Python dict/list).
        key (Union[str, Dict[str, Any]]): The key to add, or a dictionary of key-value pairs to add.
        value (Any, optional): The value to add for the key. Not used if key is a dictionary.
        jsonpath (str, optional): The JSON path where the key(s) should be added. 
                                 If empty, the key(s) are added to the root level.
    
    Returns:
        Any: The extended JSON data.
    """
    # Make a deep copy of the data to avoid modifying the original
    if isinstance(data, dict):
        result = {k: v for k, v in data.items()}
    elif isinstance(data, list):
        result = [item for item in data]
    else:
        # If data is not a dict or list, we can't extend it
        raise ValueError("Data must be a dictionary or list to extend")
    
    # Handle dictionary of key-value pairs
    if isinstance(key, dict):
        # If key is a dictionary, we add all key-value pairs
        if not jsonpath:
            if isinstance(result, dict):
                for k, v in key.items():
                    result[k] = v
                return result
            else:  # result is a list
                raise ValueError("Cannot add key-value pairs to a list without a jsonpath")
        else:
            # Add each key-value pair to the specified jsonpath
            extended_result = result
            for k, v in key.items():
                extended_result = _json_extend_single(extended_result, k, v, jsonpath)
            return extended_result
    
    # If no jsonpath is provided, add the single key-value pair to the root level
    if not jsonpath:
        if isinstance(result, dict):
            result[key] = value
        else:  # result is a list
            raise ValueError("Cannot add a key-value pair to a list without a jsonpath")
        return result
    
    # For a single key-value pair with a jsonpath, use the helper function
    return _json_extend_single(result, key, value, jsonpath)


def _json_extend_single(data: Any, key: str, value: Any, jsonpath: str) -> Any:
    """
    Helper function to add a single key-value pair to a JSON object at the specified jsonpath.
    
    Args:
        data (Any): The JSON data to extend.
        key (str): The key to add.
        value (Any): The value to add for the key.
        jsonpath (str): The JSON path where the key should be added.
    
    Returns:
        Any: The extended JSON data.
    """
    # Make a deep copy of the data to avoid modifying the original
    if isinstance(data, dict):
        result = {k: v for k, v in data.items()}
    elif isinstance(data, list):
        result = [item for item in data]
    else:
        # If data is not a dict or list, we can't extend it
        raise ValueError("Data must be a dictionary or list to extend")
    
    # Parse the jsonpath to find the target location
    path_parts = jsonpath.split('.')
    
    # Navigate to the target location
    target = result
    
    for i, part in enumerate(path_parts):
        # Check if this is the last part of the path
        is_last = i == len(path_parts) - 1
        
        # Handle array indices in the path (e.g., "users[0]" or "users[-1]")
        match = re.match(r'(.+)\[([-\d]+)\]$', part)
        if match:
            array_name, index_str = match.groups()
            index = int(index_str)
            
            # Ensure the parent has the array
            if array_name not in target:
                target[array_name] = []
            
            # Handle negative indices (e.g., array[-1] for the last element)
            if index < 0:
                # If the array is empty or the negative index is out of bounds,
                # we'll append a new element
                if len(target[array_name]) == 0 or abs(index) > len(target[array_name]):
                    target[array_name].append({} if is_last else {})
                    index = len(target[array_name]) - 1
                else:
                    # Convert negative index to positive index
                    index = len(target[array_name]) + index
            else:
                # Ensure the array is long enough for positive indices
                while len(target[array_name]) <= index:
                    target[array_name].append({} if is_last else {})
            
            # If this is the last part, add the key-value pair to the array element
            if is_last:
                target[array_name][index][key] = value
                return result
            else:
                target = target[array_name][index]
        else:
            # Regular object property
            if part not in target:
                target[part] = {}
            
            # If this is the last part, add the key-value pair to the object
            if is_last:
                target[part][key] = value
                return result
            else:
                target = target[part]
    
    # This should not be reached if the path is valid
    return result


def json_extend_file(file_path: str, key: Union[str, Dict[str, Any]], value: Any = None, jsonpath: str = "") -> Any:
    """
    Reads a JSON file, extends it with key-value pair(s), and returns the extended data.
    
    Args:
        file_path (str): Path to the JSON file.
        key (Union[str, Dict[str, Any]]): The key to add, or a dictionary of key-value pairs to add.
        value (Any, optional): The value to add for the key. Not used if key is a dictionary.
        jsonpath (str, optional): The JSON path where the key(s) should be added.
                                 If empty, the key(s) are added to the root level.
    
    Returns:
        Any: The extended JSON data.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return json_extend(data, key, value, jsonpath)# ==============================================================================
# JSON Aggregation Functions
# ==============================================================================

def json_aggregate(data: Any, field_name: str, aggregation: Union[str, Dict[str, Any]], jsonpath: str = "") -> Any:
    """
    Aggregates metrics across JSON data based on a field name.
    
    Args:
        data (Any): The JSON data to aggregate metrics from (as a Python dict/list).
        field_name (str): The field name to aggregate metrics for.
        aggregation (Union[str, Dict[str, Any]]): The aggregation function to use.
            Can be a string (e.g., "sum", "avg", "min", "max", "count") or a dictionary
            with custom aggregation options.
        jsonpath (str, optional): The JSON path where to start the aggregation from.
                                 If empty, aggregation starts from the root level.
    
    Returns:
        Any: The aggregation result.
    """
    # Extract values to aggregate based on field_name and jsonpath
    values = _extract_values(data, field_name, jsonpath)
    
    # Perform the aggregation
    if isinstance(aggregation, str):
        return _apply_builtin_aggregation(values, aggregation)
    else:
        return _apply_custom_aggregation(values, aggregation, data)


def _extract_values(data: Any, field_name: str, jsonpath: str = "") -> List[Any]:
    """
    Extracts values from JSON data based on field name and jsonpath.
    
    Args:
        data (Any): The JSON data to extract values from.
        field_name (str): The field name to extract values for.
        jsonpath (str, optional): The JSON path where to start the extraction from.
    
    Returns:
        List[Any]: List of extracted values.
    """
    values = []
    
    # If jsonpath is provided, navigate to that location first
    if jsonpath:
        data = _navigate_to_jsonpath(data, jsonpath)
        if data is None:
            return values
    
    # Extract values recursively
    _extract_values_recursive(data, field_name, values)
    
    return values


def _navigate_to_jsonpath(data: Any, jsonpath: str) -> Any:
    """
    Navigates to a specific location in the JSON data based on jsonpath.
    
    Args:
        data (Any): The JSON data to navigate in.
        jsonpath (str): The JSON path to navigate to.
    
    Returns:
        Any: The data at the specified jsonpath, or None if not found.
    """
    if not jsonpath:
        return data
    
    path_parts = jsonpath.split('.')
    current = data
    
    for part in path_parts:
        # Handle array indices in the path (e.g., "users[0]")
        match = re.match(r'(.+)\[([-\d]+)\]$', part)
        if match:
            array_name, index_str = match.groups()
            index = int(index_str)
            
            if not isinstance(current, dict) or array_name not in current:
                return None
            
            array_data = current[array_name]
            if not isinstance(array_data, list):
                return None
            
            # Handle negative indices
            if index < 0:
                if abs(index) > len(array_data):
                    return None
                current = array_data[index]
            else:
                if index >= len(array_data):
                    return None
                current = array_data[index]
        else:
            # Regular object property
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    
    return current


def _extract_values_recursive(data: Any, field_name: str, values: List[Any]) -> None:
    """
    Recursively extracts values from JSON data based on field name.
    
    Args:
        data (Any): The JSON data to extract values from.
        field_name (str): The field name to extract values for.
        values (List[Any]): List to append extracted values to.
    """
    if isinstance(data, dict):
        # Check if this dict contains the field_name
        if field_name in data:
            values.append(data[field_name])
        
        # Recursively check all values in the dict
        for value in data.values():
            _extract_values_recursive(value, field_name, values)
    
    elif isinstance(data, list):
        # Recursively check all items in the list
        for item in data:
            _extract_values_recursive(item, field_name, values)


def _apply_builtin_aggregation(values: List[Any], aggregation: str) -> Any:
    """
    Applies a built-in aggregation function to a list of values.
    
    Args:
        values (List[Any]): List of values to aggregate.
        aggregation (str): The aggregation function to apply.
    
    Returns:
        Any: The aggregation result.
    """
    # Filter out non-numeric values for numeric aggregations
    numeric_values = [v for v in values if isinstance(v, (int, float))]
    
    if not values:
        return None
    
    if aggregation.lower() == "sum":
        return sum(numeric_values) if numeric_values else None
    
    elif aggregation.lower() == "avg" or aggregation.lower() == "average" or aggregation.lower() == "mean":
        return sum(numeric_values) / len(numeric_values) if numeric_values else None
    
    elif aggregation.lower() == "min":
        return min(numeric_values) if numeric_values else None
    
    elif aggregation.lower() == "max":
        return max(numeric_values) if numeric_values else None
    
    elif aggregation.lower() == "count":
        return len(values)
    
    elif aggregation.lower() == "median":
        if not numeric_values:
            return None
        sorted_values = sorted(numeric_values)
        n = len(sorted_values)
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    elif aggregation.lower() == "mode":
        if not values:
            return None
        # Count occurrences of each value
        counter = {}
        for v in values:
            if v in counter:
                counter[v] += 1
            else:
                counter[v] = 1
        # Find the value(s) with the highest count
        max_count = max(counter.values())
        modes = [k for k, v in counter.items() if v == max_count]
        return modes[0] if len(modes) == 1 else modes
    
    elif aggregation.lower() == "stdev" or aggregation.lower() == "std":
        if not numeric_values or len(numeric_values) < 2:
            return None
        mean = sum(numeric_values) / len(numeric_values)
        variance = sum((x - mean) ** 2 for x in numeric_values) / len(numeric_values)
        return variance ** 0.5
    
    elif aggregation.lower() == "variance" or aggregation.lower() == "var":
        if not numeric_values or len(numeric_values) < 2:
            return None
        mean = sum(numeric_values) / len(numeric_values)
        return sum((x - mean) ** 2 for x in numeric_values) / len(numeric_values)
    
    elif aggregation.lower() == "range":
        if not numeric_values:
            return None
        return max(numeric_values) - min(numeric_values)
    
    elif aggregation.lower() == "first":
        return values[0] if values else None
    
    elif aggregation.lower() == "last":
        return values[-1] if values else None
    
    elif aggregation.lower() == "unique" or aggregation.lower() == "distinct":
        return list(set(values))
    
    elif aggregation.lower() == "unique_count" or aggregation.lower() == "distinct_count":
        return len(set(values))
    
    else:
        raise ValueError(f"Unknown aggregation function: {aggregation}")


def _apply_custom_aggregation(values: List[Any], options: Dict[str, Any], root_data: Any) -> Any:
    """
    Applies a custom aggregation function to a list of values.
    
    Args:
        values (List[Any]): List of values to aggregate.
        options (Dict[str, Any]): Options for the custom aggregation.
        root_data (Any): The original JSON data.
    
    Returns:
        Any: The aggregation result.
    """
    # Apply a combination of built-in aggregations
    if "combine" in options:
        combine_funcs = options["combine"]
        if not isinstance(combine_funcs, list):
            raise ValueError("'combine' must be a list of aggregation functions")
        
        results = {}
        for func in combine_funcs:
            if isinstance(func, str):
                results[func] = _apply_builtin_aggregation(values, func)
            elif isinstance(func, dict) and "name" in func:
                name = func["name"]
                args = func.get("args", {})
                if "custom_aggregation_path" in options and name not in ["sum", "avg", "average", "mean", "min", "max", "count", "median", "mode", "stdev", "std", "variance", "var", "range", "first", "last", "unique", "distinct", "unique_count", "distinct_count"]:
                    # Apply custom aggregation with specific args
                    file_path = options["custom_aggregation_path"]
                    aggregators = _load_custom_aggregators(file_path)
                    if name not in aggregators:
                        raise ValueError(f"Custom aggregation function '{name}' not found")
                    results[name] = aggregators[name](values, args, root_data)
                else:
                    # Apply built-in aggregation
                    results[name] = _apply_builtin_aggregation(values, name)
        
        return results
    
    # Check if a custom aggregation function path is provided
    elif "custom_aggregation_path" in options:
        file_path = options["custom_aggregation_path"]
        aggregators = _load_custom_aggregators(file_path)
        
        # Get the aggregation function name
        function_name = options.get("function", "")
        if not function_name or function_name not in aggregators:
            raise ValueError(f"Custom aggregation function '{function_name}' not found")
        
        # Apply the custom aggregation function
        args = options.get("args", {})
        return aggregators[function_name](values, args, root_data)
    
    # Apply a combination of built-in aggregations
    elif "combine" in options:
        combine_funcs = options["combine"]
        if not isinstance(combine_funcs, list):
            raise ValueError("'combine' must be a list of aggregation functions")
        
        results = {}
        for func in combine_funcs:
            if isinstance(func, str):
                results[func] = _apply_builtin_aggregation(values, func)
            elif isinstance(func, dict) and "name" in func:
                name = func["name"]
                args = func.get("args", {})
                if "custom_aggregation_path" in options:
                    # Apply custom aggregation with specific args
                    file_path = options["custom_aggregation_path"]
                    aggregators = _load_custom_aggregators(file_path)
                    if name not in aggregators:
                        raise ValueError(f"Custom aggregation function '{name}' not found")
                    results[name] = aggregators[name](values, args, root_data)
                else:
                    # Apply built-in aggregation
                    results[name] = _apply_builtin_aggregation(values, name)
        
        return results
    
    else:
        raise ValueError("Invalid custom aggregation options")


def _load_custom_aggregators(file_path: str) -> Dict[str, Callable]:
    """
    Safely loads a Python module from a given file path and returns its
    callable methods. This prevents the security risks associated with eval().
    
    Args:
        file_path (str): Path to the Python file with custom aggregator functions.
    
    Returns:
        Dict[str, Callable]: Dictionary of function names to callable functions.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Custom aggregator file not found at: {file_path}")

    spec = importlib.util.spec_from_file_location("custom_aggregators_module", file_path)
    if spec is None:
        raise ImportError(f"Could not load module specification from {file_path}")
        
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_aggregators_module"] = module
    spec.loader.exec_module(module)
    
    aggregators = {
        name: func for name, func in module.__dict__.items() if callable(func)
    }
    return aggregators


def json_aggregate_file(file_path: str, field_name: str, aggregation: Union[str, Dict[str, Any]], jsonpath: str = "") -> Any:
    """
    Reads a JSON file and aggregates metrics based on a field name.
    
    Args:
        file_path (str): Path to the JSON file.
        field_name (str): The field name to aggregate metrics for.
        aggregation (Union[str, Dict[str, Any]]): The aggregation function to use.
        jsonpath (str, optional): The JSON path where to start the aggregation from.
    
    Returns:
        Any: The aggregation result.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return json_aggregate(data, field_name, aggregation, jsonpath)
