# validly

### **Validly**

A powerful and extensible data validation and comparison tool designed for developers and testers. Easily integrate into your automation projects to ensure JSON data integrity.

### **Features**

  * **Deep, Recursive Comparison**: Validates nested JSON structures seamlessly.
  * **Flexible Options**: Control validation with a rich set of options for every use case.
  * **Order-Agnostic Lists**: Intelligently compares lists of objects regardless of their order.
  * **Domain-Specific Validations**: Built-in checks for common data formats like UUIDs, PAN, and Aadhaar numbers.
  * **Referencing Capabilities**: Use a dynamic template to compare a field's value to another field in the `actual` JSON.
  * **Custom Validators**: Extend validation logic with your own Python methods from an external file.
  * **Numeric Comparisons**: Validate fields with operators like greater than (`gt`), less than (`lt`), and more.
  * **Wildcard Matching**: Use placeholders to ignore values that are dynamic or unpredictable.
  * **JSON Filtering**: Filter JSON data based on JSON paths and regex patterns with include/exclude options.
  * **JSON Transformation**: Transform JSON data with built-in and custom transformation functions.

---

### **Installation**

`Validly` is available on PyPI. Install it with `pip`:

```sh
pip install Validly
````

-----

### **Basic Usage**

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

-----

### **Advanced Usage with Options**

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

### **List Validation Modes**

`Validly` offers two ways to compare lists, controlled by the `list_validation_type` option.

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

### **Custom Validator Use Cases**

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

### **JSON Filtering**

Validly provides powerful JSON filtering capabilities through two main functions: `jsonfilter` and `jsonfilter_file`.

#### **Basic Filtering**

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

#### **Include vs Exclude Filtering**

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

### **JSON Transformation**

Validly provides powerful JSON transformation capabilities through two main functions: `json_transform` and `json_transform_file`.

#### **Basic Transformation**

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

#### **Adding New Fields**

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

-----

### **Contributing**

We welcome contributions! If you have a feature idea or find a bug, please open an issue or submit a pull request on [GitHub](https://github.com/swattoolchain/validly).

-----

### **License**

This project is licensed under the MIT License.
