import pytest
from unittest.mock import Mock, patch
from src.implementation.bp5_inspect_variables_at_step import inspect_variables_at_step


class TestInspectVariablesAtStep:
    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_at_step_success(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context, mock_step_context]
        mock_stream.current_step.return_value = 1

        mock_variables = {
            "temperature": {
                "Shape": "100,50",
                "Type": "double",
                "Min": "0.0",
                "Max": "100.0",
            }
        }
        mock_stream.available_variables.return_value = mock_variables

        result = inspect_variables_at_step("test.bp", "temperature", 1)

        assert result["variable_name"] == "temperature"
        assert result["Shape"] == "100,50"
        assert result["Type"] == "double"
        assert result["Min"] == "0.0"
        assert result["Max"] == "100.0"

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_at_step_zero(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"pressure": {"Shape": "200,100", "Type": "float"}}
        mock_stream.available_variables.return_value = mock_variables

        result = inspect_variables_at_step("test.bp", "pressure", 0)

        assert result["variable_name"] == "pressure"
        assert result["Shape"] == "200,100"
        assert result["Type"] == "float"

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_not_found_at_step(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"temperature": {"Shape": "100,50", "Type": "double"}}
        mock_stream.available_variables.return_value = mock_variables

        with pytest.raises(
            RuntimeError, match="Error inspecting variable pressure at step 0"
        ):
            inspect_variables_at_step("test.bp", "pressure", 0)

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_step_exceeds_available(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context, mock_step_context]

        result = inspect_variables_at_step("test.bp", "temperature", 5)

        assert "error" in result
        assert "Step 5 exceeds available steps" in result["error"]

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_with_timeout(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"velocity": {"Shape": "50,25", "Type": "float32"}}
        mock_stream.available_variables.return_value = mock_variables

        inspect_variables_at_step("test.bp", "velocity", 0)

        mock_stream.steps.assert_called_once_with(timeout=3)

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_runtime_error(self, mock_stream_class):
        mock_stream_class.side_effect = Exception("File access error")

        with pytest.raises(
            RuntimeError, match="Error inspecting variable temperature at step 0"
        ):
            inspect_variables_at_step("test.bp", "temperature", 0)

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_multiple_steps_iteration(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_contexts = [Mock(), Mock(), Mock()]
        mock_stream.steps.return_value = mock_step_contexts
        mock_stream.current_step.side_effect = [0, 1, 2]

        mock_variables = {"data": {"Shape": "10,10", "Type": "int32"}}
        mock_stream.available_variables.return_value = mock_variables

        result = inspect_variables_at_step("test.bp", "data", 2)

        assert result["variable_name"] == "data"
        assert result["Shape"] == "10,10"
        assert result["Type"] == "int32"

    @patch("builtins.print")
    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_prints_current_step(self, mock_stream_class, mock_print):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"test_var": {"Shape": "5", "Type": "double"}}
        mock_stream.available_variables.return_value = mock_variables

        inspect_variables_at_step("test.bp", "test_var", 0)

        mock_print.assert_called_once_with("Current step is 0")

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_file_not_found(self, mock_stream_class):
        mock_stream_class.side_effect = FileNotFoundError("File not found")

        with pytest.raises(
            RuntimeError, match="Error inspecting variable test_var at step 0"
        ):
            inspect_variables_at_step("nonexistent.bp", "test_var", 0)

    @patch("src.implementation.bp5_inspect_variables_at_step.Stream")
    def test_inspect_variable_empty_variables_dict(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0
        mock_stream.available_variables.return_value = {}

        with pytest.raises(
            RuntimeError, match="Error inspecting variable test_var at step 0"
        ):
            inspect_variables_at_step("test.bp", "test_var", 0)
