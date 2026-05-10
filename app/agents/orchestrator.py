import os
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    payload: str
    system_prompt: str
    intent: str
    spatial_ctx: dict
    ha_states: dict
    agent_plan: list
    tool_calls: list
    response: str

class Orchestrator:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set. Orchestrator will run in mock mode.")
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", 
                google_api_key=api_key
            )
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)

        graph.add_node("intent_classifier", self.classify_intent)
        graph.add_node("comfort_agent", self.run_comfort_agent)
        graph.add_node("security_agent", self.run_security_agent)
        graph.add_node("query_agent", self.run_query_agent)
        graph.add_node("command_executor", self.execute_commands)
        graph.add_node("response_formatter", self.format_response)

        graph.set_entry_point("intent_classifier")

        graph.add_conditional_edges("intent_classifier", self.route_by_intent, {
            "comfort": "comfort_agent",
            "security": "security_agent",
            "query": "query_agent",
            "unknown": "response_formatter"
        })

        for agent in ["comfort_agent", "security_agent", "query_agent"]:
            graph.add_edge(agent, "command_executor")

        graph.add_edge("command_executor", "response_formatter")
        graph.add_edge("response_formatter", END)

        return graph.compile()

    async def classify_intent(self, state: AgentState) -> Dict[str, Any]:
        if not self.llm:
            # Mock intent classification
            payload = state["payload"].lower()
            if any(word in payload for word in ["light", "temp", "blind", "warm", "cool"]):
                return {"intent": "comfort"}
            if any(word in payload for word in ["lock", "camera", "secure", "door"]):
                return {"intent": "security"}
            return {"intent": "query"}

        prompt = f"Classify the following smart home request intent into one of: comfort, security, query, unknown.\nRequest: {state['payload']}\nIntent:"
        try:
            response = await self.llm.ainvoke(prompt)
            intent = response.content.strip().lower()
            if intent not in ["comfort", "security", "query"]:
                intent = "unknown"
            return {"intent": intent}
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return {"intent": "unknown"}

    def route_by_intent(self, state: AgentState) -> str:
        return state["intent"]

    async def run_comfort_agent(self, state: AgentState) -> Dict[str, Any]:
        # To be expanded with specific comfort logic
        return {"agent_plan": ["Analyzing comfort request"]}

    async def run_security_agent(self, state: AgentState) -> Dict[str, Any]:
        # To be expanded with security logic
        return {"agent_plan": ["Analyzing security request"]}

    async def run_query_agent(self, state: AgentState) -> Dict[str, Any]:
        # To be expanded with query logic
        return {"agent_plan": ["Analyzing information query"]}

    async def execute_commands(self, state: AgentState) -> Dict[str, Any]:
        # To be expanded with tool execution
        return {"tool_calls": []}

    async def format_response(self, state: AgentState) -> Dict[str, Any]:
        intent = state.get("intent", "unknown")
        response = f"I've processed your {intent} request."
        if intent == "unknown":
            response = "I'm sorry, I couldn't understand that request."
        return {"response": response}

    async def run(self, payload: str, system_prompt: str, spatial_ctx: dict, ha_states: dict) -> Dict[str, Any]:
        initial_state = {
            "payload": payload,
            "system_prompt": system_prompt,
            "spatial_ctx": spatial_ctx,
            "ha_states": ha_states,
            "intent": "",
            "agent_plan": [],
            "tool_calls": [],
            "response": ""
        }
        return await self.graph.ainvoke(initial_state)

orchestrator = Orchestrator()
