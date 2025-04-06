from enum import Enum
import json
import hashlib
import asyncio
import os
import inspect
from typing import Any, Callable, Dict, TypeVar, Set
from datetime import datetime
from functools import wraps

T = TypeVar('T', bound=Callable[..., Any])

class Mode(str, Enum):
    BYPASS = "BYPASS"
    RECORD = "RECORD"
    PLAYBACK = "PLAYBACK"

class BeatboxError(Exception):
    pass

class NoRecordingError(BeatboxError):
    pass

class SerializationError(BeatboxError):
    pass

class Beatbox:
    def __init__(self, storage_file: str = "beatbox_storage.json"):
        self.storage_file = storage_file
        self.storage: Dict[str, Any] = {}
        self.mode = Mode.BYPASS
        self._load_storage()
        
    def set_mode(self, mode: str) -> None:
        """Set the operating mode."""
        try:
            self.mode = Mode(mode)
        except ValueError:
            raise BeatboxError(f"Invalid mode: {mode}")
            
    def _load_storage(self) -> None:
        """Load saved recordings."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    self.storage = json.load(f)
            except json.JSONDecodeError:
                # Backup corrupted file
                backup = f"{self.storage_file}.backup.{int(datetime.now().timestamp())}"
                os.rename(self.storage_file, backup)
                print(f"Storage file was corrupted. Backed up to {backup} and created new storage.")
                self.storage = {}
                
    def _save_storage(self) -> None:
        """Save recordings to disk."""
        with open(self.storage_file, 'w') as f:
            json.dump(self.storage, f, indent=2)
            
    def _make_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Create a unique key for the function call."""
        def make_hashable(obj):
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            if isinstance(obj, (list, tuple)):
                return tuple(make_hashable(x) for x in obj)
            if isinstance(obj, dict):
                return tuple(sorted((str(k), make_hashable(v)) for k, v in obj.items()))
            if isinstance(obj, set):
                return tuple(sorted(make_hashable(x) for x in obj))
            return str(obj)

        # For regular functions and methods, use the function name
        # For lambdas and other callables, just use the arguments
        if hasattr(func, '__name__') and not func.__name__ == '<lambda>':
            call_repr = (func.__name__, make_hashable((args, kwargs)))
        else:
            call_repr = make_hashable((args, kwargs))
            
        return hashlib.md5(str(call_repr).encode()).hexdigest()

    def _serialize(self, obj: Any, memo: Set = None) -> Any:
        """Convert Python objects to JSON-serializable format."""
        if memo is None:
            memo = set()
            
        # Handle circular references
        obj_id = id(obj)
        if obj_id in memo:
            return "[Circular Reference]"
        memo.add(obj_id)
        
        try:
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            if isinstance(obj, (list, tuple)):
                return {
                    "__type": "tuple" if isinstance(obj, tuple) else "list",
                    "items": [self._serialize(x, memo) for x in obj]
                }
            if isinstance(obj, dict):
                serialized_dict = {}
                for k, v in obj.items():
                    if isinstance(k, (tuple, list, set, dict)):
                        key = {
                            "__type": type(k).__name__,
                            "value": self._serialize(k, memo)
                        }
                        serialized_dict[json.dumps(key)] = self._serialize(v, memo)
                    else:
                        serialized_dict[str(k)] = self._serialize(v, memo)
                return serialized_dict
            if isinstance(obj, set):
                return {
                    "__type": "set",
                    "items": [self._serialize(x, memo) for x in sorted(obj)]
                }
            if isinstance(obj, datetime):
                return {"__type": "datetime", "value": obj.isoformat()}
            if isinstance(obj, Exception):
                return {
                    "__type": "error",
                    "name": obj.__class__.__name__, 
                    "args": self._serialize(obj.args, memo)
                }
            if isinstance(obj, range):
                return {
                    "__type": "range",
                    "start": obj.start,
                    "stop": obj.stop,
                    "step": obj.step
                }
            if hasattr(obj, '__dict__'):
                return {
                    "__type": "object",
                    "attrs": self._serialize(obj.__dict__, memo)
                }
            return str(obj)
        finally:
            memo.remove(obj_id)
        
    def _deserialize(self, obj: Any) -> Any:
        """Convert serialized format back to Python objects."""
        if not isinstance(obj, dict):
            if isinstance(obj, list):
                return [self._deserialize(x) for x in obj]
            return obj
            
        # Handle special type markers
        if "__type" in obj:
            typ = obj["__type"]
            if typ == "set":
                return set(self._deserialize(x) for x in obj["items"])
            if typ == "tuple":
                return tuple(self._deserialize(x) for x in obj["items"])
            if typ == "list":
                return [self._deserialize(x) for x in obj["items"]]
            if typ == "datetime":
                return datetime.fromisoformat(obj["value"])
            if typ == "error":
                # Recreate the error with best effort
                return ValueError(*self._deserialize(obj["args"]))
            if typ == "range":
                return range(obj["start"], obj["stop"], obj.get("step", 1))
            if typ == "object":
                # Return as dictionary since we can't recreate the original class
                return self._deserialize(obj["attrs"])

        # Handle dictionary with possible special keys
        result = {}
        for k, v in obj.items():
            try:
                # Try to parse the key as a JSON string (for special types)
                key_obj = json.loads(k)
                if isinstance(key_obj, dict) and "__type" in key_obj:
                    key = self._deserialize(key_obj["value"])
                else:
                    key = k
            except json.JSONDecodeError:
                key = k
            result[key] = self._deserialize(v)
        return result

    def wrap(self, func: T) -> T:
        """Wrap a function to record/replay its calls."""
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = self._make_key(func, args, kwargs)
                
                if not isinstance(self.mode, Mode):
                    raise BeatboxError(f"Invalid mode: {self.mode}")
                    
                if self.mode == Mode.BYPASS:
                    return await func(*args, **kwargs)
                    
                if self.mode == Mode.RECORD:
                    result = await func(*args, **kwargs)
                    try:
                        self.storage[key] = self._serialize(result)
                        self._save_storage()
                    except Exception as e:
                        print(f"Warning: Failed to record result: {e}")
                    return result
                    
                # PLAYBACK mode
                if key not in self.storage:
                    raise NoRecordingError(f"No recorded result found for arguments: {json.dumps((args, kwargs))}")
                return self._deserialize(self.storage[key])
                
            return async_wrapper
            
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = self._make_key(func, args, kwargs)
                
                if not isinstance(self.mode, Mode):
                    raise BeatboxError(f"Invalid mode: {self.mode}")
                    
                if self.mode == Mode.BYPASS:
                    return func(*args, **kwargs)
                    
                if self.mode == Mode.RECORD:
                    result = func(*args, **kwargs)
                    try:
                        self.storage[key] = self._serialize(result)
                        self._save_storage()
                    except Exception as e:
                        print(f"Warning: Failed to record result: {e}")
                    return result
                    
                # PLAYBACK mode
                if key not in self.storage:
                    raise NoRecordingError(f"No recorded result found for arguments: {json.dumps((args, kwargs))}")
                return self._deserialize(self.storage[key])
                
            return sync_wrapper