from unittest.mock import patch
from src.services.kling import KlingService


class TestKlingService:
    @patch("src.services.kling.settings")
    def test_generate_jwt(self, mock_settings):
        mock_settings.kling_access_key = "test_ak"
        mock_settings.kling_secret_key = "test_sk"
        mock_settings.kling_base_url = "https://api.klingai.com"
        mock_settings.kling_model = "kling-v2-5-turbo"

        service = KlingService()
        token = service._generate_jwt()
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("src.services.kling.settings")
    def test_headers_format(self, mock_settings):
        mock_settings.kling_access_key = "test_ak"
        mock_settings.kling_secret_key = "test_sk"
        mock_settings.kling_base_url = "https://api.klingai.com"
        mock_settings.kling_model = "kling-v2-5-turbo"

        service = KlingService()
        headers = service._headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Content-Type"] == "application/json"


class TestKlingPricing:
    def test_price_lookup(self):
        from src.services.kling import KLING_PRICES
        assert KLING_PRICES["kling-v2-5-turbo"]["5s"] == 0.35
        assert KLING_PRICES["kling-v2-6-pro"]["10s"] == 0.98
