import pytest
from unittest.mock import patch, MagicMock
import os

# Assuming app.sheets is correctly importable
from app.sheets import GoogleSheetManager

@pytest.fixture
def mock_google_credentials():
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = "/path/to/fake_credentials.json"
        yield

@pytest.mark.asyncio
async def test_google_credentials_validation(mock_google_credentials):
    """GOOGLE_APPLICATION_CREDENTIALS検証"""
    with patch('google.oauth2.service_account.Credentials.from_service_account_file') as mock_from_service_account_file:
        mock_from_service_account_file.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            GoogleSheetManager()

@pytest.mark.asyncio
async def test_sheets_service_initialization():
    """self.service = None時の適切な処理"""
    with patch('googleapiclient.discovery.build') as mock_build:
        mock_build.return_value = None
        manager = GoogleSheetManager()
        assert manager.service is None
        # Attempting to use the service should raise an error or be handled gracefully
        with pytest.raises(Exception) as excinfo:
            await manager.read_sheet("dummy_spreadsheet_id", "dummy_range")
        assert "Google Sheets service not initialized" in str(excinfo.value)

@pytest.mark.asyncio
async def test_run_update_error_handling():
    """'NoneType' has no attribute 'spreadsheets'対応"""
    with patch('googleapiclient.discovery.build') as mock_build:
        mock_service = MagicMock()
        mock_service.spreadsheets.return_value.values.return_value.update.side_effect = AttributeError("'NoneType' object has no attribute 'spreadsheets'")
        mock_build.return_value = mock_service
        manager = GoogleSheetManager()
        
        with pytest.raises(AttributeError) as excinfo:
            await manager.update_sheet("dummy_spreadsheet_id", "dummy_range", [["test"]])
        assert "'NoneType' object has no attribute 'spreadsheets'" in str(excinfo.value)
