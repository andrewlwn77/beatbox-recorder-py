import pytest
import asyncio
import os
from datetime import datetime
from beatbox import Beatbox, Mode, NoRecordingError, BeatboxError

TEST_STORAGE_FILE = "test_storage.json"

@pytest.fixture
async def beatbox():
    bb = Beatbox(TEST_STORAGE_FILE)
    yield bb
    # Cleanup
    try:
        os.remove(TEST_STORAGE_FILE)
    except FileNotFoundError:
        pass

# Test functions
def sync_add(a: int, b: int) -> int:
    return a + b

async def async_add(a: int, b: int) -> int:
    await asyncio.sleep(0.01)
    return a + b

def sync_error():
    raise ValueError("Sync error")

async def async_error():
    await asyncio.sleep(0.01)
    raise ValueError("Async error")

@pytest.mark.asyncio
class TestBeatbox:
    async def test_sync_bypass(self, beatbox):
        beatbox.set_mode(Mode.BYPASS)
        wrapped = beatbox.wrap(sync_add)
        assert wrapped(2, 3) == 5

    async def test_async_bypass(self, beatbox):
        beatbox.set_mode(Mode.BYPASS)
        wrapped = beatbox.wrap(async_add)
        result = await wrapped(2, 3)
        assert result == 5

    async def test_sync_record_playback(self, beatbox):
        # Record
        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(sync_add)
        result = wrapped(2, 3)
        assert result == 5
        await asyncio.sleep(0.1)  # Allow async save to complete

        # Playback
        beatbox.set_mode(Mode.PLAYBACK)
        result = wrapped(2, 3)
        assert result == 5

    async def test_async_record_playback(self, beatbox):
        # Record
        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(async_add)
        result = await wrapped(2, 3)
        assert result == 5

        # Playback
        beatbox.set_mode(Mode.PLAYBACK)
        result = await wrapped(2, 3)
        assert result == 5

    async def test_sync_error_handling(self, beatbox):
        beatbox.set_mode(Mode.BYPASS)
        wrapped = beatbox.wrap(sync_error)
        with pytest.raises(ValueError, match="Sync error"):
            wrapped()

    async def test_async_error_handling(self, beatbox):
        beatbox.set_mode(Mode.BYPASS)
        wrapped = beatbox.wrap(async_error)
        with pytest.raises(ValueError, match="Async error"):
            await wrapped()

    async def test_missing_recording(self, beatbox):
        beatbox.set_mode(Mode.PLAYBACK)
        wrapped = beatbox.wrap(sync_add)
        with pytest.raises(NoRecordingError):
            wrapped(4, 5)

    async def test_special_types(self, beatbox):
        class CustomObject:
            def __init__(self, value):
                self.value = value

        def func_with_special_types():
            return {
                "set": {1, 2, 3},
                "date": datetime.now(),
                "nested": {"set": {4, 5, 6}},
                "complex_dict": {
                    (1, 2): "tuple_key",
                    range(3): "range_key",
                },
                "custom": CustomObject(42),
                "tuple": (1, 2, 3),
                "range": range(5),
                "error": ValueError("test error")
            }

        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(func_with_special_types)
        result = wrapped()
        await asyncio.sleep(0.1)  # Allow async save to complete

        beatbox.set_mode(Mode.PLAYBACK)
        playback_result = wrapped()
        
        # Basic types
        assert isinstance(playback_result["set"], set)
        assert isinstance(playback_result["date"], datetime)
        assert isinstance(playback_result["nested"]["set"], set)
        
        # Complex dictionary keys
        assert isinstance(playback_result["complex_dict"], dict)
        assert any(isinstance(k, tuple) for k in playback_result["complex_dict"].keys())
        
        # Additional Python types
        assert isinstance(playback_result["tuple"], tuple)
        assert isinstance(playback_result["range"], range)
        assert isinstance(playback_result["error"], ValueError)
        
        # Custom object (falls back to dict since test module isn't importable)
        assert isinstance(playback_result["custom"], dict)
        assert playback_result["custom"]["value"] == 42

    async def test_invalid_mode(self, beatbox):
        beatbox.mode = "INVALID"  # type: ignore
        wrapped = beatbox.wrap(sync_add)
        with pytest.raises(BeatboxError, match="Invalid mode"):
            wrapped(1, 2)

    async def test_corrupted_storage(self, beatbox):
        # Write corrupted JSON
        with open(TEST_STORAGE_FILE, "w") as f:
            f.write("corrupted json")

        beatbox.set_mode(Mode.PLAYBACK)
        wrapped = beatbox.wrap(sync_add)
        # Should handle corrupted file by creating backup and empty storage
        with pytest.raises(NoRecordingError):
            wrapped(1, 2)

    async def test_undefined_arguments(self, beatbox):
        def func_with_optional(a: int = None):
            return a if a is not None else 0

        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(func_with_optional)
        result = wrapped()
        assert result == 0
        await asyncio.sleep(0.1)

        beatbox.set_mode(Mode.PLAYBACK)
        result = wrapped()
        assert result == 0

    async def test_object_arguments(self, beatbox):
        def func_with_object(obj: dict):
            return obj["x"] + obj["y"]

        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(func_with_object)
        result = wrapped({"x": 1, "y": 2})
        assert result == 3
        await asyncio.sleep(0.1)

        beatbox.set_mode(Mode.PLAYBACK)
        result = wrapped({"x": 1, "y": 2})
        assert result == 3

    async def test_array_arguments(self, beatbox):
        def func_with_array(arr: list):
            return sum(arr)

        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(func_with_array)
        result = wrapped([1, 2, 3])
        assert result == 6
        await asyncio.sleep(0.1)

        beatbox.set_mode(Mode.PLAYBACK)
        result = wrapped([1, 2, 3])
        assert result == 6

    async def test_non_serializable_results(self, beatbox):
        def func_with_circular_ref():
            obj = {"data": set([1, 2, 3])}
            obj["self"] = obj  # Create circular reference
            return obj

        beatbox.set_mode(Mode.RECORD)
        wrapped = beatbox.wrap(func_with_circular_ref)
        result = wrapped()
        
        # Verify the result structure
        assert isinstance(result["data"], set)
        assert result["self"] is result  # Original circular reference preserved
        await asyncio.sleep(0.1)  # Allow async save

        beatbox.set_mode(Mode.PLAYBACK)
        playback_result = wrapped()
        
        # Check that we got a serialized version with placeholder
        assert isinstance(playback_result["data"], set)
        assert playback_result["self"] == "[Circular Reference]"

    async def test_multiple_storage_instances(self, beatbox):
        # Test with two separate storage files
        beatbox1 = Beatbox("storage1.json")
        beatbox2 = Beatbox("storage2.json")

        wrapped1 = beatbox1.wrap(sync_add)
        wrapped2 = beatbox2.wrap(sync_add)

        # Record
        beatbox1.set_mode(Mode.RECORD)
        beatbox2.set_mode(Mode.RECORD)
        result1 = wrapped1(1, 2)
        result2 = wrapped2(3, 4)
        assert result1 == 3
        assert result2 == 7
        await asyncio.sleep(0.1)

        # Playback
        beatbox1.set_mode(Mode.PLAYBACK)
        beatbox2.set_mode(Mode.PLAYBACK)
        assert wrapped1(1, 2) == 3
        assert wrapped2(3, 4) == 7

        # Cleanup
        for file in ["storage1.json", "storage2.json"]:
            try:
                os.remove(file)
            except FileNotFoundError:
                pass