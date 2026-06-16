from src.utils.sensitive_words import check_sensitive_words


class TestSensitiveWords:
    def test_no_sensitive_words(self):
        result = check_sensitive_words("这是一个正常的视频标题")
        assert result == []

    def test_single_sensitive_word(self):
        result = check_sensitive_words("这个视频涉及赌博内容")
        assert "赌博" in result

    def test_multiple_sensitive_words(self):
        result = check_sensitive_words("赌博和毒品的内容")
        assert "赌博" in result
        assert "毒品" in result

    def test_case_insensitive(self):
        result = check_sensitive_words("正常文本内容")
        assert result == []
