#!/usr/bin/env python3

import argparse
import asyncio
import os

import random
from typing import Literal, TypedDict
import uuid

import nest_asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from pydantic import SecretStr

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_tool_calling_agent
from langchain.agents import AgentExecutor

# Playwright tools
from langchain_community.tools.playwright.click import ClickTool
from langchain_community.tools.playwright.current_page import CurrentWebPageTool
from langchain_community.tools.playwright.extract_dom_tree import ExtractDOMTreeTool
from langchain_community.tools.playwright.extract_hyperlinks import ExtractHyperlinksTool
from langchain_community.tools.playwright.extract_text import ExtractTextTool
from langchain_community.tools.playwright.get_elements import GetElementsTool
from langchain_community.tools.playwright.input_text import InputTextTool
from langchain_community.tools.playwright.navigate import NavigateTool
from langchain_community.tools.playwright.navigate_back import NavigateBackTool
from langchain_community.tools.playwright.press_key import PressKeyTool
from langchain_community.tools.playwright.screenshot import ScreenshotTool
from langchain_community.tools.playwright.scroll import ScrollTool
from langchain_community.tools.playwright.dragndrop import DragAndDropTool
from langchain_community.tools.playwright.download_file import DownloadFileTool
from langchain_community.tools.playwright.output_to_file import OutputToFileTool
from langchain_community.tools.playwright.http_request import HttpRequestTool


load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

nest_asyncio.apply()

# Define shared state
class AgentState(TypedDict):
    input: str
    step: Literal["planning", "navigating"]
    result: str
    steps: list[str]
    history: list[str]

async def main():
    # Set up LLM
    
    # stup for using ollama
    # llm = ChatOllama(
    #     model="Hituzip/gemma3-tools:4b",
    #     stop=["<end_of_turn>"],
    #     temperature=0.8,
    #     num_ctx=8196,
    #     top_k=64,
    #     top_p=0.95,
    #     num_thread=16,
    # )
    
    
    # stup for using Google Gemini
    model_name = "gemini-2.5-pro-preview-05-06"
    llm = ChatGoogleGenerativeAI(model=model_name, api_key=SecretStr(api_key))

    # Launch Playwright
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        # executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        headless=False  # Optional: set to True if you want headless mode
    )
    page = await browser.new_page(no_viewport=True)

    # Create tools
    tools = [
        NavigateTool(page=page, async_browser=browser),
        NavigateBackTool(page=page, async_browser=browser),
        ExtractDOMTreeTool(page=page, async_browser=browser),
        ClickTool(page=page, async_browser=browser),
        InputTextTool(page=page, async_browser=browser),
        PressKeyTool(page=page, async_browser=browser),
        ScreenshotTool(page=page, async_browser=browser),
        CurrentWebPageTool(page=page, async_browser=browser),
        ExtractTextTool(page=page, async_browser=browser),
        ExtractHyperlinksTool(page=page, async_browser=browser),
        GetElementsTool(page=page, async_browser=browser),
        ScrollTool(page=page, async_browser=browser),
        DragAndDropTool(page=page, async_browser=browser),
        DownloadFileTool(),
        OutputToFileTool(),
        HttpRequestTool(),
    ]

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools=tools, parallel_tool_calls=False)

    # Navigation prompt
    navigator_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are a web automation agent that can browse websites and perform tasks as requested.

EFFICIENT WORKFLOW - follow this exactly:
1. Navigate to requested URL. The URLS must start with 'https://'
2. Aways accept cookies when asked
3. Call extract_dom_tree ONCE to analyze the page structure
4. Examine the DOM to identify relevant elements (forms, buttons, inputs, etc.)
5. Perform ONE action based on the task requirements
6. ONLY call extract_dom_tree again if the page state has changed
7. Continue with the next action until the task is complete
8. Make sure ALL requirements are satisfied

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
- When exporting to JSON, first try to capture and organize any inherent data structure (e.g. lists, tables, key–value pairs). 
  If the source offers no clear schema, fall back to extracting text and then wrap it in a sensible JSON format.

"""),
        HumanMessagePromptTemplate.from_template("{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    # Navigator agent (executes tool calls)
    navigator_agent = AgentExecutor(
        agent=create_tool_calling_agent(llm_with_tools, tools, navigator_prompt),
        tools=tools,
        max_iterations=120,
        max_execution_time=360,
        verbose=True,  # <-- enable logging
    )

    # Build the LangGraph
    workflow = StateGraph(AgentState)

    async def planner_node(state: AgentState) -> AgentState:
        return {
            "input": state["input"],
            "step": "navigating",
            "result": "",
            "steps": []
        }

    async def navigator_node(state: AgentState) -> AgentState:
        dom_tree = await ExtractDOMTreeTool(page=page, async_browser=browser).arun({})
        input_with_dom = f"{state['input']}\n\n[DOM]:\n{dom_tree}"
        
        steps = state.get("steps", [])
        history = state.get("history", [])
        current_input = input_with_dom

        while True:
            await page.wait_for_timeout(random.randint(1,3))
            output = await navigator_agent.ainvoke({"input": current_input})

            for tool_call, result in output.get("intermediate_steps", []):
                step_text = f"Tool: {tool_call.tool}, Args: {tool_call.tool_input}, Result: {result}"
                steps.append(step_text)
                history.append(step_text)

            if "output" in output and output["output"]:
                break  # task complete
            else:
                # Refresh DOM and continue
                dom_tree = await ExtractDOMTreeTool(page=page, async_browser=browser).arun({})
                current_input = f"{state['input']}\n\n[DOM]:\n{dom_tree}"

        return {
            "input": state["input"],
            "step": "done",
            "result": output.get("output", ""),
            "steps": steps,
            "history": history
        }
        
    checkpointer = MemorySaver()

    workflow.add_node("planner", planner_node)
    workflow.add_node("navigator", navigator_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "navigator")
    workflow.add_edge("navigator", END)

    graph = workflow.compile(checkpointer=checkpointer)

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="Prompt for the agent")
    args = parser.parse_args()

    # Run graph
    thread_id = str(uuid.uuid4())

    await graph.ainvoke({
        "input": args.prompt,
        "step": "planning",
        "result": "",
        "steps": [],
        "history": []
    }, config={"configurable": {"thread_id": thread_id}})
    
    print(f"\n✅ Job finished")
    
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
