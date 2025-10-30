from langchain.tools import tool
from langgraph.graph import StateGraph, END
from langchain_ollama import OllamaLLM
from datetime import datetime
from state_schemas import TimeManagementState, GoalFrequency, GoalStatus


def create_initial_llm_node():
    """
    Returns a function (node) that runs Ollama LLM to gather initial user data
    and updates the state.
    """
    
    # LLM Tanımı
    llm = OllamaLLM(model="gpt-oss:20b-cloud", temperature=0.1)

    def initialize_user_node(state: TimeManagementState) -> TimeManagementState:
        """
        First conversation with user to initialize their personal info and first goals.
        """
        # Kullanıcıdan alınacak temel bilgiler
        user_prompt = f"""
        You are a time management assistant.
        The user just started using you. Your goal is to collect basic information to initialize their time tracking state.

        Please ask the user questions like:
        - What's your name or nickname?
        - What kind of goals are you currently focusing on (daily, weekly, etc.)?
        - Do you have any routines or recurring tasks you want to track?
        - How would you describe your main priorities right now?

        Then summarize the user's answers as a structured JSON with these keys:
        {{
            "user_name": str,
            "goals": [
                {{
                    "title": str,
                    "description": str,
                    "frequency": "daily|weekly|monthly",
                    "priority": int
                }}
            ]
        }}
        """

        # LLM çağrısı
        response = llm.invoke(user_prompt)
        print("🧠 LLM Response:", response)

        # JSON yanıtını ayrıştır
        import json
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {"user_name": "Unknown", "goals": []}

        # Şu anki zaman
        now = datetime.now().isoformat()

        # Goal listesi oluştur
        user_goals = []
        for i, g in enumerate(parsed.get("goals", []), start=1):
            user_goals.append({
                "id": i,
                "user_id": state.get("user_id", "local_user"),
                "title": g.get("title"),
                "description": g.get("description", ""),
                "frequency": GoalFrequency(g.get("frequency", "daily")),
                "status": GoalStatus.NOT_STARTED,
                "target_value": 0.0,
                "current_value": 0.0,
                "created_at": now,
                "updated_at": now,
                "due_date": "",
                "priority": g.get("priority", 3),
            })

        # State güncelle
        state["user_name"] = parsed.get("user_name", "Unknown")
        state["all_goals"] = user_goals
        state["last_sync_with_db"] = now
        state["action_taken"] = "initialized_user_profile"
        state["is_db_updated"] = True

        return state

    return initialize_user_node
