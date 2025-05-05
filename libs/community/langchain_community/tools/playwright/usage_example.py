"""Example usage of Playwright tools."""

from typing import List

from langchain_core.tools import BaseTool

# Import Playwright
from playwright.sync_api import sync_playwright

# Import Playwright tools
from langchain_community.tools.playwright import (
    CheckTool,
    ClickTool,
    CurrentWebPageTool,
    ExtractHyperlinksTool,
    ExtractTextTool,
    GetElementsTool,
    InputTextTool,
    NavigateBackTool,
    NavigateTool,
    PressKeyTool,
    ScreenshotTool,
    SelectOptionTool,
)


def get_playwright_tools() -> List[BaseTool]:
    """
    Initialize and return a list of Playwright browser tools.
    
    This function demonstrates how to properly initialize the tools
    with a browser instance.
    
    Returns:
        List[BaseTool]: List of initialized Playwright tools
    """
    # Start a Playwright instance and browser
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    
    # Create a list of tools, all using the same browser instance
    tools = [
        NavigateTool.from_browser(sync_browser=browser),
        NavigateBackTool.from_browser(sync_browser=browser),
        ExtractTextTool.from_browser(sync_browser=browser),
        ExtractHyperlinksTool.from_browser(sync_browser=browser),
        GetElementsTool.from_browser(sync_browser=browser),
        ClickTool.from_browser(sync_browser=browser),
        CurrentWebPageTool.from_browser(sync_browser=browser),
        InputTextTool.from_browser(sync_browser=browser),
        PressKeyTool.from_browser(sync_browser=browser),
        SelectOptionTool.from_browser(sync_browser=browser),
        CheckTool.from_browser(sync_browser=browser),
        ScreenshotTool.from_browser(sync_browser=browser),
    ]
    
    return tools


def example_usage() -> None:
    """
    Demonstrate how to use the Playwright tools.
    
    This example shows basic web interactions and form filling
    with proper tool initialization.
    """
    tools = get_playwright_tools()
    
    # Access tools by index or create variables for each
    navigate_tool = tools[0]
    input_text_tool = tools[7]
    press_key_tool = tools[8]
    screenshot_tool = tools[11]
    
    # Example workflow: Navigate to a site and interact with it
    navigate_tool.run("https://www.example.com")
    
    # Take a screenshot
    screenshot_path = "/tmp/example_screenshot.png"
    screenshot_tool.run(path=screenshot_path, full_page=True)
    print(f"Screenshot saved to {screenshot_path}")
    
    # Navigate to a search engine
    navigate_tool.run("https://www.google.com")
    
    # Input text into search box
    input_text_tool.run(
        selector="input[name='q']",
        text="Python langchain playwright example"
    )
    
    # Press Enter to submit the search
    press_key_tool.run(
        key="Enter",
        selector="input[name='q']"
    )
    
    # Take another screenshot after search
    screenshot_tool.run(path="/tmp/search_results.png")


def main() -> None:
    """
    Main entry point.
    
    Shows common pitfalls and their solutions.
    """
    # INCORRECT USAGE - This will cause a ValueError
    try:
        # Creating a tool without providing a browser instance
        navigate_tool = NavigateTool()
        navigate_tool.run("https://www.example.com")
    except ValueError as e:
        print(f"Error when browser not provided: {e}")
    
    # CORRECT USAGE - Using the factory methods
    try:
        # Start a browser and create tools properly
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        
        # Use the from_browser factory method
        navigate_tool = NavigateTool.from_browser(sync_browser=browser)
        
        # Now the tool can be used successfully
        navigate_tool.run("https://www.example.com")
        print("Successfully navigated to example.com")
        
        # Clean up when done
        browser.close()
        playwright.stop()
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
    # Uncomment to run the full example
    # example_usage() 