from __future__ import annotations

import asyncio
from typing import Optional, Type, Union

from pydantic import BaseModel, Field

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import (
    get_current_page as lc_get_current_page,
    aget_current_page as lc_aget_current_page,
)
from playwright.sync_api import Page, Frame, ElementHandle as SyncElementHandle
from playwright.async_api import Page as AsyncPage, Frame as AsyncFrame, ElementHandle as AsyncElementHandle

# Define a shared attribute name for the active frame on the page object
ACTIVE_FRAME_ATTR = "_lc_active_frame"

class SwitchFrameInput(BaseModel):
    name_or_selector: str = Field(
        ...,
        description=(
            "The name (name attribute of the iframe), ID (e.g., '#frameId'), or a CSS selector "
            "for the iframe element (e.g., 'iframe.my-class', 'iframe[title=\"some title\"]'). "
            "Use special value 'PARENT_FRAME' or 'DEFAULT_CONTENT' to switch back to the main page."
        ),
    )

class SwitchFrameTool(BaseBrowserTool):
    name: str = "switch_to_frame"
    description: str = (
        "Switches the browser context to a specified iframe or back to the main document. "
        "All subsequent element interactions will target within the switched frame until switched again."
    )
    args_schema: Type[BaseModel] = SwitchFrameInput

    def _handle_switch(
        self,
        page: Union[Page, AsyncPage],
        name_or_selector: str,
    ) -> tuple[Optional[Union[Frame, AsyncFrame]], str]:
        """Shared logic for sync and async frame switching."""
        if name_or_selector.upper() in ["PARENT_FRAME", "DEFAULT_CONTENT"]:
            if hasattr(page, ACTIVE_FRAME_ATTR):
                delattr(page, ACTIVE_FRAME_ATTR)
            return None, "Switched back to the main page content."

        resolved_frame: Optional[Union[Frame, AsyncFrame]] = None
        selector_detail = ""

        # 1. Try by 'name' attribute using page.frame()
        # page.frame(name=) works for both sync and async Page objects
        try:
            # This directly returns a Frame object or None.
            # For async, the Frame object's methods are async, but getting the frame itself is sync.
            resolved_frame = page.frame(name=name_or_selector)
            if resolved_frame:
                selector_detail = f"by name attribute '{name_or_selector}'"
        except Exception: # Should ideally not happen as page.frame returns None on failure
            pass


        # 2. If not found by name, try to locate the iframe element using CSS selectors
        if not resolved_frame:
            potential_selectors = [
                name_or_selector,  # User's input as a direct CSS selector
                f"iframe[name='{name_or_selector}']", # Explicitly as iframe with name
                f"iframe#{name_or_selector.replace('#', '')}",  # As iframe with ID
            ]
            if name_or_selector.startswith(".") and not name_or_selector.startswith("iframe."):
                potential_selectors.append(f"iframe{name_or_selector}") # As iframe with class

            iframe_element: Optional[Union[SyncElementHandle, AsyncElementHandle]] = None
            
            for sel in potential_selectors:
                try:
                    if isinstance(page, Page): # Sync
                        element = page.query_selector(sel, timeout=2000)
                    else: # Async
                        element = asyncio.wait_for(page.query_selector(sel), timeout=2.0) # type: ignore

                    if element:
                        # Verify it's an iframe tag
                        tag_name_is_iframe = False
                        if isinstance(page, Page):
                            tag_name_is_iframe = element.evaluate("el => el.tagName.toLowerCase() === 'iframe'")
                        else: # Async
                            tag_name_is_iframe = asyncio.wait_for(element.evaluate("el => el.tagName.toLowerCase() === 'iframe'"), timeout=1.0) # type: ignore
                        
                        if tag_name_is_iframe:
                            iframe_element = element
                            selector_detail = f"by selector '{sel}'"
                            break
                        else: # Found an element, but it's not an iframe
                            if isinstance(page, Page): element.dispose()
                            else: asyncio.ensure_future(element.dispose()) # type: ignore
                except (asyncio.TimeoutError, Exception): # Covers Playwright's TimeoutError, other errors
                    continue # Try next selector
            
            if iframe_element:
                try:
                    if isinstance(page, Page):
                        resolved_frame = iframe_element.content_frame()
                        iframe_element.dispose()
                    else: # Async
                        resolved_frame = asyncio.wait_for(iframe_element.content_frame(), timeout=2.0) # type: ignore
                        asyncio.ensure_future(iframe_element.dispose()) # type: ignore
                    if not resolved_frame:
                        return None, f"Found iframe element ({selector_detail}), but could not access its content frame."
                except (asyncio.TimeoutError, Exception) as e:
                    return None, f"Error getting content frame for iframe ({selector_detail}): {e}"
            else:
                return None, f"Could not find an iframe element matching '{name_or_selector}' (tried various patterns)."

        if not resolved_frame:
            return None, f"Failed to switch to frame '{name_or_selector}'."
        
        setattr(page, ACTIVE_FRAME_ATTR, resolved_frame)
        return resolved_frame, f"Successfully switched to frame '{name_or_selector}' ({selector_detail})."

    def _run(
        self,
        name_or_selector: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        page = lc_get_current_page(self.sync_browser)
        if not page:
            return "No active page found. Ensure a page is navigated to first."
        
        _, message = self._handle_switch(page, name_or_selector)
        return message

    async def _arun(
        self,
        name_or_selector: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        page = await lc_aget_current_page(self.async_browser)
        if not page:
            return "No active page found. Ensure a page is navigated to first."

        # For async _handle_switch, we need to ensure its internal async calls are awaited
        # The _handle_switch itself is not an async def, but it calls async Playwright methods
        # when `page` is an AsyncPage. This is tricky. Let's refactor _handle_switch slightly.

        # Refactoring for clarity: create async version of handler
        if name_or_selector.upper() in ["PARENT_FRAME", "DEFAULT_CONTENT"]:
            if hasattr(page, ACTIVE_FRAME_ATTR):
                delattr(page, ACTIVE_FRAME_ATTR)
            return "Switched back to the main page content."

        resolved_frame: Optional[AsyncFrame] = None
        selector_detail = ""

        try:
            resolved_frame = page.frame(name=name_or_selector)
            if resolved_frame:
                selector_detail = f"by name attribute '{name_or_selector}'"
        except Exception:
            pass
        
        if not resolved_frame:
            potential_selectors = [
                name_or_selector, f"iframe[name='{name_or_selector}']",
                f"iframe#{name_or_selector.replace('#', '')}",
            ]
            if name_or_selector.startswith(".") and not name_or_selector.startswith("iframe."):
                potential_selectors.append(f"iframe{name_or_selector}")

            iframe_element: Optional[AsyncElementHandle] = None
            for sel in potential_selectors:
                try:
                    element = await asyncio.wait_for(page.query_selector(sel), timeout=2.0)
                    if element:
                        if await asyncio.wait_for(element.evaluate("el => el.tagName.toLowerCase() === 'iframe'"), timeout=1.0):
                            iframe_element = element
                            selector_detail = f"by selector '{sel}'"
                            break
                        else:
                            await element.dispose()
                except (asyncio.TimeoutError, Exception):
                    continue
            
            if iframe_element:
                try:
                    resolved_frame = await asyncio.wait_for(iframe_element.content_frame(), timeout=2.0)
                    await iframe_element.dispose()
                    if not resolved_frame:
                        return f"Found iframe element ({selector_detail}), but could not access its content frame."
                except (asyncio.TimeoutError, Exception) as e:
                    return f"Error getting content frame for iframe ({selector_detail}): {e}"
            else:
                return f"Could not find an iframe element matching '{name_or_selector}' (tried various patterns)."

        if not resolved_frame:
            return f"Failed to switch to frame '{name_or_selector}'."
        
        setattr(page, ACTIVE_FRAME_ATTR, resolved_frame)
        return f"Successfully switched to frame '{name_or_selector}' ({selector_detail})."