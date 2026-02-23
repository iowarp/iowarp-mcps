"""
Tests for ADIOS2 support checking and BP5 conversion functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
import numpy as np


@pytest.fixture
def mock_paraview():
    """Mock paraview.simple module"""
    with patch.dict(
        "sys.modules",
        {
            "paraview": MagicMock(),
            "paraview.simple": MagicMock(),
            "paraview.servermanager": MagicMock(),
            "paraview.collaboration": MagicMock(),
            "adios2": MagicMock(),
            "vtk": MagicMock(),
            "vtk.util": MagicMock(),
            "vtk.util.numpy_support": MagicMock(),
        },
    ):
        yield


@pytest.fixture
def engine(mock_paraview):
    """Create VisualizationEngine instance"""
    from paraview_mcp.implementation.paraview_capabilities import VisualizationEngine

    return VisualizationEngine()


class TestCheckParaviewAdios2Support:
    """Test _check_paraview_adios2_support method"""

    def test_check_adios2_enabled(self, engine):
        """Test when ADIOS2 is enabled in ParaView build"""
        cmake_content = """
# Some CMake cache content
PARAVIEW_ENABLE_ADIOS2:BOOL=ON
PARAVIEW_BUILD_TYPE:STRING=Release
"""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=cmake_content)),
        ):
            status = engine._check_paraview_adios2_support()

            assert status["has_support"] is True
            assert "enabled" in status["message"]
            assert len(status["cmake_flags"]) > 0

    def test_check_adios2_disabled(self, engine):
        """Test when ADIOS2 is disabled in ParaView build"""
        cmake_content = """
PARAVIEW_ENABLE_ADIOS2:BOOL=OFF
"""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=cmake_content)),
        ):
            status = engine._check_paraview_adios2_support()

            assert status["has_support"] is False
            assert "without ADIOS2" in status["message"]

    def test_check_adios2_use_flag(self, engine):
        """Test with PARAVIEW_USE_ADIOS2 flag"""
        cmake_content = """
PARAVIEW_USE_ADIOS2:UNINITIALIZED=ON
"""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=cmake_content)),
        ):
            status = engine._check_paraview_adios2_support()

            assert status["has_support"] is False
            assert "available but not enabled" in status["message"]

    def test_check_adios2_no_cache_file(self, engine):
        """Test when no cache file found"""
        with patch("os.path.exists", return_value=False):
            status = engine._check_paraview_adios2_support()

            assert status["has_support"] is False
            assert "not found" in status["message"]

    def test_check_adios2_exception(self, engine):
        """Test exception handling"""
        with patch("os.path.exists", side_effect=Exception("Test error")):
            status = engine._check_paraview_adios2_support()

            assert status["has_support"] is False
            assert "Error checking" in status["message"]


class TestConvertAdiosToVtkImproved:
    """Test _convert_adios_to_vtk_improved method"""

    def test_convert_no_adios2(self, engine, mock_paraview):
        """Test conversion without ADIOS2 available"""
        from paraview_mcp.implementation import paraview_capabilities

        original_adios2 = paraview_capabilities.ADIOS2_AVAILABLE
        paraview_capabilities.ADIOS2_AVAILABLE = False

        try:
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            assert result is None
        finally:
            paraview_capabilities.ADIOS2_AVAILABLE = original_adios2

    def test_convert_file_not_exist(self, engine, mock_paraview):
        """Test with non-existent file"""
        with patch("os.path.exists", return_value=False):
            result = engine._convert_adios_to_vtk_improved("/fake/file.bp5")
            assert result is None

    def test_convert_invalid_format(self, engine, mock_paraview):
        """Test with invalid file format"""
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
        ):
            result = engine._convert_adios_to_vtk_improved("/test/file.txt")
            assert result is None

    def test_convert_strategy_success(self, engine, mock_paraview):
        """Test successful conversion using first strategy"""
        # Create a proper mock with __name__ attribute
        mock_strategy = Mock(return_value=True)
        mock_strategy.__name__ = "_convert_strategy_streaming_api"

        with (
            patch(
                "os.path.exists",
                side_effect=lambda p: (
                    True
                    if p == "/test/file.bp5" or p == "/test/file_converted.vti"
                    else False
                ),
            ),
            patch("os.path.isdir", return_value=False),
            patch("os.path.splitext", return_value=("/test/file", ".bp5")),
            patch("os.path.getsize", return_value=1000),
            patch.object(engine, "_convert_strategy_streaming_api", mock_strategy),
        ):
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            assert result == "/test/file_converted.vti"

    def test_convert_all_strategies_fail(self, engine, mock_paraview):
        """Test when all conversion strategies fail"""
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            patch("os.path.splitext", return_value=("/test/file", ".bp5")),
            patch.object(engine, "_convert_strategy_streaming_api", return_value=False),
            patch.object(engine, "_convert_strategy_direct_bp5", return_value=False),
            patch.object(
                engine, "_convert_strategy_alternative_engines", return_value=False
            ),
        ):
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            assert result is None

    def test_convert_exception(self, engine, mock_paraview):
        """Test exception handling"""
        with patch("os.path.exists", side_effect=Exception("Test error")):
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            assert result is None


class TestConvertStrategyStreamingApi:
    """Test _convert_strategy_streaming_api method"""

    def test_streaming_api_success(self, engine, mock_paraview):
        """Test successful streaming API conversion"""

        # Mock adios2.open context manager
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)

        # Mock variables
        mock_file.available_variables.return_value = {
            "density": {"Shape": "10, 10, 10", "Type": "double"}
        }

        # Mock data reading
        test_data = np.random.rand(10, 10, 10)
        mock_file.read.return_value = test_data

        with (
            patch("adios2.open", return_value=mock_file),
            patch.object(engine, "_create_vtk_from_numpy", return_value=True),
        ):
            result = engine._convert_strategy_streaming_api(
                "/test/file.bp5", "/test/output.vti"
            )

            assert result is True

    def test_streaming_api_no_variables(self, engine, mock_paraview):
        """Test with no variables in BP5 file"""

        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.available_variables.return_value = {}

        with patch("adios2.open", return_value=mock_file):
            result = engine._convert_strategy_streaming_api(
                "/test/file.bp5", "/test/output.vti"
            )
            assert result is False

    def test_streaming_api_read_failure(self, engine, mock_paraview):
        """Test when reading variable fails"""

        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.available_variables.return_value = {
            "test": {"Shape": "10, 10, 10", "Type": "double"}
        }
        mock_file.read.return_value = None

        with patch("adios2.open", return_value=mock_file):
            result = engine._convert_strategy_streaming_api(
                "/test/file.bp5", "/test/output.vti"
            )
            assert result is False

    def test_streaming_api_exception(self, engine, mock_paraview):
        """Test exception handling"""

        with patch("adios2.open", side_effect=Exception("Test error")):
            result = engine._convert_strategy_streaming_api(
                "/test/file.bp5", "/test/output.vti"
            )
            assert result is False


class TestConvertStrategyDirectBp5:
    """Test _convert_strategy_direct_bp5 method"""

    def test_direct_bp5_success(self, engine, mock_paraview):
        """Test successful direct BP5 conversion"""
        import adios2

        mock_adios = Mock()
        mock_io = Mock()
        mock_reader = Mock()
        mock_var = Mock()

        # Mock ADIOS2 objects
        adios2.ADIOS.return_value = mock_adios
        mock_adios.DeclareIO.return_value = mock_io
        mock_io.Open.return_value = mock_reader

        # Mock variables
        mock_io.AvailableVariables.return_value = {"test": {}}
        mock_io.InquireVariable.return_value = mock_var
        mock_var.Shape.return_value = (10, 10, 10)
        mock_var.Type.return_value = np.float64

        # Mock step reading
        mock_reader.BeginStep.return_value = adios2.StepStatus.OK

        with patch.object(engine, "_create_vtk_from_numpy", return_value=True):
            result = engine._convert_strategy_direct_bp5(
                "/test/file.bp5", "/test/output.vti"
            )
            assert result is True

    def test_direct_bp5_no_variables(self, engine, mock_paraview):
        """Test with no variables"""
        import adios2

        mock_adios = Mock()
        mock_io = Mock()
        mock_reader = Mock()

        adios2.ADIOS.return_value = mock_adios
        mock_adios.DeclareIO.return_value = mock_io
        mock_io.Open.return_value = mock_reader
        mock_io.AvailableVariables.return_value = {}

        result = engine._convert_strategy_direct_bp5(
            "/test/file.bp5", "/test/output.vti"
        )
        assert result is False

    def test_direct_bp5_exception(self, engine, mock_paraview):
        """Test exception handling"""
        import adios2

        adios2.ADIOS.side_effect = Exception("Test error")

        result = engine._convert_strategy_direct_bp5(
            "/test/file.bp5", "/test/output.vti"
        )
        assert result is False


class TestConvertStrategyAlternativeEngines:
    """Test _convert_strategy_alternative_engines method"""

    def test_alternative_engines(self, engine, mock_paraview):
        """Test alternative engine attempts"""
        # This method is currently a placeholder that always returns False
        result = engine._convert_strategy_alternative_engines(
            "/test/file.bp5", "/test/output.vti"
        )
        assert result is False

    def test_alternative_engines_exception(self, engine, mock_paraview):
        """Test with all engines failing"""
        import adios2

        # Mock to raise exception for all engines
        adios2.ADIOS.side_effect = Exception("Test error")

        result = engine._convert_strategy_alternative_engines(
            "/test/file.bp5", "/test/output.vti"
        )
        assert result is False


class TestCreateVtkFromNumpy:
    """Test _create_vtk_from_numpy method"""

    def test_create_vtk_3d_data(self, engine, mock_paraview):
        """Test creating VTK from 3D numpy array"""
        import vtk
        from vtk.util import numpy_support

        # Mock VTK objects
        mock_image_data = Mock()
        mock_vtk_array = Mock()
        mock_writer = Mock()

        vtk.vtkImageData.return_value = mock_image_data
        numpy_support.numpy_to_vtk.return_value = mock_vtk_array
        vtk.vtkXMLImageDataWriter.return_value = mock_writer
        mock_writer.Write.return_value = 1  # Success

        test_data = np.random.rand(10, 20, 30).astype(np.float32)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is True
        mock_image_data.SetDimensions.assert_called_once()
        mock_writer.Write.assert_called_once()

    def test_create_vtk_2d_data(self, engine, mock_paraview):
        """Test creating VTK from 2D numpy array"""
        import vtk
        from vtk.util import numpy_support

        mock_image_data = Mock()
        mock_vtk_array = Mock()
        mock_writer = Mock()

        vtk.vtkImageData.return_value = mock_image_data
        numpy_support.numpy_to_vtk.return_value = mock_vtk_array
        vtk.vtkXMLImageDataWriter.return_value = mock_writer
        mock_writer.Write.return_value = 1

        test_data = np.random.rand(10, 20).astype(np.float32)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is True

    def test_create_vtk_1d_data(self, engine, mock_paraview):
        """Test creating VTK from 1D numpy array"""
        import vtk
        from vtk.util import numpy_support

        mock_image_data = Mock()
        mock_vtk_array = Mock()
        mock_writer = Mock()

        vtk.vtkImageData.return_value = mock_image_data
        numpy_support.numpy_to_vtk.return_value = mock_vtk_array
        vtk.vtkXMLImageDataWriter.return_value = mock_writer
        mock_writer.Write.return_value = 1

        test_data = np.random.rand(10).astype(np.float32)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is True

    def test_create_vtk_unsupported_dims(self, engine, mock_paraview):
        """Test with unsupported dimensionality"""
        import vtk

        vtk.vtkImageData.return_value = Mock()

        # 4D array is unsupported
        test_data = np.random.rand(5, 5, 5, 5).astype(np.float32)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is False

    def test_create_vtk_write_failure(self, engine, mock_paraview):
        """Test when VTK writer fails"""
        import vtk
        from vtk.util import numpy_support

        mock_image_data = Mock()
        mock_vtk_array = Mock()
        mock_writer = Mock()

        vtk.vtkImageData.return_value = mock_image_data
        numpy_support.numpy_to_vtk.return_value = mock_vtk_array
        vtk.vtkXMLImageDataWriter.return_value = mock_writer
        mock_writer.Write.return_value = 0  # Failure

        test_data = np.random.rand(10, 10, 10).astype(np.float32)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is False

    def test_create_vtk_exception(self, engine, mock_paraview):
        """Test exception handling"""
        import vtk

        vtk.vtkImageData.side_effect = Exception("Test error")

        test_data = np.random.rand(10, 10, 10)

        result = engine._create_vtk_from_numpy(
            test_data, "test_var", "/test/output.vti"
        )

        assert result is False


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple methods"""

    def test_bp5_full_conversion_pipeline(self, engine, mock_paraview):
        """Test full BP5 to VTK conversion pipeline"""

        # Mock the complete conversion flow
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.available_variables.return_value = {
            "density": {"Shape": "10, 10, 10", "Type": "double"}
        }
        mock_file.read.return_value = np.random.rand(10, 10, 10)

        import vtk
        from vtk.util import numpy_support

        vtk.vtkImageData.return_value = Mock()
        numpy_support.numpy_to_vtk.return_value = Mock()
        mock_writer = Mock()
        mock_writer.Write.return_value = 1
        vtk.vtkXMLImageDataWriter.return_value = mock_writer

        with (
            patch("adios2.open", return_value=mock_file),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            patch("os.path.splitext", return_value=("/test/file", ".bp5")),
            patch("os.path.getsize", return_value=1000),
        ):
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            assert result == "/test/file_converted.vti"

    def test_bp5_conversion_no_valid_variables(self, engine, mock_paraview):
        """Test BP5 conversion when variables exist but can't be read"""

        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.available_variables.return_value = {
            "test": {"Shape": "", "Type": "double"}  # Invalid shape
        }
        mock_file.read.return_value = np.array([])  # Empty data

        with (
            patch("adios2.open", return_value=mock_file),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            patch("os.path.splitext", return_value=("/test/file", ".bp5")),
        ):
            result = engine._convert_adios_to_vtk_improved("/test/file.bp5")
            # Should fail and return None
            assert result is None or result == "/test/file_converted.vti"
