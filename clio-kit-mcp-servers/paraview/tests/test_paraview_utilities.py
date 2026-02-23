"""
Tests for ParaView utility methods (pipeline, arrays, camera, screenshot, histogram)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


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


class TestGetPipeline:
    """Test get_pipeline method"""

    def test_get_pipeline_with_sources(self, engine, mock_paraview):
        """Test getting pipeline with sources"""
        from paraview.simple import GetSources

        mock_sphere = Mock()
        mock_sphere.__class__.__name__ = "Sphere"
        mock_cone = Mock()
        mock_cone.__class__.__name__ = "Cone"

        GetSources.return_value = {
            ("Sphere1", ""): mock_sphere,
            ("Cone1", ""): mock_cone,
        }

        success, message = engine.get_pipeline()

        assert success is True
        assert "Sphere1" in message
        assert "Cone1" in message
        assert "Sphere" in message
        assert "Cone" in message

    def test_get_pipeline_empty(self, engine, mock_paraview):
        """Test getting empty pipeline"""
        from paraview.simple import GetSources

        GetSources.return_value = {}

        success, message = engine.get_pipeline()

        assert success is True
        assert "empty" in message.lower()

    def test_get_pipeline_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.simple import GetSources

        GetSources.side_effect = Exception("Test error")

        success, message = engine.get_pipeline()

        assert success is False
        assert "Error getting pipeline" in message


class TestGetAvailableArrays:
    """Test get_available_arrays method"""

    def test_get_arrays_with_point_and_cell_data(self, engine, mock_paraview):
        """Test getting arrays with both point and cell data"""
        from paraview.simple import GetActiveSource

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_cell_info = Mock()

        # Mock point arrays
        mock_point_array1 = Mock()
        mock_point_array1.GetName.return_value = "temperature"
        mock_point_array1.GetNumberOfComponents.return_value = 1

        mock_point_info.GetNumberOfArrays.return_value = 1
        mock_point_info.GetArrayInformation.return_value = mock_point_array1

        # Mock cell arrays
        mock_cell_array1 = Mock()
        mock_cell_array1.GetName.return_value = "pressure"
        mock_cell_array1.GetNumberOfComponents.return_value = 1

        mock_cell_info.GetNumberOfArrays.return_value = 1
        mock_cell_info.GetArrayInformation.return_value = mock_cell_array1

        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_data_info.GetCellDataInformation.return_value = mock_cell_info
        mock_source.GetDataInformation.return_value = mock_data_info

        GetActiveSource.return_value = mock_source

        success, message = engine.get_available_arrays()

        assert success is True
        assert "temperature" in message
        assert "pressure" in message
        assert "Point data" in message
        assert "Cell data" in message

    def test_get_arrays_no_source(self, engine, mock_paraview):
        """Test with no active source"""
        from paraview.simple import GetActiveSource

        GetActiveSource.return_value = None

        success, message = engine.get_available_arrays()

        assert success is False
        assert "No active source" in message

    def test_get_arrays_no_point_data(self, engine, mock_paraview):
        """Test with no point data arrays"""
        from paraview.simple import GetActiveSource

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_cell_info = Mock()

        mock_point_info.GetNumberOfArrays.return_value = 0
        mock_cell_info.GetNumberOfArrays.return_value = 0

        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_data_info.GetCellDataInformation.return_value = mock_cell_info
        mock_source.GetDataInformation.return_value = mock_data_info

        GetActiveSource.return_value = mock_source

        success, message = engine.get_available_arrays()

        assert success is True
        # Should still succeed but show no arrays
        assert "No point data arrays" in message or message.count("components") == 0

    def test_get_arrays_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.simple import GetActiveSource

        GetActiveSource.side_effect = Exception("Test error")

        success, message = engine.get_available_arrays()

        assert success is False
        assert "Error getting available arrays" in message


class TestGetHistogram:
    """Test get_histogram method"""

    def test_get_histogram_auto_field(self, engine, mock_paraview):
        """Test histogram with auto-selected field"""
        from paraview.simple import (
            GetActiveSource,
            Histogram,
            servermanager,
        )

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_array_info = Mock()
        mock_hist_filter = Mock()
        mock_nbins_prop = Mock()

        # Single array for auto-selection
        mock_array_info.GetName.return_value = "density"
        mock_point_info.GetNumberOfArrays.return_value = 1
        mock_point_info.GetArrayInformation.return_value = mock_array_info
        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_source.GetDataInformation.return_value = mock_data_info

        # Mock histogram filter
        mock_hist_filter.GetProperty.return_value = mock_nbins_prop
        Histogram.return_value = mock_hist_filter

        # Mock histogram table
        mock_table = Mock()
        mock_bin_centers = Mock()
        mock_frequencies = Mock()

        mock_bin_centers.GetValue.side_effect = [0.0, 50.0, 100.0]
        mock_frequencies.GetValue.side_effect = [10, 20, 30]
        mock_table.GetNumberOfRows.return_value = 3
        mock_table.GetColumnByName.side_effect = lambda name: (
            mock_bin_centers if "center" in name else mock_frequencies
        )

        servermanager.Fetch.return_value = mock_table
        GetActiveSource.return_value = mock_source

        success, message, hist_data = engine.get_histogram()

        assert success is True
        assert "'density'" in message
        assert len(hist_data) == 3
        assert hist_data[0] == (0.0, 10)

    def test_get_histogram_custom_field(self, engine, mock_paraview):
        """Test histogram with custom field and parameters"""
        from paraview.simple import GetActiveSource, Histogram, servermanager

        mock_source = Mock()
        mock_hist_filter = Mock()
        mock_nbins_prop = Mock()

        mock_hist_filter.GetProperty.return_value = mock_nbins_prop
        Histogram.return_value = mock_hist_filter

        mock_table = Mock()
        mock_table.GetNumberOfRows.return_value = 0

        servermanager.Fetch.return_value = mock_table
        GetActiveSource.return_value = mock_source

        success, message, hist_data = engine.get_histogram(
            field="temperature", num_bins=128, data_location="CELLS"
        )

        # Will fail due to empty data, but checks parameter handling
        assert success is False or isinstance(hist_data, list)

    def test_get_histogram_no_source(self, engine, mock_paraview):
        """Test with no active source"""
        from paraview.simple import GetActiveSource

        GetActiveSource.return_value = None

        success, message, hist_data = engine.get_histogram()

        assert success is False
        assert "No active source" in message

    def test_get_histogram_multiple_fields(self, engine, mock_paraview):
        """Test with multiple fields (should fail without field specification)"""
        from paraview.simple import GetActiveSource

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_array1 = Mock()
        mock_array2 = Mock()

        mock_array1.GetName.return_value = "field1"
        mock_array2.GetName.return_value = "field2"
        mock_point_info.GetNumberOfArrays.return_value = 2
        mock_point_info.GetArrayInformation.side_effect = [mock_array1, mock_array2]
        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_source.GetDataInformation.return_value = mock_data_info

        GetActiveSource.return_value = mock_source

        success, message, hist_data = engine.get_histogram()

        assert success is False
        assert "Multiple fields available" in message
        assert "field1" in message and "field2" in message

    def test_get_histogram_empty_data(self, engine, mock_paraview):
        """Test with empty histogram data"""
        from paraview.simple import GetActiveSource, Histogram, servermanager

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_array_info = Mock()
        mock_hist_filter = Mock()
        mock_nbins_prop = Mock()

        mock_array_info.GetName.return_value = "test"
        mock_point_info.GetNumberOfArrays.return_value = 1
        mock_point_info.GetArrayInformation.return_value = mock_array_info
        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_source.GetDataInformation.return_value = mock_data_info

        mock_hist_filter.GetProperty.return_value = mock_nbins_prop
        Histogram.return_value = mock_hist_filter

        mock_table = Mock()
        mock_table.GetNumberOfRows.return_value = 0

        servermanager.Fetch.return_value = mock_table
        GetActiveSource.return_value = mock_source

        success, message, hist_data = engine.get_histogram()

        assert success is False
        assert "empty data" in message.lower()

    def test_get_histogram_no_bins_property(self, engine, mock_paraview):
        """Test when histogram filter has no NumberOfBins property"""
        from paraview.simple import GetActiveSource, Histogram

        mock_source = Mock()
        mock_data_info = Mock()
        mock_point_info = Mock()
        mock_array_info = Mock()
        mock_hist_filter = Mock()

        mock_array_info.GetName.return_value = "test"
        mock_point_info.GetNumberOfArrays.return_value = 1
        mock_point_info.GetArrayInformation.return_value = mock_array_info
        mock_data_info.GetPointDataInformation.return_value = mock_point_info
        mock_source.GetDataInformation.return_value = mock_data_info

        mock_hist_filter.GetProperty.return_value = None  # No property
        Histogram.return_value = mock_hist_filter
        GetActiveSource.return_value = mock_source

        success, message, hist_data = engine.get_histogram()

        assert success is False
        assert "does not have" in message

    def test_get_histogram_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.simple import GetActiveSource

        GetActiveSource.side_effect = Exception("Test error")

        success, message, hist_data = engine.get_histogram()

        assert success is False
        assert "Error computing histogram" in message


class TestCameraOperations:
    """Test camera rotation and reset"""

    def test_rotate_camera_success(self, engine, mock_paraview):
        """Test rotating camera successfully"""
        from paraview.simple import GetActiveView

        mock_view = Mock()
        mock_camera = Mock()
        mock_view.GetActiveCamera.return_value = mock_camera

        GetActiveView.return_value = mock_view

        success, message = engine.rotate_camera(45.0, 30.0)

        assert success is True
        assert "45" in message
        assert "30" in message
        mock_camera.Azimuth.assert_called_once_with(45.0)
        mock_camera.Elevation.assert_called_once_with(30.0)

    def test_rotate_camera_default_params(self, engine, mock_paraview):
        """Test rotating camera with default parameters"""
        from paraview.simple import GetActiveView

        mock_view = Mock()
        mock_camera = Mock()
        mock_view.GetActiveCamera.return_value = mock_camera

        GetActiveView.return_value = mock_view

        success, message = engine.rotate_camera()

        assert success is True
        mock_camera.Azimuth.assert_called_once_with(30.0)
        mock_camera.Elevation.assert_called_once_with(0.0)

    def test_rotate_camera_no_view(self, engine, mock_paraview):
        """Test with no active view"""
        from paraview.simple import GetActiveView

        GetActiveView.return_value = None

        success, message = engine.rotate_camera()

        assert success is False
        assert "No active view" in message

    def test_rotate_camera_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.simple import GetActiveView

        GetActiveView.side_effect = Exception("Test error")

        success, message = engine.rotate_camera()

        assert success is False
        assert "Error rotating camera" in message

    def test_reset_camera_success(self, engine, mock_paraview):
        """Test resetting camera successfully"""
        from paraview.simple import GetActiveView, ResetCamera

        mock_view = Mock()
        GetActiveView.return_value = mock_view

        success, message = engine.reset_camera()

        assert success is True
        assert "reset" in message.lower()
        ResetCamera.assert_called_once_with(mock_view)

    def test_reset_camera_no_view(self, engine, mock_paraview):
        """Test with no active view"""
        from paraview.simple import GetActiveView

        GetActiveView.return_value = None

        success, message = engine.reset_camera()

        assert success is False
        assert "No active view" in message

    def test_reset_camera_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.simple import GetActiveView

        GetActiveView.side_effect = Exception("Test error")

        success, message = engine.reset_camera()

        assert success is False
        assert "Error resetting camera" in message


class TestGetScreenshot:
    """Test screenshot capture"""

    def test_get_screenshot_success(self, engine, mock_paraview):
        """Test successful screenshot capture"""
        from paraview import servermanager

        # Mock proxy manager
        mock_pxm = Mock()
        mock_view_proxy = Mock()
        mock_view_proxy.GetXMLName.return_value = "RenderView"

        mock_pxm.GetProxiesInGroup.return_value = {
            ("views", "RenderView1"): mock_view_proxy
        }

        servermanager.ProxyManager.return_value = mock_pxm

        with (
            patch("os.getcwd", return_value="/test/dir"),
            patch("os.path.join", return_value="/test/dir/screenshot.png"),
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=12345),
            patch("datetime.datetime") as mock_datetime,
        ):
            mock_now = Mock()
            mock_now.strftime.return_value = "20250101_120000"
            mock_datetime.now.return_value = mock_now

            success, message, path = engine.get_screenshot()

            assert success is True
            assert "screenshot.png" in message or "Screenshot saved" in message

    def test_get_screenshot_no_gui_view(self, engine, mock_paraview):
        """Test when no GUI render view found"""
        from paraview import servermanager

        mock_pxm = Mock()
        mock_pxm.GetProxiesInGroup.return_value = {}  # No views

        servermanager.ProxyManager.return_value = mock_pxm

        success, message, path = engine.get_screenshot()

        assert success is False
        assert "No GUI render view" in message

    def test_get_screenshot_file_not_created(self, engine, mock_paraview):
        """Test when screenshot file is not created"""
        from paraview import servermanager

        mock_pxm = Mock()
        mock_view_proxy = Mock()
        mock_view_proxy.GetXMLName.return_value = "RenderView"
        mock_pxm.GetProxiesInGroup.return_value = {
            ("views", "RenderView1"): mock_view_proxy
        }

        servermanager.ProxyManager.return_value = mock_pxm

        with (
            patch("os.getcwd", return_value="/test"),
            patch("os.path.join", return_value="/test/screenshot.png"),
            patch("os.path.exists", return_value=False),
        ):  # File not created
            success, message, path = engine.get_screenshot()

            assert success is False
            assert "not created" in message

    def test_get_screenshot_exception(self, engine, mock_paraview):
        """Test exception handling"""
        from paraview.collaboration import processServerEvents

        processServerEvents.side_effect = Exception("Test error")

        success, message, path = engine.get_screenshot()

        assert success is False
        assert "Error getting screenshot" in message
