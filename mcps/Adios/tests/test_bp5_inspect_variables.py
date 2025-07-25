import pytest
from unittest.mock import Mock, patch
from src.implementation.bp5_inspect_variables import inspect_variables


class TestInspectVariables:
    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_all_variables_success(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {
            "temperature": {
                "Shape": "100,50,25",
                "Type": "double",
                "AvailableStepsCount": "10",
            },
            "pressure": {
                "Shape": "100,50,25",
                "Type": "float",
                "AvailableStepsCount": "10",
            },
        }
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp")

        mock_stream.available_variables.assert_called_once()
        assert len(result) == 2
        assert "temperature" in result
        assert "pressure" in result
        assert result["temperature"]["Shape"] == "100,50,25"
        assert result["temperature"]["Type"] == "double"
        assert result["pressure"]["Type"] == "float"

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_specific_variable_success(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {
            "temperature": {
                "Shape": "100,50,25",
                "Type": "double",
                "AvailableStepsCount": "10",
            },
            "pressure": {
                "Shape": "100,50,25",
                "Type": "float",
                "AvailableStepsCount": "10",
            },
        }
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp", "temperature")

        assert len(result) == 1
        assert "temperature" in result
        assert "pressure" not in result
        assert result["temperature"]["Shape"] == "100,50,25"
        assert result["temperature"]["Type"] == "double"

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variable_not_found(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {
            "temperature": {
                "Shape": "100,50,25",
                "Type": "double",
                "AvailableStepsCount": "10",
            }
        }
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp", "nonexistent_var")

        assert result["error"] == "Variable 'nonexistent_var' not found in file."

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_empty_file(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_stream.available_variables.return_value = {}

        result = inspect_variables("test.bp")

        assert result == {}

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_with_additional_params(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {
            "velocity": {
                "Shape": "1000,500",
                "Type": "float32",
                "AvailableStepsCount": "5",
                "Min": "0.0",
                "Max": "100.0",
                "CustomParam": "CustomValue",
            }
        }
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp")

        assert result["velocity"]["Min"] == "0.0"
        assert result["velocity"]["Max"] == "100.0"
        assert result["velocity"]["CustomParam"] == "CustomValue"

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_metadata_conversion(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_adios_params = {
            "Shape": "10,20",
            "Type": "int32",
            "AvailableStepsCount": "3",
        }

        mock_vars_info = {"data": mock_adios_params}
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp")

        assert isinstance(result["data"], dict)
        assert result["data"]["Shape"] == "10,20"
        assert result["data"]["Type"] == "int32"

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_file_error(self, mock_file_reader):
        mock_file_reader.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            inspect_variables("nonexistent.bp")

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_default_parameter(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {"test_var": {"Shape": "5,5", "Type": "double"}}
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp", None)

        assert len(result) == 1
        assert "test_var" in result

    @patch("src.implementation.bp5_inspect_variables.FileReader")
    def test_inspect_variables_case_sensitive(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_vars_info = {"Temperature": {"Shape": "100", "Type": "double"}}
        mock_stream.available_variables.return_value = mock_vars_info

        result = inspect_variables("test.bp", "temperature")

        assert result["error"] == "Variable 'temperature' not found in file."
