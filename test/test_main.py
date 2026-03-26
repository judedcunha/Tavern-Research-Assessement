import pytest
from unittest.mock import patch, MagicMock
from collections.abc import Generator
from main import main

@pytest.fixture
def mock_wiki_functions() -> Generator[dict[str, MagicMock], None, None]:
    """Fixture to mock Wikipedia-related functions"""
    with patch('main.get_page') as mock_get_page, \
         patch('main.find_short_path') as mock_find_path:
        
        # Create mock page
        mock_page = MagicMock()
        mock_page.title = "Test Page"
        mock_page.summary = "Test summary"
        mock_get_page.return_value = mock_page
        
        # Create mock path
        mock_find_path.return_value = ["Start", "End"]
        
        yield {
            'get_page': mock_get_page,
            'find_short_path': mock_find_path
        }

@pytest.fixture
def mock_input() -> Generator[MagicMock, None, None]:
    """Fixture to mock input function"""
    with patch('builtins.input') as mock_input_func:
        yield mock_input_func


def test_main_single_round(mock_wiki_functions: dict[str, MagicMock], mock_input: MagicMock) -> None:
    """Test main function for a single round"""
    # Set up input: enter, mode selection, page name, quit
    mock_input.side_effect = ['', 'n', 'Ocean', 'q']

    main()

    assert mock_input.call_count == 4

def test_main_multiple_rounds(mock_wiki_functions: dict[str, MagicMock], mock_input: MagicMock) -> None:
    """Test main function with custom input sequence"""
    # Simulate: enter, mode, page+again, page+again, page+quit
    mock_input.side_effect = ['', 'n', 'Mountain', '', 'River', '', 'Plain', 'q']

    main()

    assert mock_input.call_count == 8

def test_stop_q(mock_wiki_functions: dict[str, MagicMock], mock_input: MagicMock) -> None:
    """Test that main function handles different input types"""
    # Test with different input types
    test_inputs = ['q']

    for test_input in test_inputs:
        mock_input.reset_mock()
        mock_input.side_effect = ['', 'n', 'Forest', test_input, 'Utopia', 'n']

        # Should not raise any exceptions
        main()

        assert mock_input.call_count == 4