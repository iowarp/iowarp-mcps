import pytest
import numpy as np
from unittest.mock import Mock, patch
from src.implementation.bp5_attributes import inspect_attributes


class TestInspectAttributes:
    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_global_attributes_success(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {
            "global_attr1": {"Type": "int32", "Elements": "1"},
            "global_attr2": {"Type": "string", "Elements": "1"},
        }
        mock_stream.available_attributes.return_value = mock_attrs_meta
        mock_stream.read_attribute.side_effect = [
            np.int32(42),
            np.array(["test_string"]),
        ]

        result = inspect_attributes("test.bp")

        mock_stream.available_attributes.assert_called_once_with()
        assert len(result) == 2
        assert result["global_attr1"]["value"] == 42
        assert result["global_attr1"]["Type"] == "int32"
        assert result["global_attr2"]["value"] == ["test_string"]
        assert result["global_attr2"]["Type"] == "string"

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_variable_attributes_success(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {
            "var_attr1": {"Type": "float64", "Elements": "1"},
            "var_attr2": {"Type": "int64", "Elements": "3"},
        }
        mock_stream.available_attributes.return_value = mock_attrs_meta
        mock_stream.read_attribute.side_effect = [
            np.float64(3.14),
            np.array([1, 2, 3], dtype=np.int64),
        ]

        result = inspect_attributes("test.bp", "my_variable")

        mock_stream.available_attributes.assert_called_once_with("my_variable")
        assert len(result) == 2
        assert result["var_attr1"]["value"] == 3.14
        assert result["var_attr1"]["Type"] == "float64"
        assert result["var_attr2"]["value"] == [1, 2, 3]
        assert result["var_attr2"]["Type"] == "int64"

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_no_attributes(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream
        mock_stream.available_attributes.return_value = None

        result = inspect_attributes("test.bp")

        assert result == {"error": "Invalid Variable name or no attributes found"}

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_empty_dict(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream
        mock_stream.available_attributes.return_value = {}

        result = inspect_attributes("test.bp")

        assert result == {"error": "Invalid Variable name or no attributes found"}

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_scalar_conversion(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {"scalar_attr": {"Type": "float32", "Elements": "1"}}
        mock_stream.available_attributes.return_value = mock_attrs_meta

        scalar_array = np.array(5.5, dtype=np.float32)
        mock_stream.read_attribute.return_value = scalar_array

        result = inspect_attributes("test.bp")

        assert result["scalar_attr"]["value"] == 5.5
        assert isinstance(result["scalar_attr"]["value"], float)

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_array_conversion(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {"array_attr": {"Type": "int32", "Elements": "4"}}
        mock_stream.available_attributes.return_value = mock_attrs_meta

        array_data = np.array([[1, 2], [3, 4]], dtype=np.int32)
        mock_stream.read_attribute.return_value = array_data

        result = inspect_attributes("test.bp")

        assert result["array_attr"]["value"] == [1, 2, 3, 4]
        assert isinstance(result["array_attr"]["value"], list)

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_with_elements_metadata(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {"test_attr": {"Type": "double", "Elements": "2"}}
        mock_stream.available_attributes.return_value = mock_attrs_meta
        mock_stream.read_attribute.return_value = np.array([1.1, 2.2])

        result = inspect_attributes("test.bp")

        assert "Elements" in result["test_attr"]
        assert result["test_attr"]["Elements"] == "2"

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_variable_path_construction(self, mock_file_reader):
        mock_stream = Mock()
        mock_file_reader.return_value.__enter__.return_value = mock_stream

        mock_attrs_meta = {"var_attr": {"Type": "string", "Elements": "1"}}
        mock_stream.available_attributes.return_value = mock_attrs_meta
        mock_stream.read_attribute.return_value = "test_value"

        inspect_attributes("test.bp", "my_var")

        mock_stream.read_attribute.assert_called_with("my_var/var_attr")

    @patch("src.implementation.bp5_attributes.FileReader")
    def test_inspect_attributes_file_error(self, mock_file_reader):
        mock_file_reader.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            inspect_attributes("nonexistent.bp")
