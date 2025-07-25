import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.implementation.bp5_list import list_bp5


class TestListBp5:
    def test_list_bp5_default_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()

            (data_dir / "file1.bp").touch()
            (data_dir / "file2.bp5").touch()
            (data_dir / "file3.txt").touch()

            with patch("src.implementation.bp5_list.Path") as mock_path:
                mock_base = Mock()
                mock_path.return_value = mock_base
                mock_base.exists.return_value = True
                mock_base.glob.side_effect = [[Path("file1.bp")], [Path("file2.bp5")]]

                result = list_bp5("data")

                assert len(result) == 2
                assert Path("file1.bp") in result
                assert Path("file2.bp5") in result

    def test_list_bp5_custom_directory(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [
                [Path("/custom/path/test1.bp")],
                [Path("/custom/path/test2.bp5")],
            ]

            result = list_bp5("/custom/path")

            mock_path.assert_called_once_with("/custom/path")
            assert len(result) == 2

    def test_list_bp5_directory_not_found(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = False

            with pytest.raises(
                FileNotFoundError, match="Directory 'nonexistent' not found"
            ):
                list_bp5("nonexistent")

    def test_list_bp5_only_bp_files(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [[Path("file1.bp"), Path("file2.bp")], []]

            result = list_bp5("test_dir")

            assert len(result) == 2
            assert all(str(f).endswith(".bp") for f in result)

    def test_list_bp5_only_bp5_files(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [[], [Path("file1.bp5"), Path("file2.bp5")]]

            result = list_bp5("test_dir")

            assert len(result) == 2
            assert all(str(f).endswith(".bp5") for f in result)

    def test_list_bp5_mixed_files(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [
                [Path("simulation.bp"), Path("output.bp")],
                [Path("data.bp5"), Path("results.bp5")],
            ]

            result = list_bp5("mixed_dir")

            assert len(result) == 4
            bp_files = [f for f in result if str(f).endswith(".bp")]
            bp5_files = [f for f in result if str(f).endswith(".bp5")]
            assert len(bp_files) == 2
            assert len(bp5_files) == 2

    def test_list_bp5_no_files_found(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [[], []]

            result = list_bp5("empty_dir")

            assert result == []

    def test_list_bp5_with_real_temp_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "test_bp_files"
            test_dir.mkdir()

            (test_dir / "file1.bp").touch()
            (test_dir / "file2.bp5").touch()
            (test_dir / "other.txt").touch()

            result = list_bp5(str(test_dir))

            bp_files = [f for f in result if f.name.endswith(".bp")]
            bp5_files = [f for f in result if f.name.endswith(".bp5")]

            assert len(bp_files) == 1
            assert len(bp5_files) == 1
            assert bp_files[0].name == "file1.bp"
            assert bp5_files[0].name == "file2.bp5"

    def test_list_bp5_glob_patterns(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [[], []]

            list_bp5("test_dir")

            calls = mock_base.glob.call_args_list
            assert len(calls) == 2
            assert calls[0][0][0] == "*.bp"
            assert calls[1][0][0] == "*.bp5"

    def test_list_bp5_return_type(self):
        with patch("src.implementation.bp5_list.Path") as mock_path:
            mock_base = Mock()
            mock_path.return_value = mock_base
            mock_base.exists.return_value = True
            mock_base.glob.side_effect = [[Path("test.bp")], [Path("test.bp5")]]

            result = list_bp5("test_dir")

            assert isinstance(result, list)
            assert all(isinstance(item, Path) for item in result)
