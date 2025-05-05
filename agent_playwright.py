#!/usr/bin/env python3
"""
Example of using the Playwright tools with LangChain's agent framework.
This demonstrates how to set up a web browsing and data extraction agent.
"""

import argparse
import asyncio
import time
import functools
from datetime import datetime
from pathlib import Path
from typing import List

import nest_asyncio

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool, BaseTool
from langchain_ollama import ChatOllama

# Import the PlayWright tools directly from LangChain
from langchain_community.tools.playwright.click import ClickTool
from langchain_community.tools.playwright.current_page import CurrentWebPageTool  
from langchain_community.tools.playwright.extract_text import ExtractTextTool
from langchain_community.tools.playwright.extract_hyperlinks import ExtractHyperlinksTool
from langchain_community.tools.playwright.extract_dom_tree import ExtractDOMTreeTool
from langchain_community.tools.playwright.get_elements import GetElementsTool
from langchain_community.tools.playwright.navigate import NavigateTool
from langchain_community.tools.playwright.navigate_back import NavigateBackTool
from langchain_community.tools.playwright.screenshot import ScreenshotTool
from langchain_community.tools.playwright.input_text import InputTextTool
from langchain_community.tools.playwright.press_key import PressKeyTool
from playwright.async_api import async_playwright

# Apply nest_asyncio to allow running asyncio in Jupyter notebooks
nest_asyncio.apply()

# Create a global lock for sequential tool execution
tool_lock = asyncio.Lock()

# Function to wrap tools with a lock
async def with_lock(func, *args, **kwargs):
    """Run a function with a lock to prevent parallel execution."""
    print(f"Waiting for lock to execute tool")
    async with tool_lock:
        print(f"Acquired lock, executing tool")
        try:
            # Run the actual function
            result = await func(*args, **kwargs)
            
            # Wait a small delay after execution
            await asyncio.sleep(1)
            return result
        finally:
            print(f"Released lock")

def wrap_tools_with_lock(tools):
    """Apply lock to all tools to ensure sequential execution."""
    for tool in tools:
        if hasattr(tool, '_arun'):
            original_arun = tool._arun
            tool._arun = functools.partial(with_lock, original_arun)
    return tools

async def main():
    """Main function to run the agent."""
    
    # Create the LLM - you can replace with any LLM that supports tool calling
    llm = ChatOllama(
        model="Hituzip/gemma3-tools:4b",
        stop=["<end_of_turn>"],
        num_ctx=8196,
        temperature=0.7,  # Slightly reduced for more consistent output
        top_k=64,
        top_p=0.95,
        num_threads=8,
        gpu_layers=10
    )
    
    # Launch Playwright directly
    print("Launching browser...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    
    # Create tools using the actual page object
    tools = [
        NavigateTool(page=page, async_browser=browser),
        ExtractDOMTreeTool(page=page, async_browser=browser),
        ClickTool(page=page, async_browser=browser),
        InputTextTool(page=page, async_browser=browser),
        PressKeyTool(page=page, async_browser=browser),
        ScreenshotTool(page=page, async_browser=browser),
        CurrentWebPageTool(page=page, async_browser=browser),
        ExtractTextTool(page=page, async_browser=browser),
        ExtractHyperlinksTool(page=page, async_browser=browser),
        GetElementsTool(page=page, async_browser=browser),
    ]
    
    # Wrap all tools with the lock to ensure sequential execution
    tools = wrap_tools_with_lock(tools)
    
    # Set up the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content="""You are a web automation agent that can browse websites and perform tasks as requested.

EFFICIENT WORKFLOW - follow this exactly:
1. Navigate to requested URL
2. Call extract_dom_tree ONCE to analyze the page structure
3. Examine the DOM to identify relevant elements (forms, buttons, inputs, etc.)
4. Perform ONE action based on the task requirements
5. ONLY call extract_dom_tree again if the page state has changed
6. Continue with the next action until the task is complete

GENERAL GUIDELINES:
- Extract the DOM tree ONCE after navigation to understand page structure
- Extract the DOM again ONLY after actions that change the page
- Use selectors found in the DOM extraction (don't hardcode selectors)
- Complete all requested actions in the proper sequence
- Take screenshots when explicitly requested or to show final results

COMMON WEB TASKS:
- For search tasks: Input text and press Enter to submit the query
- For form filling: Find form fields, enter data, and submit the form
- For navigation: Identify and click on relevant links or buttons
- For extraction: Extract text or data from relevant elements

IMPORTANT NOTES:
- For screenshots, use take_screenshot with simple parameters:
  take_screenshot with {"filename": "results"}
- Avoid using selector parameters for screenshots to prevent errors
- Use press_key to submit forms or trigger actions (e.g., Enter key)
- After inputting text in forms, always take the appropriate action to submit
- For any page, analyze the DOM first to discover the correct selectors
"""),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    
    # Create the agent with the tools
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_execution_time=360,
        verbose=True,
        handle_parsing_errors=True,  # Better error handling for tool parsing
        early_stopping_method="force",  # Force sequential execution
        max_iterations=12,           # Increased to allow for more DOM extractions
        return_intermediate_steps=True,
        run_parallel=False,          # Explicitly disable parallel execution
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Web browsing and data extraction agent.')
    parser.add_argument('prompt', help='Query or task for the agent')
    args = parser.parse_args()
    query = args.prompt
    
    print(f"Query: {query}")
    print("NOTE: Tools will be executed sequentially using a lock")
    
    try:
        # Run the agent
        result = await agent_executor.ainvoke({"input": query})
        print("\nResult:")
        print(result["output"])
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        # Make sure to close the browser
        print("Closing browser resources...")
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 