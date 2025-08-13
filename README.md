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

-----

### **Installation**

`Validly` is available on PyPI. Install it with `pip`:

```sh
pip install Validly
```

-----

### **Basic Usage**

Use `json_difference` to compare two JSON objects. It returns a list of failure messages if differences are found.

```python
from Validly import json_difference

expected = {"id": 100, "name": "test"}
actual = {"id": 101, "name": "test"}

differences = json_difference(expected, actual)

# Output:
# ❌ Value mismatch at id: expected '100', got '101'
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
# This is a sample `custom_validators.py` file with your validation logic.
# You would need to create this file in your project.
#
# custom_validators.py
# import re
# from typing import Any, Tuple
# def validate_email_format(expected: Any, actual: Any) -> Tuple[bool, str]:
#     if not isinstance(actual, str): return False, "Value is not a string."
#     email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
#     if email_pattern.match(actual): return True, ""
#     return False, "Value is not a valid email format."

options = {
    "wildcard_keys": ["user.name"],
    "numeric_validations": {
        "user.age": {"operator": "gt", "value": 30},
        "login_count": {"operator": "le", "value": 5}
    },
    "is_uuid_keys": ["user.uuid", "uuid_field"],
    "is_pan_keys": ["user.pan", "pan_field"],
    "is_aadhar_keys": ["user.pan", "pan_field"],
    "custom_validators": {"user.email": "validate_email_format"},
    "custom_validator_path": "custom_validators.py",
    "skip_keys": ["user_id"]
}

# --- Running the comparison ---
differences = json_difference(expected_data, actual_data, options=options)

# Expected differences:
# ❌ Value mismatch at user.name: expected 'Jane Doe', got 'John Doe'
# ❌ Numeric validation failed at login_count: Value is not less than or equal to 5
# ❌ Extra key in actual: user.email
```

-----

### **Custom Validators**

Create a Python file (e.g., `custom_validators.py`) with your custom logic. Your validator methods should accept `expected` and `actual` values and return a `(bool, str)` tuple.

```python
# custom_validators.py
import re
from typing import Any, Tuple

def validate_email_format(expected: Any, actual: Any) -> Tuple[bool, str]:
    # ... (code as provided) ...
```

Then, configure the validator in your `options` dictionary:

```python
options = {
    "custom_validators": {"user.email": "validate_email_format"},
    "custom_validator_path": "custom_validators.py"
}
```

-----

### **Command Line Usage**

Compare two files directly from your terminal:

```sh
python -m Validly expected.json actual.json
```

-----

### **Contributing**

We welcome contributions\! If you have a feature idea or find a bug, please open an issue or submit a pull request on GitHub.

-----

### **License**

This project is licensed under the MIT License.