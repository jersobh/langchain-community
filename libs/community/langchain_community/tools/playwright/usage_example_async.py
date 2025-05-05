"""Example usage of Playwright tools with async browser."""

import asyncio
from typing import List

from langchain_core.tools import BaseTool

# Import Playwright async API
from playwright.async_api import async_playwright

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


async def get_playwright_tools_async() -> List[BaseTool]:
    """
    Initialize and return a list of Playwright browser tools using async browser.
    
    This function demonstrates how to properly initialize the tools
    with an async browser instance.
    
    Returns:
        List[BaseTool]: List of initialized Playwright tools using async browser
    """
    # Start a Playwright instance and browser asynchronously
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    
    # Create a list of tools, all using the same async browser instance
    tools = [
        NavigateTool.from_browser(async_browser=browser),
        NavigateBackTool.from_browser(async_browser=browser),
        ExtractTextTool.from_browser(async_browser=browser),
        ExtractHyperlinksTool.from_browser(async_browser=browser),
        GetElementsTool.from_browser(async_browser=browser),
        ClickTool.from_browser(async_browser=browser),
        CurrentWebPageTool.from_browser(async_browser=browser),
        InputTextTool.from_browser(async_browser=browser),
        PressKeyTool.from_browser(async_browser=browser),
        SelectOptionTool.from_browser(async_browser=browser),
        CheckTool.from_browser(async_browser=browser),
        ScreenshotTool.from_browser(async_browser=browser),
    ]
    
    # Return both the tools and the resources that need to be closed later
    return tools, playwright, browser


async def example_async_usage() -> None:
    """
    Demonstrate how to use the Playwright tools with async browser.
    
    This example shows basic web interactions and form filling
    with proper tool initialization using async browser.
    """
    # Get tools and resources
    tools, playwright, browser = await get_playwright_tools_async()
    
    try:
        # Access tools by index or create variables for each
        navigate_tool = tools[0]
        input_text_tool = tools[7]
        press_key_tool = tools[8]
        screenshot_tool = tools[11]
        
        # Example workflow: Navigate to a site and interact with it
        # Notice we use _arun instead of run for async execution
        await navigate_tool._arun("https://www.example.com")
        
        # Take a screenshot
        screenshot_path = "/tmp/example_screenshot_async.png"
        await screenshot_tool._arun(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")
        
        # Navigate to a search engine
        await navigate_tool._arun("https://www.google.com")
        
        # Input text into search box
        await input_text_tool._arun(
            selector="input[name='q']",
            text="Python langchain playwright async example"
        )
        
        # Press Enter to submit the search
        await press_key_tool._arun(
            key="Enter",
            selector="input[name='q']"
        )
        
        # Take another screenshot after search
        await screenshot_tool._arun(path="/tmp/search_results_async.png")
        
    finally:
        # Clean up resources
        await browser.close()
        await playwright.stop()


async def demonstrate_common_issues() -> None:
    """
    Demonstrate common issues and their solutions with async browser.
    """
    # INCORRECT USAGE - This will cause a ValueError
    try:
        # Creating a tool without providing a browser instance
        navigate_tool = NavigateTool()
        await navigate_tool._arun("https://www.example.com")
    except ValueError as e:
        print(f"Error when browser not provided: {e}")
    
    # CORRECT USAGE - Using the factory methods with async browser
    try:
        # Start an async browser
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        
        # Use the from_browser factory method with async_browser parameter
        navigate_tool = NavigateTool.from_browser(async_browser=browser)
        
        # Now the tool can be used successfully with _arun
        await navigate_tool._arun("https://www.example.com")
        print("Successfully navigated to example.com")
        
        # Clean up when done
        await browser.close()
        await playwright.stop()
    except Exception as e:
        print(f"Unexpected error: {e}")


async def main_async() -> None:
    """Main async entry point."""
    await demonstrate_common_issues()
    # Uncomment to run the full example
    # await example_async_usage()


# Run the async code
if __name__ == "__main__":
    asyncio.run(main_async()) 