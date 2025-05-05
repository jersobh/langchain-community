from __future__ import annotations

import json
from typing import Optional, Type, Dict, Any, List

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


class ExtractDOMTreeToolInput(BaseModel):
    """Input for ExtractDOMTreeTool."""
    pass


class ExtractDOMTreeTool(BaseBrowserTool):
    """Tool for extracting a slim DOM tree with focus on interactive elements."""

    name: str = "extract_dom_tree"
    description: str = (
        "Extract a concise DOM tree from the current webpage, "
        "focusing on structure and interactive elements like buttons, links, and form fields. "
        "Call with NO parameters. Use to understand page structure before interacting with elements."
    )
    args_schema: Type[BaseModel] = ExtractDOMTreeToolInput

    playwright_timeout: float = 5_000
    """Timeout (in ms) for Playwright to wait for JavaScript execution."""

    def _dom_extract_script(self) -> str:
        """Build the JavaScript to extract a slim DOM tree."""
        return """
        () => {
            // Helper to check if an element is interactive
            function isInteractive(element) {
                if (!element) return false;
                
                // Common interactive tags
                const interactiveTags = [
                    'a', 'button', 'input', 'select', 'textarea', 'option',
                    'label', 'form', 'summary'
                ];
                
                // Check tag name
                const tagName = element.tagName.toLowerCase();
                if (interactiveTags.includes(tagName)) return true;
                
                // Check common interactive attributes
                const interactiveAttrs = [
                    'onclick', 'onchange', 'onsubmit', 'role', 'tabindex',
                    'contenteditable', 'href', 'data-action'
                ];
                
                for (const attr of interactiveAttrs) {
                    if (element.hasAttribute(attr)) return true;
                }
                
                // Check for event handlers
                if (element.onclick || element.onchange || element.onsubmit) return true;
                
                // Check for ARIA roles
                const interactiveRoles = ['button', 'link', 'checkbox', 'dialog', 'menuitem', 'tab', 'radio', 'combobox', 'search'];
                const role = element.getAttribute('role');
                if (role && interactiveRoles.includes(role)) return true;
                
                return false;
            }
            
            // Get a simplified version of attributes
            function getSimplifiedAttributes(element) {
                const result = {};
                const priorityAttrs = [
                    'id', 'name', 'class', 'type', 'role', 'aria-label',
                    'href', 'value', 'placeholder', 'data-testid', 'title',
                    'alt', 'src', 'tabindex', 'disabled'
                ];
                
                // Add important attributes first
                for (const attr of priorityAttrs) {
                    if (element.hasAttribute(attr)) {
                        const value = element.getAttribute(attr);
                        // Truncate very long values
                        result[attr] = value.length > 50 ? value.substring(0, 50) + '...' : value;
                    }
                }
                
                // For interactive elements, add state information
                if (isInteractive(element)) {
                    // Add state information for inputs
                    if (element.tagName.toLowerCase() === 'input') {
                        const type = element.getAttribute('type')?.toLowerCase();
                        if (type === 'checkbox' || type === 'radio') {
                            result['checked'] = element.checked;
                        } else if (['text', 'search', 'number', 'email', 'password'].includes(type) || 
                                  element.tagName.toLowerCase() === 'textarea') {
                            // Add value for text inputs
                            if (element.value) {
                                result['value'] = element.value.length > 20 ? 
                                    element.value.substring(0, 20) + '...' : element.value;
                            }
                        }
                    }
                    
                    // Add disabled state
                    if ('disabled' in element) {
                        result['disabled'] = element.disabled;
                    }
                }
                
                return result;
            }
            
            // Get simplified text content
            function getSimplifiedText(element) {
                const text = element.innerText?.trim();
                if (!text) return null;
                
                // Truncate long text
                return text.length > 100 ? text.substring(0, 100) + '...' : text;
            }
            
            // Determine the type of interaction possible with an element
            function getInteractionType(element) {
                const tagName = element.tagName.toLowerCase();
                const role = element.getAttribute('role');
                const type = element.getAttribute('type')?.toLowerCase();
                
                if (tagName === 'a' || role === 'link') return 'link';
                if (tagName === 'button' || role === 'button') return 'button';
                
                if (tagName === 'input') {
                    if (['text', 'search', 'number', 'email', 'password'].includes(type)) {
                        return 'input';
                    } else if (type === 'checkbox') {
                        return 'checkbox';
                    } else if (type === 'radio') {
                        return 'radio';
                    } else if (['submit', 'button'].includes(type)) {
                        return 'button';
                    }
                }
                
                if (tagName === 'textarea') return 'input';
                if (tagName === 'select' || role === 'combobox') return 'select';
                
                if (element.onclick || element.getAttribute('onclick')) return 'clickable';
                
                return 'interactive';
            }
            
            // Check if element is visible and in viewport
            function isVisibleInViewport(element) {
                if (!element) return false;
                
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return false;
                }
                
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && 
                       rect.top < window.innerHeight && rect.bottom > 0 && 
                       rect.left < window.innerWidth && rect.right > 0;
            }
            
            // Extract DOM tree recursively with smart truncation
            function extractNode(node, depth = 0, maxDepth = 4) {
                if (depth > maxDepth) return null;
                
                // Skip non-element nodes except for important text nodes
                if (node.nodeType !== Node.ELEMENT_NODE) {
                    if (node.nodeType === Node.TEXT_NODE) {
                        const text = node.textContent.trim();
                        if (text && text.length > 3 && depth <= 2) {
                            return { type: 'text', content: text.length > 50 ? text.substring(0, 50) + '...' : text };
                        }
                    }
                    return null;
                }
                
                // Skip invisible elements (unless interactive or they might become visible)
                if (!isVisibleInViewport(node) && !isInteractive(node) && 
                    !node.querySelector('button, a, input, select, textarea')) {
                    // Check for special cases - don't skip header/nav even if not in viewport
                    const tagName = node.tagName.toLowerCase();
                    const role = node.getAttribute('role');
                    if (!['header', 'nav', 'footer', 'main'].includes(tagName) && 
                        !['navigation', 'banner', 'main', 'contentinfo'].includes(role)) {
                        return null;
                    }
                }
                
                // Skip less important elements at deeper levels to keep DOM tree slim
                if (depth > 1) {
                    const tagName = node.tagName.toLowerCase();
                    // Skip style, svg, script and similar elements
                    if (['style', 'svg', 'script', 'noscript', 'path', 'link', 'meta'].includes(tagName)) {
                        return null;
                    }
                    
                    // Only include divs and spans if they have useful content or are interactive
                    if ((tagName === 'div' || tagName === 'span') && !isInteractive(node)) {
                        // Check if it has interactive children
                        let hasInteractiveChild = false;
                        for (const child of node.children) {
                            if (isInteractive(child)) {
                                hasInteractiveChild = true;
                                break;
                            }
                        }
                        
                        // Skip if no interesting content and no interactive children
                        if (!hasInteractiveChild && (!node.textContent || node.textContent.trim().length < 5)) {
                            return null;
                        }
                    }
                }
                
                const result = {
                    tag: node.tagName.toLowerCase(),
                    children: []
                };
                
                // Add attributes (simplified)
                const attrs = getSimplifiedAttributes(node);
                if (Object.keys(attrs).length > 0) {
                    result.attrs = attrs;
                }
                
                // Add text content if exists and useful
                const text = getSimplifiedText(node);
                if (text) {
                    result.text = text;
                }
                
                // Add position information (for viewport elements)
                if (isVisibleInViewport(node) && (isInteractive(node) || depth <= 1)) {
                    const rect = node.getBoundingClientRect();
                    result.position = {
                        x: Math.round(rect.left),
                        y: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        inViewport: true
                    };
                }
                
                // Mark interactive elements explicitly with more details
                if (isInteractive(node)) {
                    result.interactive = true;
                    result.interactionType = getInteractionType(node);
                    
                    // Add selector suggestions
                    const selectors = getSelectorSuggestions(node);
                    if (selectors.length > 0) {
                        result.selectors = selectors;
                    }
                }
                
                // Generate selector suggestions for interactive elements
                function getSelectorSuggestions(element) {
                    const selectors = [];
                    const tagName = element.tagName.toLowerCase();
                    
                    // ID selector (most specific)
                    if (element.id) {
                        selectors.push(`#${element.id}`);
                    }
                    
                    // Attribute selectors
                    if (element.getAttribute('name')) {
                        selectors.push(`${tagName}[name="${element.getAttribute('name')}"]`);
                    }
                    
                    if (element.getAttribute('data-testid')) {
                        selectors.push(`[data-testid="${element.getAttribute('data-testid')}"]`);
                    }
                    
                    // Type + text combination for buttons and links
                    if ((tagName === 'button' || tagName === 'a') && element.innerText.trim()) {
                        const buttonText = element.innerText.trim();
                        if (buttonText.length < 20) {
                            selectors.push(`${tagName}:has-text("${buttonText}")`);
                        }
                    }
                    
                    // For inputs, add type selectors
                    if (tagName === 'input' && element.getAttribute('type')) {
                        selectors.push(`input[type="${element.getAttribute('type')}"]`);
                    }
                    
                    return selectors.slice(0, 3); // Limit to top 3 suggestions
                }
                
                // Process children recursively
                // Limit number of children at deeper levels
                const maxChildren = depth === 0 ? 100 : depth === 1 ? 30 : depth === 2 ? 20 : 10;
                let childrenCount = 0;
                
                for (const child of node.childNodes) {
                    if (childrenCount >= maxChildren) {
                        result.children.push({ type: 'truncated', message: `${node.childNodes.length - maxChildren} more children omitted...` });
                        break;
                    }
                    
                    const childResult = extractNode(child, depth + 1, maxDepth);
                    if (childResult) {
                        result.children.push(childResult);
                        childrenCount++;
                    }
                }
                
                return result;
            }
            
            // Find main page sections (header, nav, main, etc.)
            function identifyPageSections() {
                const sections = {};
                
                // Try to identify important page regions
                const selectors = {
                    header: 'header, [role="banner"], .header, #header',
                    navigation: 'nav, [role="navigation"], .nav, .navigation, #nav',
                    main: 'main, [role="main"], .main, #main, article, .content, #content',
                    search: 'input[type="search"], form input[name="q"], .search-form, .searchform',
                    footer: 'footer, [role="contentinfo"], .footer, #footer'
                };
                
                for (const [name, selector] of Object.entries(selectors)) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        sections[name] = elements.length === 1 ? '1 element found' : `${elements.length} elements found`;
                    }
                }
                
                return sections;
            }
            
            // Find forms on the page
            function analyzeForms() {
                const forms = Array.from(document.forms);
                const formData = [];
                
                for (const form of forms) {
                    const formInfo = {
                        id: form.id || null,
                        action: form.action || null,
                        method: form.method || 'get',
                        fields: []
                    };
                    
                    // Get form inputs
                    const inputs = form.querySelectorAll('input, select, textarea, button[type="submit"]');
                    for (const input of inputs) {
                        const type = input.type || input.tagName.toLowerCase();
                        if (['submit', 'image', 'reset', 'button'].includes(type)) {
                            formInfo.submitButton = {
                                type: type,
                                value: input.value || null,
                                text: input.innerText || input.value || null
                            };
                        } else {
                            formInfo.fields.push({
                                name: input.name || null,
                                type: type,
                                id: input.id || null,
                                required: input.required || false
                            });
                        }
                    }
                    
                    formData.push(formInfo);
                }
                
                return formData;
            }
            
            try {
                const bodyElement = document.body;
                if (!bodyElement) return { error: "Document body not found" };
                
                // Get page metadata
                const metadata = {
                    url: document.location.href,
                    title: document.title,
                    description: document.querySelector('meta[name="description"]')?.getAttribute('content') || null,
                    siteName: document.querySelector('meta[property="og:site_name"]')?.getAttribute('content') || null,
                    doctype: document.doctype ? document.doctype.name : 'unknown',
                    viewport: document.querySelector('meta[name="viewport"]')?.getAttribute('content') || null,
                    lang: document.documentElement.lang || null
                };
                
                // Detect if this is possibly a search page
                const isSearchPage = metadata.url.includes('search') || 
                                    metadata.url.includes('q=') || 
                                    metadata.title.toLowerCase().includes('search') ||
                                    !!document.querySelector('input[type="search"], input[name="q"]');
                
                if (isSearchPage) {
                    metadata.pageType = 'search';
                }
                
                // Analyze page sections
                const pageSections = identifyPageSections();
                
                // Analyze forms if present
                const forms = analyzeForms();
                
                // Extract main DOM tree
                const domTree = extractNode(bodyElement);
                
                // Find searchboxes specifically
                const searchBoxes = [];
                const searchSelectors = [
                    'input[type="search"]', 
                    'input[name="q"]', 
                    'input[name="query"]',
                    'input[placeholder*="Search" i]',
                    'input[aria-label*="Search" i]',
                    'form input[type="text"]'
                ];
                
                for (const selector of searchSelectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        elements.forEach(el => {
                            searchBoxes.push({
                                tag: el.tagName.toLowerCase(),
                                type: el.getAttribute('type'),
                                name: el.getAttribute('name'),
                                id: el.getAttribute('id'),
                                placeholder: el.getAttribute('placeholder'),
                                selector: selector
                            });
                        });
                    }
                }
                
                return {
                    metadata: metadata,
                    pageSections: pageSections,
                    searchBoxes: searchBoxes.length > 0 ? searchBoxes.slice(0, 3) : null, // Limit to top 3
                    forms: forms.length > 0 ? forms : null,
                    body: domTree
                };
            } catch (error) {
                return { error: `Error extracting DOM: ${error.message}` };
            }
        }
        """

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        
        page = get_current_page(self.sync_browser)
        
        try:
            # Execute the DOM extraction script without timeout parameter
            result = page.evaluate(self._dom_extract_script())
            
            # Format the result
            if result is None:
                return "No elements found in the page."
            elif isinstance(result, dict) and "error" in result:
                return f"Error: {result['error']}"
            else:
                # Process results to add suggested actions based on the page content
                if 'searchBoxes' in result and result['searchBoxes']:
                    result['actionSuggestions'] = self._generate_action_suggestions(result)
                
                # Return a nicely formatted but compact JSON result
                return json.dumps(result, indent=1)
                
        except Exception as e:
            return f"Error extracting DOM tree: {str(e)}"

    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        
        page = await aget_current_page(self.async_browser)
        
        try:
            # Execute the DOM extraction script without timeout parameter
            result = await page.evaluate(self._dom_extract_script())
            
            # Format the result
            if result is None:
                return "No elements found in the page."
            elif isinstance(result, dict) and "error" in result:
                return f"Error: {result['error']}"
            else:
                # Process results to add suggested actions based on the page content
                if 'searchBoxes' in result and result['searchBoxes']:
                    result['actionSuggestions'] = self._generate_action_suggestions(result)
                
                # Return a nicely formatted but compact JSON result
                return json.dumps(result, indent=1)
                
        except Exception as e:
            return f"Error extracting DOM tree: {str(e)}"
    
    def _generate_action_suggestions(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate action suggestions based on the page content analysis."""
        suggestions = []
        
        # If search boxes found, suggest using them
        if result.get('searchBoxes'):
            for box in result['searchBoxes']:
                if 'selector' in box:
                    suggestions.append({
                        "action": "search",
                        "description": f"You can search using the search box",
                        "selector": box['selector'],
                        "tool": "input_text"
                    })
        
        # If forms found, suggest filling them
        if result.get('forms'):
            for form in result['forms']:
                if form.get('fields') and len(form['fields']) > 0:
                    suggestions.append({
                        "action": "fill_form",
                        "description": f"You can fill out a form with {len(form['fields'])} fields",
                        "formId": form.get('id'),
                        "tool": "input_text"
                    })
        
        # Add navigation suggestions if navigation sections found
        if result.get('pageSections', {}).get('navigation'):
            suggestions.append({
                "action": "navigate",
                "description": "You can navigate to different sections using the navigation menu",
                "tool": "click_element"
            })
        
        return suggestions 