import pytest
import asyncio
import os
from datetime import datetime
from beatbox_recorder import Beatbox, Mode, NoRecordingError, BeatboxError

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

# All existing test functions remain the same...

@pytest.mark.asyncio
class TestBeatbox:
    # All existing test methods remain...

    async def test_identical_signature_functions(self, beatbox):
        """Test that functions with identical signatures but different names are stored separately."""
        def func1(x: int) -> int:
            return x + 1

        def func2(x: int) -> int:
            return x + 2

        beatbox.set_mode(Mode.RECORD)
        wrapped1 = beatbox.wrap(func1)
        wrapped2 = beatbox.wrap(func2)

        # Record both functions
        result1 = wrapped1(5)
        result2 = wrapped2(5)
        assert result1 == 6
        assert result2 == 7
        await asyncio.sleep(0.1)  # Allow async save

        # Playback - ensure they return different results
        beatbox.set_mode(Mode.PLAYBACK)
        assert wrapped1(5) == 6
        assert wrapped2(5) == 7

    async def test_lambda_functions(self, beatbox):
        """Test that lambda functions are handled by their arguments only."""
        lambda1 = lambda x: x + 1
        lambda2 = lambda x: x + 2  # Different lambda, same signature

        beatbox.set_mode(Mode.RECORD)
        wrapped1 = beatbox.wrap(lambda1)
        wrapped2 = beatbox.wrap(lambda2)

        # Record both functions with different arguments
        result1 = wrapped1(5)
        result2 = wrapped2(6)
        assert result1 == 6
        assert result2 == 8
        await asyncio.sleep(0.1)

        # Playback - verify they share cache based on arguments
        beatbox.set_mode(Mode.PLAYBACK)
        assert wrapped1(5) == 6  # Same args as first call
        assert wrapped2(6) == 8  # Same args as second call

        # Verify that using the same args returns the first recorded result
        assert wrapped2(5) == 6  # Same args as first call

    async def test_method_functions(self, beatbox):
        """Test that class methods are handled correctly."""
        class TestClass:
            def method1(self, x):
                return x + 1

            def method2(self, x):
                return x + 2

        obj = TestClass()
        
        beatbox.set_mode(Mode.RECORD)
        wrapped1 = beatbox.wrap(obj.method1)
        wrapped2 = beatbox.wrap(obj.method2)

        # Record both methods
        result1 = wrapped1(5)
        result2 = wrapped2(5)
        assert result1 == 6
        assert result2 == 7
        await asyncio.sleep(0.1)

        # Playback - ensure they return different results
        beatbox.set_mode(Mode.PLAYBACK)
        assert wrapped1(5) == 6
        assert wrapped2(5) == 7

    async def test_instance_method_consistency(self, beatbox):
        """Test that instance methods with the same name but different args cache separately."""
        class TestClass:
            def __init__(self, id):
                self.id = id

            def method(self, x):
                return x + self.id

        obj1 = TestClass(1)
        obj2 = TestClass(2)

        beatbox.set_mode(Mode.RECORD)
        wrapped1 = beatbox.wrap(obj1.method)
        wrapped2 = beatbox.wrap(obj2.method)

        # Record with different arguments
        result1 = wrapped1(1)  # Total: 2
        result2 = wrapped2(2)  # Total: 4
        assert result1 == 2
        assert result2 == 4
        await asyncio.sleep(0.1)

        # Playback - verify cache is based on method name + args
        beatbox.set_mode(Mode.PLAYBACK)
        assert wrapped1(1) == 2  # Same args as first call
        assert wrapped2(2) == 4  # Same args as second call

    async def test_nested_function_wrapping(self, beatbox):
        """Test that nested functions with the same name cache based on arguments."""
        def create_function(increment):
            def inner(x):
                return x + increment
            return inner

        func1 = create_function(1)
        func2 = create_function(2)

        beatbox.set_mode(Mode.RECORD)
        wrapped1 = beatbox.wrap(func1)
        wrapped2 = beatbox.wrap(func2)

        # Record with different arguments
        result1 = wrapped1(1)  # Total: 2
        result2 = wrapped2(2)  # Total: 4
        assert result1 == 2
        assert result2 == 4
        await asyncio.sleep(0.1)

        # Playback - verify cache is based on function name + args
        beatbox.set_mode(Mode.PLAYBACK)
        assert wrapped1(1) == 2  # Same args as first call
        assert wrapped2(2) == 4  # Same args as second call