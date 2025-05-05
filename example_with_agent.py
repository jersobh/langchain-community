#!/usr/bin/env python3
"""
Example of using the Playwright tools with LangChain's agent framework.
This demonstrates how to set up a web browsing and data extraction agent.
"""

import argparse
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import List

import nest_asyncio

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

# Import the PlayWrightBrowserToolkit and browser creation utility
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import (
    create_async_playwright_browser,
)


# Apply nest_asyncio to allow running asyncio in Jupyter notebooks
nest_asyncio.apply()


async def main():
    """Main function to run the agent."""
    
    # Create the LLM - you can replace with any LLM that supports tool calling
    llm = ChatOllama(
        model="Hituzip/gemma3-tools:4b",
        stop=["<end_of_turn>"],
        num_ctx=8196,
        temperature=1,
        top_k=64,
        top_p=0.95,
        num_threads=8,
        gpu_layers=10
    )
    # Alternative: llm = ChatOllama(model="qwen3:8b")
    
    # Create the async browser - setting headless=False to see the browser while testing
    async_browser = create_async_playwright_browser(headless=False)
    
    # Create the toolkit and get the tools
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    tools = toolkit.get_tools()
    
    # Set up the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", """You are a powerful web automation and data extraction agent.
            
You can browse the web, interact with pages, and extract information using various tools. Aways extract the DOM tree to be able to see the existing elements.

CRITICAL INSTRUCTIONS:
- The extract_dom_tree tool takes NO parameters. Call it exactly as: extract_dom_tree()
- NEVER try to pass parameters to extract_dom_tree - it will fail if you do

When analyzing a page, always follow this sequence:
1. Navigate to the URL
2. IMPORTANT: Call extract_dom_tree() with NO parameters to understand the structure of the page
3. Look for interactive elements in the DOM tree (marked with "interactive": true)
4. Use appropriate tools to interact with these elements based on their type

For search inputs and form filling:
- To search, use the input_text tool to enter text into search fields
- Common search field selectors: input[type='search'], input[name='q'], .search-input
- After filling a search box, use press_key with key='Enter' to submit the search
- Example search sequence:
  1. input_text(selector="input[type='search']", text="your search term")
  2. press_key(key="Enter", selector="input[type='search']")

Key capabilities:
- Navigate to websites and back/forward in history
- Extract text, hyperlinks, and page structure
- Extract the DOM tree to identify all interactive elements (use NO parameters!)
- Interact with forms through clicking, typing, key presses, and selecting options
- Take screenshots of pages or specific elements

For clicking elements:
- Be specific with selectors - use element IDs, unique classes, or detailed paths
- For elements that trigger navigation, set wait_for_navigation=true
- For elements that update the page without navigation, use wait_for_timeout=500 (milliseconds)
- For elements that might be obscured or hidden, use force=true
- If a click fails, try again with more precise selectors or force=true

For all selectors:
- Prefer using IDs (#some-id) over classes (.some-class)
- Be as specific as possible (e.g., button#submit instead of just button)
- Use attribute selectors when needed (e.g., [data-test-id="submit-button"])
- If multiple elements match, narrow down using :nth-child() or more specific selectors

When examining the DOM tree:
- Look for elements with "interactive": true flag
- Check "tag" values to understand element types
- Use "attrs" like id, class, type to create precise selectors
- Note "text" content to understand what the element is for

Present your findings in a clear, structured manner.
"""),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
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
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Web browsing and data extraction agent.')
    parser.add_argument('prompt', help='Query or task for the agent')
    args = parser.parse_args()
    query = args.prompt
    
    print(f"Query: {query}")
    
    try:
        # Run the agent
        result = await agent_executor.ainvoke({"input": query})
        print("\nResult:")
        print(result["output"])
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Make sure to close the browser
        await async_browser.close()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())