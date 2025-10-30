"""
State schemas for LangGraph time management and personal development tracking system.
SQLite-backed state for goals, plans, and self-evaluation.
"""

from typing import Annotated
from typing_extensions import TypedDict
from datetime import datetime
from enum import Enum

# ============================================================================
# Enums for State Management
# ============================================================================

class GoalFrequency(str, Enum):
    """Frequency types for goals and plans"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class GoalStatus(str, Enum):
    """Status of goals"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ON_HOLD = "on_hold"


class PlanStatus(str, Enum):
    """Status of plans"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


# ============================================================================
# Individual Goal/Plan Record Types
# ============================================================================

class Goal(TypedDict, total=False):
    """Individual goal record"""
    id: int
    user_id: str
    title: str
    description: str
    frequency: GoalFrequency  # daily, weekly, monthly, yearly
    status: GoalStatus
    target_value: float  # for quantifiable goals
    current_value: float
    created_at: str  # ISO format datetime
    updated_at: str
    due_date: str
    priority: int  # 1-5, where 5 is highest


class Plan(TypedDict, total=False):
    """Individual plan record"""
    id: int
    user_id: str
    goal_id: int  # linked to goal
    title: str
    description: str
    frequency: GoalFrequency  # weekly, monthly, yearly
    status: PlanStatus
    start_date: str
    end_date: str
    tasks: list[str]  # breakdown of actions
    progress_percentage: float
    created_at: str
    updated_at: str


class SelfEvaluation(TypedDict, total=False):
    """Self-evaluation record for tracking progress"""
    id: int
    user_id: str
    goal_id: int
    plan_id: int
    evaluation_date: str
    score: float  # 1-10
    notes: str
    achievements: list[str]
    challenges: list[str]
    next_actions: list[str]
    created_at: str


# ============================================================================
# LangGraph State Schema
# ============================================================================

class TimeManagementState(TypedDict):
    """
    Main state schema for time management and personal development tracking.
    
    This state is used throughout the LangGraph workflow to:
    1. Track user's long-term goals
    2. Manage weekly/monthly/yearly plans
    3. Store self-evaluation progress
    4. Maintain conversation history
    5. Store intermediate reasoning and decisions
    """
    
    # User Information
    user_id: str
    user_name: str
    
    # Conversation State
    messages: list[dict]  # Chat history
    current_input: str  # Current user query
    
    # Goals Management
    all_goals: list[Goal]  # All goals for this user
    current_goal_id: int  # Currently being worked on
    goals_to_evaluate: list[Goal]  # Goals pending evaluation
    
    # Plans Management
    weekly_plans: list[Plan]  # Current week's plans
    monthly_plans: list[Plan]  # Current month's plans
    yearly_plans: list[Plan]  # Current year's plans
    
    # Self-Evaluation
    recent_evaluations: list[SelfEvaluation]  # Last 5-10 evaluations
    evaluation_insights: dict  # Patterns and insights from evaluations
    
    # System State
    last_sync_with_db: str  # Last database update timestamp
    action_taken: str  # What action was just taken
    reasoning: str  # LLM's reasoning for decisions
    next_step: str  # What should happen next
    
    # Database Operations
    database_path: str  # Path to SQLite database
    is_db_updated: bool  # Flag for database changes
    
    # SQL Agent Specific
    sql_query: str  # Generated SQL query
    sql_result: str  # Result from SQL execution
    intent: str  # Query intent (select, insert, update, delete, create)


# ============================================================================
# Reducer Functions for State Updates
# ============================================================================

def messages_reducer(current: list[dict], updates: list[dict]) -> list[dict]:
    """Append new messages to conversation history"""
    if current is None:
        return updates
    return current + updates


def goals_reducer(current: list[Goal], updates: list[Goal]) -> list[Goal]:
    """Update or add goals, avoiding duplicates"""
    if current is None:
        return updates
    
    # Create dict keyed by goal id for easy updates
    goals_dict = {g.get("id"): g for g in current if g.get("id")}
    
    # Update with new goals
    for goal in updates:
        if goal.get("id"):
            goals_dict[goal["id"]] = goal
        else:
            # New goal without id, just append
            current.append(goal)
    
    return list(goals_dict.values())


def plans_reducer(current: list[Plan], updates: list[Plan]) -> list[Plan]:
    """Update or add plans"""
    if current is None:
        return updates
    
    plans_dict = {p.get("id"): p for p in current if p.get("id")}
    for plan in updates:
        if plan.get("id"):
            plans_dict[plan["id"]] = plan
        else:
            current.append(plan)
    
    return list(plans_dict.values())


# ============================================================================
# State Initialization
# ============================================================================

def create_initial_state(user_id: str, user_name: str, db_path: str = "./databases/timemanagement.db") -> TimeManagementState:
    """Create initial state for a new user session"""
    now = datetime.now().isoformat()
    
    return TimeManagementState(
        user_id=user_id,
        user_name=user_name,
        messages=[],
        current_input="",
        all_goals=[],
        current_goal_id=0,
        goals_to_evaluate=[],
        weekly_plans=[],
        monthly_plans=[],
        yearly_plans=[],
        recent_evaluations=[],
        evaluation_insights={},
        last_sync_with_db=now,
        action_taken="",
        reasoning="",
        next_step="",
        database_path=db_path,
        is_db_updated=False,
        sql_query="",
        sql_result="",
        intent="",
    )
