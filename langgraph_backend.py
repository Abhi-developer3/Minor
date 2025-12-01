# langgraph_backend.py
import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

from data_base.database import conn  
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


def chat_node(state: State):
    model = genai.GenerativeModel("gemini-2.5-flash") 
    # Build history from full state
    history = []
    for msg in state["messages"]:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        history.append({"role": role, "parts": [msg.content]})

    chat = model.start_chat(history=history[:-1])  # Exclude last user message (already in send_message)

    # Get last user message
    last_msg = state["messages"][-1]
    if not isinstance(last_msg, HumanMessage):
        return {"messages": [AIMessage(content="No user message.")]}

    try:
        resp = chat.send_message(last_msg.content)
        return {"messages": [AIMessage(content=resp.text)]}
    except Exception as e:
        return {"messages": [AIMessage(content="Sorry, I couldn't respond. Try again.")]}


checkpointer = SqliteSaver(conn=conn)
graph = StateGraph(State)
graph.add_node("chat", chat_node)
graph.add_edge(START, "chat")
graph.add_edge("chat", END)
chatbot = graph.compile(checkpointer=checkpointer)