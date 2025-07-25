import pytest
import numpy as np
from unittest.mock import Mock, patch
from src.implementation.bp5_read_variable_at_step import read_variable_at_step


class TestReadVariableAtStep:
    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_scalar_success(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context, mock_step_context]
        mock_stream.current_step.side_effect = [0, 1]

        mock_variables = {"temperature": {"Type": "double", "Shape": ""}}
        mock_stream.available_variables.return_value = mock_variables

        scalar_value = np.float64(25.5)
        mock_stream.read.return_value = scalar_value

        result = read_variable_at_step("test.bp", "temperature", 1)

        assert result == 25.5
        assert isinstance(result, float)
        mock_stream.read.assert_called_once_with("temperature")

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_array_success(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"pressure": {"Type": "float", "Shape": "2,2"}}
        mock_stream.available_variables.return_value = mock_variables

        array_value = np.array([[1.1, 2.2], [3.3, 4.4]], dtype=np.float32)
        mock_stream.read.return_value = array_value

        result = read_variable_at_step("test.bp", "pressure", 0)

        # Use pytest.approx for floating point comparisons
        assert result == pytest.approx([1.1, 2.2, 3.3, 4.4], rel=1e-6)
        assert isinstance(result, list)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_not_found(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"temperature": {"Type": "double", "Shape": ""}}
        mock_stream.available_variables.return_value = mock_variables

        with pytest.raises(ValueError, match="Variable 'pressure' not in step 0"):
            read_variable_at_step("test.bp", "pressure", 0)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_step_not_found(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        with pytest.raises(ValueError, match="Step 5 not found in file 'test.bp'"):
            read_variable_at_step("test.bp", "temperature", 5)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_zero_dimensional_array(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"scalar_var": {"Type": "int32", "Shape": ""}}
        mock_stream.available_variables.return_value = mock_variables

        zero_d_array = np.array(42, dtype=np.int32)
        mock_stream.read.return_value = zero_d_array

        result = read_variable_at_step("test.bp", "scalar_var", 0)

        assert result == 42
        assert isinstance(result, int)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_multiple_steps(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_contexts = [Mock(), Mock(), Mock()]
        mock_stream.steps.return_value = mock_step_contexts
        mock_stream.current_step.side_effect = [0, 1, 2]

        mock_variables = {"velocity": {"Type": "double", "Shape": "3"}}
        mock_stream.available_variables.return_value = mock_variables

        array_value = np.array([10.0, 20.0, 30.0], dtype=np.float64)
        mock_stream.read.return_value = array_value

        result = read_variable_at_step("test.bp", "velocity", 2)

        assert result == [10.0, 20.0, 30.0]

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_numpy_generic_type(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"test_var": {"Type": "uint64", "Shape": ""}}
        mock_stream.available_variables.return_value = mock_variables

        numpy_scalar = np.uint64(123456789)
        mock_stream.read.return_value = numpy_scalar

        result = read_variable_at_step("test.bp", "test_var", 0)

        assert result == 123456789
        assert isinstance(result, int)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_1d_array(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"data_1d": {"Type": "int32", "Shape": "5"}}
        mock_stream.available_variables.return_value = mock_variables

        array_1d = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        mock_stream.read.return_value = array_1d

        result = read_variable_at_step("test.bp", "data_1d", 0)

        assert result == [1, 2, 3, 4, 5]
        assert isinstance(result, list)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_3d_array_flattened(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0

        mock_variables = {"data_3d": {"Type": "float64", "Shape": "2,2,2"}}
        mock_stream.available_variables.return_value = mock_variables

        array_3d = np.array(
            [[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]], dtype=np.float64
        )
        mock_stream.read.return_value = array_3d

        result = read_variable_at_step("test.bp", "data_3d", 0)

        assert result == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        assert isinstance(result, list)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_file_error(self, mock_stream_class):
        mock_stream_class.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            read_variable_at_step("nonexistent.bp", "temperature", 0)

    @patch("src.implementation.bp5_read_variable_at_step.adios2.Stream")
    def test_read_variable_empty_variables_dict(self, mock_stream_class):
        mock_stream = Mock()
        mock_stream_class.return_value.__enter__.return_value = mock_stream

        mock_step_context = Mock()
        mock_stream.steps.return_value = [mock_step_context]
        mock_stream.current_step.return_value = 0
        mock_stream.available_variables.return_value = {}

        with pytest.raises(ValueError, match="Variable 'test_var' not in step 0"):
            read_variable_at_step("test.bp", "test_var", 0)
