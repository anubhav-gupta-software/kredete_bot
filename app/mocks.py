import enum

MODEL_ACTION_COST = 2
WEB_SEARCH_COST = 5
MAX_STEPS = 5


class Action(enum.Enum):
    CALL_TOOL = "CALL_TOOL"
    FINISH = "FINISH"


def decide_next_action(step_number, goal, last_output):
    # Deterministic policy for demo:
    # Default: steps 1-2 -> CALL_TOOL; step 3 -> FINISH
    if step_number <= 2:
        return Action.CALL_TOOL
    return Action.FINISH


def mock_web_search(query, simulate_failure=False):
    # deterministic fake tool: returns a string or raises
    if simulate_failure:
        raise RuntimeError("TOOL_ERROR: simulated failure")
    return f"search_results_for:{query}"
