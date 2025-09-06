import json
import os
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
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

def jsonfilter(data: Any, options: Dict[str, Any]) -> Any:
    """
    Filters a JSON object based on specified options.
    
    Args:
        data (Any): The JSON data to filter (as a Python dict/list).
        options (Dict[str, Any]): Filtering options with the following possible keys:
            - jsonpath (List[str]): List of JSON paths to filter (supports wildcards).
            - regex (str): Filter keys containing this text pattern.
            - filter_type (str): Either "include" (default) or "exclude" to specify whether to include or exclude the matched paths.
    
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
    
    # Handle different data types
    if isinstance(data, dict):
        return _filter_dict(data, options, "")
    elif isinstance(data, list):
        return _filter_list(data, options, "")
    else:
        # Primitive types are returned as is
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
    filter_type = options.get("filter_type", "include")
    
    # If no filtering options provided, return the data as is
    if not jsonpaths and not regex_pattern:
        return data
    
    for key, value in data.items():
        # Build the current JSON path
        key_path = f"{current_path}.{key}" if current_path else key
        
        # Check if this key or its children should be included/excluded
        path_matched = False
        
        # Check jsonpath patterns
        if jsonpaths:
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
        
        # Check regex pattern
        if regex_pattern and re.search(regex_pattern, key):
            path_matched = True
        
        # Determine whether to include this key based on filter_type
        include_key = (path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude")
        
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
    filter_type = options.get("filter_type", "include")
    
    if not jsonpaths and not regex_pattern:
        return data
    
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
    if (path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude"):
        return data
    
    result = []
    
    for i, item in enumerate(data):
        item_path = f"{current_path}[{i}]"
        
        if isinstance(item, dict):
            filtered_item = _filter_dict(item, options, item_path)
            if filtered_item:  # Only add non-empty dictionaries
                result.append(filtered_item)
        elif isinstance(item, list):
            filtered_item = _filter_list(item, options, item_path)
            if filtered_item:  # Only add non-empty lists
                result.append(filtered_item)
        else:
            # For primitive types, check if the parent path is included
            path_matched = False
            
            for path in jsonpaths:
                if path == current_path or current_path.startswith(f"{path}."):
                    path_matched = True
                    break
            
            # Check regex pattern for the index (as a string)
            if regex_pattern and re.search(regex_pattern, str(i)):
                path_matched = True
            
            # Determine whether to include this item based on filter_type
            include_item = (path_matched and filter_type == "include") or (not path_matched and filter_type == "exclude")
            
            if include_item:
                result.append(item)
    
    return result


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
