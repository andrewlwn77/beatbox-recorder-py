# Beatbox Recorder

<p align="center">
  <img src="https://raw.githubusercontent.com/andrewlwn77/beatbox-recorder/main/docs/assets/beatbox.png" alt="Beatbox Logo" width="400"/>
</p>

## Overview

Beatbox is a lightweight Python library that records and replays function calls, making it perfect for testing, mocking, and debugging. It can capture the results of expensive operations, API calls, or complex computations and play them back instantly, significantly speeding up tests and development cycles.

## Requirements

- Python 3.9 or higher

## Features

- Record and playback function calls with identical results
- Support for both synchronous and asynchronous functions
- Handles complex Python types (sets, tuples, datetimes, custom objects)
- Graceful handling of circular references
- Easy storage management with JSON files
- Simple API with record/playback/bypass modes

## Installation

Using pip:
```bash
pip install beatbox-recorder
```

Using poetry:
```bash
poetry add beatbox-recorder
```

## Quick Start

```python
from beatbox import Beatbox, Mode

# Create a Beatbox instance
bb = Beatbox("my_storage.json")

# Function to wrap
async def fetch_user_data(user_id: int):
    # Expensive API call or database query
    response = await api.get_user(user_id)
    return response.data

# Wrap the function
wrapped_fetch = bb.wrap(fetch_user_data)

# Record mode - will make real API calls and store results
bb.set_mode(Mode.RECORD)
user_data = await wrapped_fetch(123)  # Makes actual API call

# Playback mode - will use stored results without making API calls
bb.set_mode(Mode.PLAYBACK)
user_data = await wrapped_fetch(123)  # Returns stored result instantly

# Bypass mode - makes real API calls without recording
bb.set_mode(Mode.BYPASS)
user_data = await wrapped_fetch(123)  # Makes actual API call
```

## Usage in Tests

```python
import pytest
from beatbox import Beatbox, Mode

@pytest.fixture
def recorder():
    bb = Beatbox("test_storage.json")
    return bb

def test_user_service(recorder):
    user_service = UserService()
    
    # Record actual API responses
    recorder.set_mode(Mode.RECORD)
    result = user_service.get_user(123)
    
    # Use recorded responses in future test runs
    recorder.set_mode(Mode.PLAYBACK)
    cached_result = user_service.get_user(123)
    assert cached_result == result
```

## Storage

Beatbox stores recorded function calls and their results in a JSON file. The storage format is:

```json
{
  "hash_of_function_args": {
    "result": "serialized_result",
    "timestamp": "2024-01-01T00:00:00"
  }
}
```

## Supported Types

Beatbox can handle serialization of:
- Basic Python types (str, int, float, bool, None)
- Collections (list, tuple, dict, set)
- Datetime objects
- Custom objects (serialized as dictionaries)
- Exceptions
- Circular references (replaced with placeholder)
- Range objects

## Error Handling

```python
from beatbox import NoRecordingError, SerializationError

try:
    bb.set_mode(Mode.PLAYBACK)
    result = wrapped_function(123)
except NoRecordingError:
    # No recording found for these arguments
    pass
except SerializationError:
    # Failed to serialize/deserialize result
    pass
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.