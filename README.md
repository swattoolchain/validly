# Validly

A powerful and extensible data validation and comparison tool designed for developers and testers. Easily integrate into your automation projects to ensure JSON data integrity.

<a name="table-of-contents-anchor"></a>
## Features & Documentation

| Tool | Description | Documentation |
|------|-------------|---------------|
| **JSON Difference** | Deep, recursive comparison of JSON structures with flexible options, order-agnostic lists, domain-specific validations, referencing capabilities, custom validators, numeric comparisons, and wildcard matching. | [json_difference](#json-difference) |
| **JSON Filtering** | Filter JSON data based on JSON paths and regex patterns with include/exclude options. | [jsonfilter](#json-filtering) |
| **JSON Transformation** | Transform JSON data with built-in and custom transformation functions. | [json_transform](#json-transformation) |
| **JSON Extension** | Add key-value pairs to JSON data at any level, with support for multiple keys and array operations. | [json_extend](#json-extension) |
| **JSON Aggregation** | Aggregate metrics across JSON data with built-in and custom aggregation functions. | [json_aggregate](#json-aggregation) |
| **JSON Validation** | Validate JSON data against API contracts with type checking and format validation. | [json_validate](#json-validation) |
| **OpenAPI Validation** | Validate JSON data against OpenAPI/Swagger specifications. | [validate_openapi](#openapi-validation) |

- [Contributing](#user-content-contributing)
- [License](#user-content-license)

<a name="installation-anchor"></a>
## Installation

`Validly` is available on PyPI. Install it with `pip`:

```sh
pip install Validly
```


<h3 id="json-difference">1. JSON Difference (json_difference)</h3>

The `json_difference` function compares two JSON objects and identifies any differences between them.

<a name="basic-usage-anchor"></a>
#### Basic Usage

Use `json_difference` to compare two JSON objects. It returns a list of failure messages if differences are found.

```python
from Validly import json_difference

expected = {"id": 100, "name": "test"}
actual = {"id": 101, "name": "test"}

differences = json_difference(expected, actual)

# Output:
# {
#   'result': False,
#   'errors': [
#     {
#       'field': 'id',
#       'jsonpath': 'id',
#       'message': "Value mismatch: expected '100', got '101'"
#     }
#   ]
# }
```

<a name="advanced-usage-anchor"></a>
#### Advanced Usage with Options

Pass a dictionary of options to customize the validation behavior.

```python
from Validly import json_difference

# --- Sample Data ---
expected_data = {
    "user_id": "{ACTUAL_VALUE:user.id}",
    "user": {
        "id": 1234,
        "name": "Jane Doe",
        "age": 30
    },
    "uuid_field": "{ACTUAL_VALUE:user.uuid}",
    "pan_field": "{ACTUAL_VALUE:user.pan}",
    "login_count": 5
}
actual_data = {
    "user_id": 1234,
    "user": {
        "id": 1234,
        "name": "John Doe",
        "age": 32,
        "email": "test@example.com",
        "uuid": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        "pan": "ABCDE1234F"
    },
    "uuid_field": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "pan_field": "ABCDE1234F",
    "login_count": 6
}

# --- Validation Options ---
options = {
    "wildcard_keys": ["user.name"],
    "numeric_validations": {
        "user.age": {"operator": "gt", "value": 30},
        "login_count": {"operator": "le", "value": 5}
    },
    "is_uuid_keys": ["user.uuid", "uuid_field"],
    "is_pan_keys": ["user.pan", "pan_field"],
    "is_aadhar_keys": ["user.aadhar"],
    "custom_validators": {"user.email": "validate_email_format"},
    "custom_validator_path": "custom_validators.py",
    "skip_keys": ["user_id"]
}

# --- Running the comparison ---
differences = json_difference(expected_data, actual_data, options=options)

# Expected differences:
# {
#   'result': False,
#   'errors': [
#     {
#       'field': 'login_count',
#       'jsonpath': 'login_count',
#       'message': "Numeric validation failed: Value is not less than or equal to 5"
#     },
#     {
#       'field': 'email',
#       'jsonpath': 'user.email',
#       'message': "Extra key in actual: user.email"
#     }
#   ]
# }
```

<a name="list-validation-modes-anchor"></a>
### **List Validation Modes**

`Validly` offers two ways to compare lists, controlled by the `list_validation_type` option.

<a name="1-unordered-anchor"></a>
#### **1. Unordered (Default)**

This mode is designed for lists of objects where the order doesn't matter. It intelligently matches objects based on a set of common keys such as `"name"`, `"id"`, and `"qId"`.

```python
from Validly import json_difference

expected_list = [
    {"id": 1, "value": "a"},
    {"id": 2, "value": "b"}
]

actual_list = [
    {"id": 2, "value": "b"},
    {"id": 1, "value": "a"}
]

# The default behavior is 'unordered', so no option is needed here.
results = json_difference(expected_list, actual_list)

# { 'result': True, 'errors': [] }
```

<a name="2-symmetric-anchor"></a>
#### **2. Symmetric**

This mode is for lists where the order of items is critical. It performs a direct, index-based comparison.

```python
options = { "list_validation_type": "symmetric" }
results = json_difference(expected_list, actual_list, options=options)

# Expected result (failure due to different order):
# {
#   'result': False,
#   'errors': [
#     {
#       'field': '0',
#       'jsonpath': '[0]',
#       'message': "Value mismatch: expected {'id': 1, 'value': 'a'}, got {'id': 2, 'value': 'b'}"
#     },
#     {
#       'field': '1',
#       'jsonpath': '[1]',
#       'message': "Value mismatch: expected {'id': 2, 'value': 'b'}, got {'id': 1, 'value': 'a'}"
#     }
#   ]
# }
```

-----

<a name="custom-validators-anchor"></a>
### **Custom Validators**

Create a Python file (e.g., `custom_validators.py`) with your custom logic. Your validator methods should accept `expected` and `actual` values and return a `(bool, str)` tuple.

```python
# custom_validators.py
import re
from typing import Any, Tuple

def validate_email_format(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates if the actual value is a properly formatted email address."""
    if not isinstance(actual, str):
        return False, "Value is not a string."
    
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if email_pattern.match(actual):
        return True, ""
    
    return False, "Value is not a valid email format."

def validate_phone_number(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates if the actual value is a properly formatted phone number."""
    if not isinstance(actual, str):
        return False, "Value is not a string."
    
    # Remove any non-digit characters for comparison
    digits_only = re.sub(r'\D', '', actual)
    
    # Check if it's a valid length for a phone number (adjust as needed)
    if 10 <= len(digits_only) <= 15:
        return True, ""
    
    return False, f"Value '{actual}' is not a valid phone number format."

def validate_date_format(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates if the actual value matches the expected date format."""
    if not isinstance(actual, str):
        return False, "Value is not a string."
    
    # Expected should be a format string like "YYYY-MM-DD"
    if isinstance(expected, str) and expected.startswith("format:"):
        format_str = expected.split(":")[1].strip()
        
        # Simple validation for common formats
        if format_str == "YYYY-MM-DD":
            pattern = r"^\d{4}-\d{2}-\d{2}$"
        elif format_str == "MM/DD/YYYY":
            pattern = r"^\d{2}/\d{2}/\d{4}$"
        else:
            return False, f"Unknown date format: {format_str}"
            
        if re.match(pattern, actual):
            return True, ""
        return False, f"Value does not match the {format_str} format."
    
    # If no format specified, just do direct comparison
    return expected == actual, f"Expected {expected}, got {actual}"
```

Then, configure the validator in your `options` dictionary:

```python
options = {
    "custom_validators": {
        "user.email": "validate_email_format",
        "user.phone": "validate_phone_number",
        "user.birthdate": "validate_date_format"
    },
    "custom_validator_path": "path/to/custom_validators.py"
}
```

<a name="custom-validator-use-cases-anchor"></a>
### **Custom Validator Use Cases**

<a name="1-complex-format-validation-anchor"></a>
#### **1. Complex Format Validation**

Validate complex formats that aren't covered by built-in validators:

```python
# In custom_validators.py
def validate_credit_card(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates credit card numbers using the Luhn algorithm."""
    if not isinstance(actual, str):
        return False, "Value is not a string."
    
    # Remove spaces and dashes
    digits = re.sub(r'[\s-]', '', actual)
    if not digits.isdigit():
        return False, "Credit card contains non-digit characters."
    
    # Luhn algorithm implementation
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        n = int(digit)
        if i % 2 == 1:  # Odd position (0-indexed from right)
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    
    if checksum % 10 == 0:
        return True, ""
    return False, "Invalid credit card number (failed Luhn check)."
```

<a name="2-conditional-validation-anchor"></a>
#### **2. Conditional Validation**

Validate fields based on the values of other fields:

```python
# In custom_validators.py
def validate_shipping_address(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates shipping address based on country-specific rules."""
    if not isinstance(actual, dict):
        return False, "Value is not an object."
    
    country = actual.get('country', '')
    postal_code = actual.get('postalCode', '')
    
    # Different validation rules per country
    if country == 'US':
        if not re.match(r'^\d{5}(-\d{4})?$', postal_code):
            return False, "Invalid US ZIP code format."
    elif country == 'UK':
        if not re.match(r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$', postal_code, re.I):
            return False, "Invalid UK postal code format."
    
    return True, ""
```

<a name="3-integration-with-external-services-anchor"></a>
#### **3. Integration with External Services**

Validate data against external APIs or databases:

```python
# In custom_validators.py
import requests

def validate_against_api(expected: Any, actual: Any) -> Tuple[bool, str]:
    """Validates data against an external API."""
    try:
        # Make API call to validate the data
        response = requests.post(
            "https://api.example.com/validate",
            json={"value": actual}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("valid"):
                return True, ""
            return False, result.get("message", "API validation failed.")
        
        return False, f"API validation error: {response.status_code}"
    except Exception as e:
        return False, f"API validation exception: {str(e)}"
```

<a name="cli-usage-anchor"></a>
### **CLI Usage**

The `Validly` CLI allows you to perform validations from the command line without writing a Python script, making it ideal for CI/CD pipelines and automated testing.

```sh
# Basic usage
python -m Validly expected.json actual.json

# With options file
python -m Validly expected.json actual.json options.json
```

**Example options.json with custom validators:**

```json
{
  "list_validation_type": "symmetric",
  "wildcard_keys": ["user.name"],
  "numeric_validations": {
    "user.age": {"operator": "gt", "value": 30},
    "login_count": {"operator": "le", "value": 5}
  },
  "is_uuid_keys": ["user.uuid"],
  "is_pan_keys": ["user.pan"],
  "custom_validators": {
    "user.email": "validate_email_format",
    "user.phone": "validate_phone_number"
  },
  "custom_validator_path": "./custom_validators.py",
  "skip_keys": ["user_id", "id"]
}
```

-----

<h3 id="json-filtering">2. JSON Filtering (jsonfilter)</h3>

Validly provides powerful JSON filtering capabilities through two main functions: `jsonfilter` and `jsonfilter_file`.

<a name="basic-filtering-anchor"></a>
#### Basic Filtering

Filter JSON data using JSON paths and regex patterns:

```python
from Validly import jsonfilter

# Sample data
data = {
    "user": {
        "id": 1234,
        "name": "John Doe",
        "contact": {
            "email": "john@example.com",
            "phone": "555-1234"
        }
    },
    "orders": [
        {"id": 101, "product": "Laptop", "price": 999.99},
        {"id": 102, "product": "Mouse", "price": 24.99}
    ],
    "metadata": {
        "version": "1.0",
        "timestamp": "2025-09-06T06:00:00Z"
    }
}

# Filter options (include mode is default)
options = {
    "jsonpath": ["user.name", "user.contact.email", "orders"]
}

# Apply filtering
filtered_data = jsonfilter(data, options)

# Result:
# {
#     "user": {
#         "name": "John Doe",
#         "contact": {
#             "email": "john@example.com"
#         }
#     },
#     "orders": [
#         {"id": 101, "product": "Laptop", "price": 999.99},
#         {"id": 102, "product": "Mouse", "price": 24.99}
#     ]
# }
```

<a name="include-vs-exclude-filtering-anchor"></a>
#### Include vs Exclude Filtering

Choose between including or excluding the matched paths:

```python
# Include mode (default)
options = {
    "jsonpath": ["user.id", "metadata.version"],
    "filter_type": "include"  # Only keep matched paths
}

# Result:
# {
#     "user": {
#         "id": 1234
#     },
#     "metadata": {
#         "version": "1.0"
#     }
# }

# Exclude mode
options = {
    "jsonpath": ["user.id", "metadata.version"],
    "filter_type": "exclude"  # Remove matched paths, keep everything else
}

# Result:
# {
#     "user": {
#         "name": "John Doe",
#         "contact": {
#             "email": "john@example.com",
#             "phone": "555-1234"
#         }
#     },
#     "orders": [
#         {"id": 101, "product": "Laptop", "price": 999.99},
#         {"id": 102, "product": "Mouse", "price": 24.99}
#     ],
#     "metadata": {
#         "timestamp": "2025-09-06T06:00:00Z"
#     }
# }
```

<a name="wildcard-filtering-anchor"></a>
#### **Wildcard Filtering**

Use wildcards to include multiple fields matching a pattern:

```python
# Filter with wildcards
options = {
    "jsonpath": ["user.*", "metadata.version"]
}

filtered_data = jsonfilter(data, options)

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe",
#         "contact": {
#             "email": "john@example.com",
#             "phone": "555-1234"
#         }
#     },
#     "metadata": {
#         "version": "1.0"
#     }
# }
```

<a name="regex-based-filtering-anchor"></a>
#### **Regex-based Filtering**

Filter keys that match a regular expression pattern:

```python
# Filter with regex
options = {
    "regex": "id"
}

filtered_data = jsonfilter(data, options)

# Result:
# {
#     "user": {
#         "id": 1234
#     },
#     "orders": [
#         {"id": 101},
#         {"id": 102}
#     ]
# }
```

<a name="key-based-filtering-across-all-levels-anchor"></a>
#### **Key-based Filtering Across All Levels**

Filter keys exactly matching specified names at any level in the JSON structure:

```python
# Filter by exact key names at any level
options = {
    "keys": ["id", "email"],
    "filter_type": "include"  # Only keep matched keys
}

filtered_data = jsonfilter(data, options)

# Result:
# {
#     "user": {
#         "id": 1234,
#         "contact": {
#             "email": "john@example.com"
#         }
#     },
#     "orders": [
#         {"id": 101},
#         {"id": 102}
#     ]
# }

# Exclude specific keys at any level
options = {
    "keys": ["email", "price"],
    "filter_type": "exclude"  # Remove matched keys
}

filtered_data = jsonfilter(data, options)

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe",
#         "contact": {
#             "phone": "555-1234"
#         }
#     },
#     "orders": [
#         {"id": 101, "product": "Laptop"},
#         {"id": 102, "product": "Mouse"}
#     ],
#     "metadata": {
#         "version": "1.0",
#         "timestamp": "2025-09-06T06:00:00Z"
#     }
# }
```

<a name="value-based-filtering-anchor"></a>
#### **Value-based Filtering**

Filter JSON data based on the values of fields:

```python
# Sample data with various value types
data = {
    "user": {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com",
        "age": 17,
        "address": {
            "street": "123 Main St",
            "city": "Anytown",
            "country": null
        },
        "phone": "",
        "preferences": {
            "notifications": True,
            "language": null
        }
    },
    "orders": [
        {
            "id": 1001,
            "total": 99.99,
            "shipping": null,
            "notes": ""
        },
        {
            "id": 1002,
            "total": 149.99,
            "shipping": 10.0,
            "notes": "Express delivery"
        }
    ]
}

# Remove null values
options = {
    "value_filters": {
        "null_values": True
    }
}

filtered_data = jsonfilter(data, options)

# Result will exclude all null values:
# {
#     "user": {
#         "id": 123,
#         "name": "John Doe",
#         "email": "john@example.com",
#         "age": 17,
#         "address": {
#             "street": "123 Main St",
#             "city": "Anytown"
#         },
#         "phone": "",
#         "preferences": {
#             "notifications": true
#         }
#     },
#     "orders": [
#         {
#             "id": 1001,
#             "total": 99.99,
#             "notes": ""
#         },
#         {
#             "id": 1002,
#             "total": 149.99,
#             "shipping": 10.0,
#             "notes": "Express delivery"
#         }
#     ]
# }

# Remove empty strings
options = {
    "value_filters": {
        "empty_strings": True
    }
}

filtered_data = jsonfilter(data, options)

# Remove values based on conditions
options = {
    "value_filters": {
        "conditions": [
            {
                "key": "age",
                "operator": "lt",
                "value": 18
            }
        ]
    }
}

filtered_data = jsonfilter(data, options)

# Combine multiple value filters
options = {
    "value_filters": {
        "null_values": True,
        "empty_strings": True,
        "conditions": [
            {
                "key": "*",  # Apply to all keys
                "operator": "lt",
                "value": 10
            }
        ]
    }
}

filtered_data = jsonfilter(data, options)

# Combine with path-based filtering
options = {
    "jsonpath": ["user.name", "user.email"],
    "value_filters": {
        "null_values": True
    }
}

filtered_data = jsonfilter(data, options)
```

Supported value filter operators:
- `eq`: Equal to
- `ne`: Not equal to
- `gt`: Greater than
- `lt`: Less than
- `ge`: Greater than or equal to
- `le`: Less than or equal to

<a name="filtering-from-files-anchor"></a>
#### **Filtering from Files**

Filter JSON data directly from files:

```python
from Validly import jsonfilter_file

# Filter JSON from a file
options = {
    "jsonpath": ["user", "metadata.version"]
}

filtered_data = jsonfilter_file("data.json", options)

# Process the filtered data
print(filtered_data)
```

<h3 id="json-transformation">3. JSON Transformation (json_transform)</h3>

Validly provides powerful JSON transformation capabilities through two main functions: `json_transform` and `json_transform_file`.

<a name="basic-transformation-anchor"></a>
#### Basic Transformation

Transform JSON data using built-in transformation methods:

```python
from Validly import json_transform

# Sample data
data = {
    "user": {
        "id": "1234",  # String that needs to be converted to integer
        "name": "john doe",  # Needs to be capitalized
        "active": 1  # Needs to be converted to boolean
    },
    "price": "99.99"  # String that needs to be converted to float
}

# Transform options
options = {
    "transforms": {
        "user.id": {"method": "to_int"},
        "user.name": {"method": "format", "args": {"format": "{0.title()}"}},
        "user.active": {"method": "to_bool"},
        "price": {"method": "to_float"}
    }
}

# Apply transformation
transformed_data = json_transform(data, options)

# Result:
# {
#     "user": {
#         "id": 1234,  # Now an integer
#         "name": "John Doe",  # Now capitalized
#         "active": True  # Now a boolean
#     },
#     "price": 99.99  # Now a float
# }
```

<a name="adding-new-fields-anchor"></a>
#### Adding New Fields

Add new fields to the JSON structure:

```python
# Add new fields
options = {
    "add_fields": {
        "user.full_name": {
            "value": "John Smith Doe",
            "parent": "user"
        },
        "metadata": {
            "value": {"created_at": "2025-09-06", "version": "1.0"},
            "parent": ""
        }
    }
}

transformed_data = json_transform(data, options)

# Result:
# {
#     "user": {
#         "id": "1234",
#         "name": "john doe",
#         "active": 1,
#         "full_name": "John Smith Doe"  # New field added
#     },
#     "price": "99.99",
#     "metadata": {  # New field added at root level
#         "created_at": "2025-09-06",
#         "version": "1.0"
#     }
# }
```

<a name="custom-transformers-anchor"></a>
#### **Custom Transformers**

Create a Python file with custom transformation functions:

```python
# custom_transformers.py
def capitalize_name(value, args, root_data):
    """Capitalize each word in a name."""
    if not isinstance(value, str):
        return value
    return value.title()

def calculate_total(value, args, root_data):
    """Calculate total price based on price and quantity."""
    price = float(root_data.get("price", 0))
    quantity = args.get("quantity", 1)
    return price * quantity
```

Then use these custom transformers in your code:

```python
options = {
    "transforms": {
        "user.name": {"method": "capitalize_name"},
        "total": {"method": "calculate_total", "args": {"quantity": 3}}
    },
    "add_fields": {
        "total": {
            "value": 0,  # This will be replaced by the transformer
            "parent": ""
        }
    },
    "custom_transform_path": "custom_transformers.py"
}

transformed_data = json_transform(data, options)

# Result:
# {
#     "user": {
#         "id": "1234",
#         "name": "John Doe",  # Capitalized using custom transformer
#         "active": 1
#     },
#     "price": "99.99",
#     "total": 299.97  # Calculated using custom transformer (99.99 * 3)
# }
```

<a name="transforming-from-files-anchor"></a>
#### **Transforming from Files**

Transform JSON data directly from files:

```python
from Validly import json_transform_file

# Transform JSON from a file
options = {
    "transforms": {
        "user.id": {"method": "to_int"},
        "price": {"method": "to_float"}
    }
}

transformed_data = json_transform_file("data.json", options)

# Process the transformed data
print(transformed_data)
```

<h3 id="json-extension">4. JSON Extension (json_extend)</h3>

Validly provides a powerful way to add keys to JSON data at any level through the `json_extend` and `json_extend_file` functions.

<a name="basic-extension-anchor"></a>
#### Basic Extension

Add a key-value pair to a JSON object:

```python
from Validly import json_extend

# Sample data
data = {
    "user": {
        "id": 1234,
        "name": "John Doe"
    },
    "metadata": {
        "version": "1.0"
    }
}

# Add a key to the root level
extended_data = json_extend(data, "status", "active")

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe"
#     },
#     "metadata": {
#         "version": "1.0"
#     },
#     "status": "active"
# }
```

Add multiple keys at once:

```python
# Add multiple keys at once to the root level
extended_data = json_extend(data, {
    "status": "active",
    "created_at": "2025-09-09",
    "updated_at": "2025-09-09"
})

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe"
#     },
#     "metadata": {
#         "version": "1.0"
#     },
#     "status": "active",
#     "created_at": "2025-09-09",
#     "updated_at": "2025-09-09"
# }
```

<a name="nested-path-extension-anchor"></a>
#### Nested Path Extension

Add a key-value pair to a nested object using a JSON path:

```python
# Add a key to a nested object
extended_data = json_extend(data, "email", "john@example.com", "user")

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe",
#         "email": "john@example.com"
#     },
#     "metadata": {
#         "version": "1.0"
#     }
# }

# Add multiple keys to a nested object
extended_data = json_extend(data, {
    "address": "123 Main St",
    "city": "New York",
    "country": "USA"
}, jsonpath="user")

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe",
#         "address": "123 Main St",
#         "city": "New York",
#         "country": "USA"
#     },
#     "metadata": {
#         "version": "1.0"
#     }
# }

# Add a key to a deeply nested object (creates the path if it doesn't exist)
extended_data = json_extend(data, "shipping", {"method": "express"}, "user.preferences")

# Result:
# {
#     "user": {
#         "id": 1234,
#         "name": "John Doe",
#         "preferences": {
#             "shipping": {
#                 "method": "express"
#             }
#         }
#     },
#     "metadata": {
#         "version": "1.0"
#     }
# }
```

<a name="array-element-extension-anchor"></a>
#### Array Element Extension

Add a key-value pair to an array element:

```python
# Sample data with an array
data = {
    "users": [
        {"id": 1, "name": "John"},
        {"id": 2, "name": "Jane"}
    ]
}

# Add a key to an array element
extended_data = json_extend(data, "email", "john@example.com", "users[0]")

# Result:
# {
#     "users": [
#         {
#             "id": 1,
#             "name": "John",
#             "email": "john@example.com"
#         },
#         {
#             "id": 2,
#             "name": "Jane"
#         }
#     ]
# }

# Add a key to the last array element using negative index
extended_data = json_extend(data, "email", "jane@example.com", "users[-1]")

# Result:
# {
#     "users": [
#         {
#             "id": 1,
#             "name": "John"
#         },
#         {
#             "id": 2,
#             "name": "Jane",
#             "email": "jane@example.com"
#         }
#     ]
# }

# Add multiple keys to an array element
extended_data = json_extend(data, {
    "quantity": 2,
    "discount": 0.1,
    "total": 899.99
}, jsonpath="orders[0]")

# Add a key to a non-existent array element (creates the array and element)
extended_data = json_extend(data, "name", "Alice", "family[0]")

# Result:
# {
#     "users": [
#         {"id": 1, "name": "John"},
#         {"id": 2, "name": "Jane"}
#     ],
#     "family": [
#         {"name": "Alice"}
#     ]
# }

# Append to a non-existent array using array[-1]
extended_data = json_extend(data, "name", "Alice", "family[-1]")

# Result is the same as above
```

<a name="extending-files-anchor"></a>
#### Extending from Files

Extend JSON data directly from files:

```python
from Validly import json_extend_file

# Extend JSON from a file with a single key-value pair
extended_data = json_extend_file("data.json", "status", "active")

# Extend JSON from a file with multiple key-value pairs
extended_data = json_extend_file("data.json", {
    "status": "active",
    "created_at": "2025-09-09",
    "updated_at": "2025-09-09"
})

# Extend JSON from a file at a specific path
extended_data = json_extend_file("data.json", "email", "john@example.com", "user")

# Extend JSON from a file with multiple key-value pairs at a specific path
extended_data = json_extend_file("data.json", {
    "address": "123 Main St",
    "city": "New York",
    "country": "USA"
}, jsonpath="user")

# Extend JSON from a file with array indices, including negative indices
extended_data = json_extend_file("data.json", "email", "john@example.com", "users[0]")
extended_data = json_extend_file("data.json", "email", "jane@example.com", "users[-1]")

# Process the extended data
print(extended_data)
```

<h3 id="json-validation">6. JSON Validation (json_validate)</h3>

Validly provides a powerful way to validate JSON data against API contracts using the `json_validate` function.

<a name="basic-validation-anchor"></a>
#### Basic Validation

Validate JSON data against a contract schema:

```python
from Validly import json_validate

# Sample data
data = {
    "user": {
        "id": "1234",
        "name": "John Doe",
        "age": 30,
        "email": "john@example.com"
    },
    "orders": [
        {"id": 101, "product": "Laptop", "price": 999.99}
    ]
}

# Contract schema
contract = {
    "user": {
        "id": "",
        "name": "",
        "age": 0,
        "email": ""
    },
    "orders": [
        {"id": 0, "product": "", "price": 0.0}
    ]
}

# Validate data against contract
result = json_validate(data, contract)

# Result:
# {
#     "result": True,
#     "errors": []
# }
```

<a name="type-validation-anchor"></a>
#### Type Validation

Validate that fields have the correct data types:

```python
options = {
    "type_validations": {
        "user.id": "string",
        "user.age": "number",
        "user.active": "boolean",
        "orders": "array"
    }
}

result = json_validate(data, contract, options)
```

Supported types include: `string`, `number`, `boolean`, `array`, `object`, and `any`.

<a name="format-validation-anchor"></a>
#### Format Validation

Validate that fields match specific formats:

```python
options = {
    "is_uuid_keys": ["user.uuid"],
    "is_pan_keys": ["user.pan"],
    "is_aadhar_keys": ["user.aadhar"],
    "regex_keys": {
        "user.email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    }
}

result = json_validate(data, contract, options)
```

<a name="required-fields-validation-anchor"></a>
#### Required Fields Validation

Specify fields that must be present in the data:

```python
options = {
    "required_keys": [
        "user.id",
        "user.name",
        "user.email",
        "orders"
    ]
}

result = json_validate(data, contract, options)
```

<a name="custom-validation-anchor"></a>
#### Custom Validation

Use custom validators for complex validation logic:

```python
# First, create a custom validator file
with open('custom_validators.py', 'w') as f:
    f.write(r"""
def validate_email(expected, actual):
    import re
    if not isinstance(actual, str):
        return False, "Value is not a string"
    
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if email_pattern.match(actual):
        return True, ""
    
    return False, f"'{actual}' is not a valid email format"
""")

# Then use the custom validator
options = {
    "custom_validators": {
        "user.email": "validate_email"
    },
    "custom_validator_path": "custom_validators.py"
}

result = json_validate(data, contract, options)
```

<a name="strict-mode-anchor"></a>
#### Strict Mode

Enforce that the data doesn't contain any fields not defined in the contract:

```python
options = {
    "strict_mode": True
}

result = json_validate(data, contract, options)
```

<h3 id="openapi-validation">7. OpenAPI Validation (validate_openapi)</h3>

Validly provides powerful validation against OpenAPI/Swagger specifications using the `validate_openapi` function.

<a name="basic-openapi-validation-anchor"></a>
#### Basic OpenAPI Validation

Validate JSON data against an OpenAPI schema:

```python
from Validly import validate_openapi, validate_openapi_file, validate_openapi_url, load_openapi_schema

# Method 1: Load schema from file and validate
result = validate_openapi_file(data, 'openapi.json')

# Method 2: Load schema from URL and validate
result = validate_openapi_url(data, 'https://example.com/api/openapi.json')

# Method 3: Load schema manually and validate
with open('openapi.json', 'r') as f:
    openapi_schema = json.load(f)

# Or load from URL
openapi_schema = load_openapi_schema('https://example.com/api/openapi.json')

# Sample data to validate
data = {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
}

# Validate against a specific schema component
user_schema = openapi_schema["components"]["schemas"]["User"]
result = validate_openapi(data, user_schema)

# Result:
# {
#     "result": True,
#     "errors": []
# }
```

<a name="validating-request-response-anchor"></a>
#### Validating Request/Response

Validate request or response data against OpenAPI path definitions:

```python
# Extract request schema from OpenAPI spec
request_schema = openapi_schema["paths"]["/users"]["post"]["requestBody"]["content"]["application/json"]["schema"]

# Validate request data
request_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
}

result = validate_openapi(request_data, request_schema)

# Extract response schema for a 200 response
response_schema = openapi_schema["paths"]["/users"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]

# Validate response data
response_data = {
    "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    "name": "John Doe",
    "email": "john@example.com",
    "created_at": "2025-09-06T06:00:00Z"
}

result = validate_openapi(response_data, response_schema)
```

<a name="openapi-schema-components-anchor"></a>
#### OpenAPI Schema Components

The `validate_openapi` function automatically handles OpenAPI schema features:

- **Data Types**: string, number, integer, boolean, array, object
- **Formats**: uuid, email, uri, date, date-time
- **Validations**: required fields, minimum/maximum values, patterns
- **Schema Structures**: oneOf, anyOf, allOf
- **Nested References**: $ref references to other schema components

```python
# OpenAPI schema with nested references
schema = {
    "openapi": "3.0.0",
    "components": {
        "schemas": {
            "User": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"$ref": "#/components/schemas/Address"}
                }
            },
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"}
                }
            }
        }
    }
}

# Data with nested structure
data = {
    "name": "John Doe",
    "address": {
        "street": "123 Main St",
        "city": "New York"
    }
}

# Validate against the schema with nested references
result = validate_openapi(data, schema["components"]["schemas"]["User"])
```

```python
# OpenAPI schema with various validations
schema = {
    "type": "object",
    "required": ["name", "email"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1
        },
        "email": {
            "type": "string",
            "format": "email"
        },
        "age": {
            "type": "integer",
            "minimum": 18
        }
    }
}

# Validate data against the schema
result = validate_openapi(data, schema)
```

<a name="custom-openapi-validation-anchor"></a>
#### Custom OpenAPI Validation

You can extend OpenAPI validation with custom validators:

```python
# First, create a custom validator file
with open('custom_validators.py', 'w') as f:
    f.write(r"""
def validate_complex_email(expected, actual):
    import re
    if not isinstance(actual, str):
        return False, "Value is not a string"
    
    # More complex email validation than the standard format
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not email_pattern.match(actual):
        return False, f"'{actual}' is not a valid email format"
    
    # Additional validation rules
    if actual.endswith('.test'):
        return False, "Test domains are not allowed"
    
    return True, ""
""")

# Then use the custom validator with OpenAPI validation
options = {
    "custom_validators": {
        "email": "validate_complex_email"
    },
    "custom_validator_path": "custom_validators.py"
}

result = validate_openapi(data, schema, options)
```

<h2 id="contributing">Contributing</h2>

We welcome contributions! If you have a feature idea or find a bug, please open an issue or submit a pull request on [GitHub](https://github.com/swattoolchain/validly).

<h2 id="license">License</h2>

This project is licensed under the MIT License.

<h3 id="json-aggregation">5. JSON Aggregation (json_aggregate)</h3>

Validly provides a powerful way to aggregate metrics across JSON data through the `json_aggregate` and `json_aggregate_file` functions.

<a name="basic-aggregation-anchor"></a>
#### Basic Aggregation

Aggregate metrics from JSON data based on a field name:

```python
from Validly import json_aggregate

# Sample data
data = {
    "metrics": [
        {"name": "CPU", "value": 75.5, "unit": "%"},
        {"name": "Memory", "value": 60.2, "unit": "%"},
        {"name": "Disk", "value": 85.0, "unit": "%"}
    ],
    "servers": [
        {
            "id": "srv-001",
            "name": "Web Server",
            "metrics": [
                {"name": "CPU", "value": 80.0, "unit": "%"},
                {"name": "Memory", "value": 70.5, "unit": "%"},
                {"name": "Requests", "value": 1500, "unit": "req/s"}
            ]
        }
    ]
}

# Sum all "value" fields across the entire JSON
result = json_aggregate(data, "value", "sum")

# Result: 1871.2
```

You can also specify a JSON path to aggregate metrics from a specific part of the JSON:

```python
# Average of "value" fields in root metrics only
result = json_aggregate(data, "value", "avg", "metrics")

# Result: 73.56666666666666
```

<a name="multiple-aggregations-anchor"></a>
#### Multiple Aggregations

Perform multiple aggregations at once:

```python
# Multiple aggregations at once
result = json_aggregate(data, "value", {
    "combine": ["sum", "avg", "min", "max", "count"]
})

# Result:
# {
#     "sum": 1871.2,
#     "avg": 73.56666666666666,
#     "min": 60.2,
#     "max": 1500,
#     "count": 6
# }
```

<a name="statistical-aggregations-anchor"></a>
#### Statistical Aggregations

Perform statistical aggregations:

```python
# Statistical aggregations
result = json_aggregate(data, "value", {
    "combine": ["median", "stdev", "variance", "range"]
})

# Result:
# {
#     "median": 77.75,
#     "stdev": 583.2,
#     "variance": 340000.0,
#     "range": 1439.8
# }
```

Supported aggregation functions:
- `sum`: Sum of all values
- `avg`, `average`, `mean`: Average of all values
- `min`: Minimum value
- `max`: Maximum value
- `count`: Count of all values
- `median`: Median value
- `mode`: Most frequent value(s)
- `stdev`, `std`: Standard deviation
- `variance`, `var`: Variance
- `range`: Range (max - min)
- `first`: First value
- `last`: Last value
- `unique`, `distinct`: List of unique values
- `unique_count`, `distinct_count`: Count of unique values

<a name="custom-aggregations-anchor"></a>
#### Custom Aggregations

Create a Python file with custom aggregation functions:

```python
# custom_aggregators.py
def weighted_average(values, args, root_data):
    """Calculate weighted average of values."""
    weights = args.get("weights", [1.0] * len(values))
    if len(weights) < len(values):
        weights = weights + [1.0] * (len(values) - len(weights))
    
    weighted_sum = sum(v * w for v, w in zip(values, weights))
    total_weight = sum(weights[:len(values)])
    
    return weighted_sum / total_weight if total_weight > 0 else None

def percentile(values, args, root_data):
    """Calculate percentile of values."""
    p = args.get("p", 50)  # Default to median (50th percentile)
    
    if not values:
        return None
    
    # Filter numeric values
    numeric_values = [v for v in values if isinstance(v, (int, float))]
    if not numeric_values:
        return None
    
    # Sort values
    sorted_values = sorted(numeric_values)
    n = len(sorted_values)
    
    # Calculate percentile
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    
    # Calculate index
    idx = (n - 1) * p / 100
    idx_floor = int(idx)
    idx_ceil = idx_floor + 1 if idx_floor < n - 1 else idx_floor
    
    # Interpolate
    if idx_floor == idx_ceil:
        return sorted_values[idx_floor]
    else:
        return sorted_values[idx_floor] * (idx_ceil - idx) + sorted_values[idx_ceil] * (idx - idx_floor)
```

Then use these custom aggregators in your code:

```python
# Custom aggregation
result = json_aggregate(data, "value", {
    "custom_aggregation_path": "custom_aggregators.py",
    "function": "weighted_average",
    "args": {
        "weights": [2.0, 1.0, 1.5, 0.5, 1.0]
    }
})

# Result: 559.6461538461538
```

You can also combine built-in and custom aggregations:

```python
# Combining built-in and custom aggregations
result = json_aggregate(data, "value", {
    "combine": [
        "avg",
        "median",
        {
            "name": "weighted_average",
            "args": {
                "weights": [2.0, 1.0, 1.5, 0.5, 1.0]
            }
        },
        {
            "name": "percentile",
            "args": {
                "p": 75
            }
        }
    ],
    "custom_aggregation_path": "custom_aggregators.py",
    "function": "dummy"  # This is needed but won't be used for combine mode
})

# Result:
# {
#     "avg": 73.56666666666666,
#     "median": 77.75,
#     "weighted_average": 559.6461538461538,
#     "percentile": 91.525
# }
```

<a name="aggregating-files-anchor"></a>
#### Aggregating from Files

Aggregate metrics directly from JSON files:

```python
from Validly import json_aggregate_file

# Aggregate metrics from a file
result = json_aggregate_file("data.json", "value", "sum")

# Aggregate metrics from a file with multiple aggregations
result = json_aggregate_file("data.json", "value", {
    "combine": ["sum", "avg", "min", "max", "count"]
})

# Process the aggregated results
print(result)
```
