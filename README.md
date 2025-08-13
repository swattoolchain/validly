# Validly

A powerful and extensible data validation and comparison tool designed for developers and testers. Easily integrate it into your automation projects to ensure JSON data integrity.

### **Features**

* **Deep, Recursive Comparison**: Validates nested JSON structures seamlessly.
* **Flexible Options**: Control validation with a rich set of options for every use case.
* **List Validation Modes**: Choose between order-agnostic and symmetric list comparisons.
* **Domain-Specific Validations**: Built-in checks for common data formats like UUIDs, PAN, and Aadhaar numbers.
* **Referencing Capabilities**: Use a dynamic template to compare a field's value to another field in the `actual` JSON.
* **Numeric Comparisons**: Validate fields with operators like greater than (`gt`), less than (`lt`), and more.
* **Wildcard Matching**: Use placeholders to ignore values that are dynamic or unpredictable.

---

### **Installation**

`Validly` is available on PyPI. Install it with `pip`:

```sh
pip install Validly
````

-----

### **Usage and Output**

The core function, `json_difference`, returns a structured dictionary containing the validation result and a detailed list of errors, if any. This format is ideal for programmatic analysis and reporting in your automation framework.

**Return Format:**

The function returns a dictionary with the following keys:

  * `result`: A boolean (`True` for success, `False` for failure).
  * `errors`: A list of dictionaries, where each dictionary represents a single validation failure.

**Error Dictionary Format:**

Each error in the `errors` list contains these keys:

  * `field`: The name of the field where the error occurred.
  * `jsonpath`: The full path to the field (e.g., `"user.age"`).
  * `message`: A human-readable description of the validation failure.

**Example:**

```python
from Validly import json_difference

expected = {"id": 100, "name": "test"}
actual = {"id": 101, "name": "test"}

result = json_difference(expected, actual)

# The result dictionary will be:
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

### **List Validation Modes**

`Validly` offers two ways to compare lists, controlled by the `list_validation_type` option.

#### **1. Unordered (Default)**

This mode is designed for lists of objects where the order doesn't matter. It intelligently matches objects based on a set of common keys such as `"name"`, `"id"`, and `"qId"`.

**How it works:**
The function creates a map of objects from both lists and then compares them based on their key. It reports missing and extra items but ignores changes in their order.

**Example:**
The comparison will pass despite the different order in the `actual` list.

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

**How to use:**
Set `list_validation_type` to `"symmetric"` in your options.

```python
options = { "list_validation_type": "symmetric" }

expected_list = [
    {"id": 1, "value": "a"},
    {"id": 2, "value": "b"}
]

actual_list = [
    {"id": 2, "value": "b"},
    {"id": 1, "value": "a"}
]

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

### **CLI Usage**

The `Validly` CLI allows you to perform validations from the command line without writing a Python script, making it ideal for CI/CD pipelines and automated testing.

#### **Basic Command**

The core command to run `Validly` is:

`python -m Validly <expected_json_file> <actual_json_file>`

**Example of a successful comparison:**

```sh
$ python -m Validly expected.json actual.json

Comparing 'expected.json' with 'actual.json'...

✅ Validation passed with no differences.
```

**Example of a failed comparison:**

```sh
$ python -m Validly expected.json actual.json

Comparing 'expected.json' with 'actual.json'...

❌ Failures found:
- Field: id, JSON Path: id, Message: Value mismatch: expected '100', got '101'
```

#### **Advanced Usage with Options**

To pass advanced options via the CLI, provide a third JSON file containing the validation rules. This file's structure directly mirrors the options dictionary used in the Python API.

**1. Create an `options.json` file**

This file holds all your validation rules.

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
  "skip_keys": ["user_id", "id"]
}
```

**2. Run the command with the options file**

The CLI will automatically detect and parse the third argument as the options file.

`python -m Validly <expected_json_file> <actual_json_file> <options_json_file>`

-----

### **Contributing**

We welcome contributions\! If you have a feature idea or find a bug, please open an issue or submit a pull request on GitHub.

-----

### **License**

This project is licensed under the MIT License.