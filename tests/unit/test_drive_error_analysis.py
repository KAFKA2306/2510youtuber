"""Unit tests for DriveManager error analysis helpers."""

import json
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from app.drive import DriveManager


@pytest.mark.unit
class TestDriveErrorAnalysis:
    def test_analyze_storage_quota_error(self):
        payload = {
            "error": {
                "code": 403,
                "message": "Service Accounts do not have storage quota.",
                "errors": [
                    {
                        "domain": "usageLimits",
                        "reason": "storageQuotaExceeded",
                        "message": "Service Accounts do not have storage quota.",
                    }
                ],
            }
        }
        http_error = HttpError(
            SimpleNamespace(status=403, reason="Forbidden"),
            json.dumps(payload).encode("utf-8"),
            uri="https://www.googleapis.com/upload/drive/v3/files",
        )

        analysis = DriveManager._analyze_drive_error(http_error)

        assert analysis["classification"] == "storage_quota"
        assert analysis["status"] == 403
        assert analysis["reason"] == "storageQuotaExceeded"
        assert any("shared drive" in suggestion for suggestion in analysis["suggestions"])

    def test_analyze_permission_error(self):
        payload = {
            "error": {
                "code": 403,
                "message": "Insufficient permissions for this file.",
                "errors": [
                    {
                        "domain": "global",
                        "reason": "insufficientFilePermissions",
                        "message": "Insufficient Permission",
                    }
                ],
            }
        }
        http_error = HttpError(
            SimpleNamespace(status=403, reason="Forbidden"),
            json.dumps(payload).encode("utf-8"),
            uri="https://www.googleapis.com/drive/v3/files",
        )

        analysis = DriveManager._analyze_drive_error(http_error)

        assert analysis["classification"] == "permission_denied"
        assert any("service account" in suggestion for suggestion in analysis["suggestions"])
        assert analysis["status"] == 403
