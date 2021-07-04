def build_mock_requests_get(html_files_by_url):
    """Build a mock requests.get function to return canned responses from files.
    :param html_files_by_url: A dict mapping urls to files with the page contents.
    """
    def mock_requests_get(url):
        class MockResponse:
            def __init__(self, text):
                self.text = text

        with open(html_files_by_url[url]) as f:
            response = MockResponse(f.read())
        return response
    return mock_requests_get
