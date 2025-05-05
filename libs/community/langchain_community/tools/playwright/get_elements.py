from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional, Sequence, Type, Any, Dict

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

if TYPE_CHECKING:
    from playwright.async_api import Page as AsyncPage
    from playwright.sync_api import Page as SyncPage


class GetElementsToolInput(BaseModel):
    """Input for GetElementsTool."""

    selector: Optional[str] = Field(
        default="body",
        description="CSS selector like 'div', 'p', 'a', '#id', '.classname'. If not provided, defaults to 'body' to get the entire page.",
    )
    attributes: Optional[List[str]] = Field(
        None,
        description="Set of attributes to retrieve for each element. If None, will extract standard useful attributes.",
    )


async def _aget_elements(
    page: AsyncPage, selector: str, attributes: Optional[Sequence[str]] = None
) -> List[Dict[str, Any]]:
    """Get elements matching the given CSS selector with enhanced attribute collection."""
    
    # Define script to extract elements with their attributes
    script = """
    (selector, requestedAttributes) => {
        const elements = Array.from(document.querySelectorAll(selector));
        const results = [];
        
        // Define commonly useful attributes to always check
        const defaultAttributes = [
            'id', 'name', 'class', 'type', 'value', 'placeholder', 'href',
            'role', 'aria-label', 'title', 'alt', 'src', 'data-testid'
        ];
        
        // Use requested attributes or default to useful ones
        const attributesToGet = requestedAttributes && requestedAttributes.length > 0 
            ? requestedAttributes 
            : defaultAttributes;
            
        for (const element of elements) {
            const result = {
                tag: element.tagName.toLowerCase(),
                text: element.textContent?.trim() || null,
                isVisible: isElementVisible(element),
                attributes: {},
                boundingBox: element.getBoundingClientRect().toJSON()
            };
            
            // Collect requested attributes
            for (const attr of attributesToGet) {
                if (attr === 'innerText') {
                    result.text = element.innerText?.trim() || null;
                } else if (element.hasAttribute(attr)) {
                    result.attributes[attr] = element.getAttribute(attr);
                }
            }
            
            // For interactive elements, add special indicators
            if (isInteractiveElement(element)) {
                result.interactive = true;
                result.interactionType = getInteractionType(element);
            }
            
            results.push(result);
        }
        
        return results;
        
        // Helper to check if element is visible
        function isElementVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && 
                   style.visibility !== 'hidden' && 
                   el.offsetWidth > 0 && 
                   el.offsetHeight > 0;
        }
        
        // Helper to check if element is interactive
        function isInteractiveElement(el) {
            // Check tag name
            const interactiveTags = ['a', 'button', 'input', 'select', 'textarea', 'option', 'label'];
            if (interactiveTags.includes(el.tagName.toLowerCase())) return true;
            
            // Check role attribute
            const interactiveRoles = ['button', 'link', 'checkbox', 'menuitem', 'tab', 'radio'];
            const role = el.getAttribute('role');
            if (role && interactiveRoles.includes(role)) return true;
            
            // Check for event listeners
            if (el.onclick || el.getAttribute('onclick')) return true;
            
            // Check for other interactive attributes
            if (el.getAttribute('tabindex') || el.getAttribute('contenteditable')) return true;
            
            return false;
        }
        
        // Determine the type of interaction possible
        function getInteractionType(el) {
            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type')?.toLowerCase();
            
            if (tag === 'a' || el.getAttribute('role') === 'link') return 'link';
            if (tag === 'button' || el.getAttribute('role') === 'button') return 'button';
            if (tag === 'input') {
                if (type === 'text' || type === 'email' || type === 'number' || type === 'password' || type === 'search') {
                    return 'input';
                }
                if (type === 'checkbox' || type === 'radio') return type;
                if (type === 'submit' || type === 'button') return 'button';
            }
            if (tag === 'select') return 'select';
            if (tag === 'textarea') return 'input';
            
            // Default for other interactive elements
            return 'clickable';
        }
    }
    """
    
    # Execute the script on the page
    result = await page.evaluate(script, selector, list(attributes) if attributes else None)
    return result


def _get_elements(
    page: SyncPage, selector: str, attributes: Optional[Sequence[str]] = None
) -> List[Dict[str, Any]]:
    """Get elements matching the given CSS selector with enhanced attribute collection."""
    
    # Define script to extract elements with their attributes
    script = """
    (selector, requestedAttributes) => {
        const elements = Array.from(document.querySelectorAll(selector));
        const results = [];
        
        // Define commonly useful attributes to always check
        const defaultAttributes = [
            'id', 'name', 'class', 'type', 'value', 'placeholder', 'href',
            'role', 'aria-label', 'title', 'alt', 'src', 'data-testid'
        ];
        
        // Use requested attributes or default to useful ones
        const attributesToGet = requestedAttributes && requestedAttributes.length > 0 
            ? requestedAttributes 
            : defaultAttributes;
            
        for (const element of elements) {
            const result = {
                tag: element.tagName.toLowerCase(),
                text: element.textContent?.trim() || null,
                isVisible: isElementVisible(element),
                attributes: {},
                boundingBox: element.getBoundingClientRect().toJSON()
            };
            
            // Collect requested attributes
            for (const attr of attributesToGet) {
                if (attr === 'innerText') {
                    result.text = element.innerText?.trim() || null;
                } else if (element.hasAttribute(attr)) {
                    result.attributes[attr] = element.getAttribute(attr);
                }
            }
            
            // For interactive elements, add special indicators
            if (isInteractiveElement(element)) {
                result.interactive = true;
                result.interactionType = getInteractionType(element);
            }
            
            results.push(result);
        }
        
        return results;
        
        // Helper to check if element is visible
        function isElementVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && 
                   style.visibility !== 'hidden' && 
                   el.offsetWidth > 0 && 
                   el.offsetHeight > 0;
        }
        
        // Helper to check if element is interactive
        function isInteractiveElement(el) {
            // Check tag name
            const interactiveTags = ['a', 'button', 'input', 'select', 'textarea', 'option', 'label'];
            if (interactiveTags.includes(el.tagName.toLowerCase())) return true;
            
            // Check role attribute
            const interactiveRoles = ['button', 'link', 'checkbox', 'menuitem', 'tab', 'radio'];
            const role = el.getAttribute('role');
            if (role && interactiveRoles.includes(role)) return true;
            
            // Check for event listeners
            if (el.onclick || el.getAttribute('onclick')) return true;
            
            // Check for other interactive attributes
            if (el.getAttribute('tabindex') || el.getAttribute('contenteditable')) return true;
            
            return false;
        }
        
        // Determine the type of interaction possible
        function getInteractionType(el) {
            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type')?.toLowerCase();
            
            if (tag === 'a' || el.getAttribute('role') === 'link') return 'link';
            if (tag === 'button' || el.getAttribute('role') === 'button') return 'button';
            if (tag === 'input') {
                if (type === 'text' || type === 'email' || type === 'number' || type === 'password' || type === 'search') {
                    return 'input';
                }
                if (type === 'checkbox' || type === 'radio') return type;
                if (type === 'submit' || type === 'button') return 'button';
            }
            if (tag === 'select') return 'select';
            if (tag === 'textarea') return 'input';
            
            // Default for other interactive elements
            return 'clickable';
        }
    }
    """
    
    # Execute the script on the page
    result = page.evaluate(script, selector, list(attributes) if attributes else None)
    return result


class GetElementsTool(BaseBrowserTool):
    """Tool for getting elements in the current web page matching a CSS selector."""

    name: str = "get_elements"
    description: str = (
        "Find elements on the current webpage using CSS selectors. "
        "Returns detailed information about matching elements including attributes, "
        "tag name, text content, interactivity status, and position. "
        "IMPORTANT: If no selector is specified, defaults to 'body' to get the entire page content. "
        "Use this tool to locate interactive elements like buttons, links, inputs, and forms. "
        "Particularly useful for finding search boxes, navigation menus, and input fields."
    )
    args_schema: Type[BaseModel] = GetElementsToolInput

    def _run(
        self,
        selector: str = "body",
        attributes: Optional[Sequence[str]] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        
        try:
            # If searching for search inputs with no matches, try common search selectors
            results = _get_elements(page, selector, attributes)
            
            if not results:
                # If the selector could be for a search box but returned no results, try alternatives
                if "search" in selector.lower() or "q" in selector.lower():
                    common_selectors = [
                        "input[type='search']",
                        "input[name='q']", 
                        "input[placeholder*='Search' i]",
                        "input.search",
                        ".searchbox input",
                        "textarea[name='q']"
                    ]
                    
                    # Try each selector
                    for alt_selector in common_selectors:
                        if alt_selector == selector:
                            continue
                            
                        alt_results = _get_elements(page, alt_selector, attributes)
                        
                        if alt_results:
                            return json.dumps({
                                "note": f"No results for '{selector}', showing results for '{alt_selector}' instead.",
                                "elements": alt_results
                            }, ensure_ascii=False)
            
            return json.dumps({
                "elements": results,
                "count": len(results)
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"Error finding elements with '{selector}': {str(e)}",
                "suggestion": "Try a more specific or different selector."
            }, ensure_ascii=False)

    async def _arun(
        self,
        selector: str = "body",
        attributes: Optional[Sequence[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        
        try:
            # If searching for search inputs with no matches, try common search selectors
            results = await _aget_elements(page, selector, attributes)
            
            if not results:
                # If the selector could be for a search box but returned no results, try alternatives
                if "search" in selector.lower() or "q" in selector.lower():
                    common_selectors = [
                        "input[type='search']",
                        "input[name='q']", 
                        "input[placeholder*='Search' i]",
                        "input.search",
                        ".searchbox input",
                        "textarea[name='q']"
                    ]
                    
                    # Try each selector
                    for alt_selector in common_selectors:
                        if alt_selector == selector:
                            continue
                            
                        alt_results = await _aget_elements(page, alt_selector, attributes)
                        
                        if alt_results:
                            return json.dumps({
                                "note": f"No results for '{selector}', showing results for '{alt_selector}' instead.",
                                "elements": alt_results
                            }, ensure_ascii=False)
            
            return json.dumps({
                "elements": results,
                "count": len(results)
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"Error finding elements with '{selector}': {str(e)}",
                "suggestion": "Try a more specific or different selector."
            }, ensure_ascii=False)
