from __future__ import annotations

from typing import Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field

from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)


class ClickToolInput(BaseModel):
    """Input for ClickTool."""

    selector: str = Field(..., description="CSS selector for the element to click")
    force: bool = Field(
        False, 
        description="Whether to bypass pointer interception and click through"
    )
    wait_for_navigation: bool = Field(
        False,
        description="Whether to wait for navigation to complete after clicking"
    )
    wait_for_timeout: int = Field(
        0,
        description="Milliseconds to wait after clicking (useful for letting page updates render)"
    )


class ClickTool(BaseBrowserTool):
    """Tool for clicking on an element with the given CSS selector."""

    name: str = "click_element"
    description: str = (
        "Click on an element with the given CSS selector. "
        "Can wait for navigation or timeout after clicking. "
        "Use force=True to click hidden elements."
    )
    args_schema: Type[BaseModel] = ClickToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""
    playwright_timeout: float = 5_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""

    def _selector_effective(self, selector: str) -> str:
        if not self.visible_only:
            return selector
        return f"{selector} >> visible=1"

    def _run(
        self,
        selector: str,
        force: bool = False,
        wait_for_navigation: bool = False,
        wait_for_timeout: int = 0,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        
        # Prepare our effective selector
        selector_effective = self._selector_effective(selector=selector)
        
        # Import required exceptions
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import Error as PlaywrightError

        try:
            # First verify element exists by trying to locate it
            try:
                # Get locator without strict mode (which might not be supported)
                element = page.locator(selector_effective).first
                
                # Check if element exists
                count = element.count()
                if count == 0:
                    return f"Element '{selector}' not found"
                
                # Check if element is visible if needed
                is_visible = element.is_visible(timeout=self.playwright_timeout / 2)
                if not is_visible and not force and self.visible_only:
                    return f"Element '{selector}' found but not visible. Use force=True to click it."
            except PlaywrightTimeoutError:
                return f"Element '{selector}' not found or timed out waiting for it"
            except PlaywrightError as e:
                return f"Error locating element '{selector}': {str(e)}"

            # Setup for navigation waiting if requested
            if wait_for_navigation:
                try:
                    with page.expect_navigation(timeout=self.playwright_timeout * 2) as nav_promise:
                        # Perform the click with appropriate options
                        page.click(
                            selector_effective,
                            force=force,
                            timeout=self.playwright_timeout,
                        )
                    # Wait for navigation to complete
                    nav_result = nav_promise.value
                    # Add extra timeout if requested
                    if wait_for_timeout > 0:
                        page.wait_for_timeout(wait_for_timeout)
                    return f"Clicked element '{selector}' and navigated to {nav_result.url}"
                except PlaywrightTimeoutError:
                    return f"Clicked element '{selector}' but navigation timed out"
            else:
                # Perform the click without waiting for navigation
                try:
                    page.click(
                        selector_effective,
                        force=force,
                        timeout=self.playwright_timeout,
                    )
                    
                    # Add extra timeout if requested
                    if wait_for_timeout > 0:
                        page.wait_for_timeout(wait_for_timeout)
                    
                    # Get the current URL
                    current_url = page.url
                    
                    return f"Clicked element '{selector}'"
                except PlaywrightTimeoutError:
                    return f"Unable to click element '{selector}': element not clickable"
                
        except Exception as e:
            return f"Error clicking element '{selector}': {str(e)}"

    async def _arun(
        self,
        selector: str,
        force: bool = False,
        wait_for_navigation: bool = False,
        wait_for_timeout: int = 0,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        
        # Prepare our effective selector
        selector_effective = self._selector_effective(selector=selector)
        
        # Import required exceptions
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import Error as PlaywrightError

        try:
            # First verify element exists by trying to locate it
            try:
                # Get locator without strict mode (which might not be supported)
                element = page.locator(selector_effective).first
                
                # Check if element exists
                count = await element.count()
                if count == 0:
                    return f"Element '{selector}' not found"
                
                # Check if element is visible if needed
                is_visible = await element.is_visible(timeout=self.playwright_timeout / 2)
                if not is_visible and not force and self.visible_only:
                    return f"Element '{selector}' found but not visible. Use force=True to click it."
            except PlaywrightTimeoutError:
                return f"Element '{selector}' not found or timed out waiting for it"
            except PlaywrightError as e:
                return f"Error locating element '{selector}': {str(e)}"

            # Setup for navigation waiting if requested
            if wait_for_navigation:
                try:
                    async with page.expect_navigation(timeout=self.playwright_timeout * 2) as nav_promise:
                        # Perform the click
                        await page.click(
                            selector_effective,
                            force=force,
                            timeout=self.playwright_timeout,
                        )
                    # Wait for navigation to complete
                    nav_result = await nav_promise.value
                    # Add extra timeout if requested
                    if wait_for_timeout > 0:
                        await page.wait_for_timeout(wait_for_timeout)
                    return f"Clicked element '{selector}' and navigated to {nav_result.url}"
                except PlaywrightTimeoutError:
                    return f"Clicked element '{selector}' but navigation timed out"
            else:
                # Perform the click without waiting for navigation
                try:
                    await page.click(
                        selector_effective,
                        force=force,
                        timeout=self.playwright_timeout,
                    )
                    
                    # Add extra timeout if requested
                    if wait_for_timeout > 0:
                        await page.wait_for_timeout(wait_for_timeout)
                    
                    # Get the current URL
                    current_url = page.url
                    
                    return f"Clicked element '{selector}'"
                except PlaywrightTimeoutError:
                    return f"Unable to click element '{selector}': element not clickable"
                
        except Exception as e:
            return f"Error clicking element '{selector}': {str(e)}"
