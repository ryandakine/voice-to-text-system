from src.config import Config

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost of a request based on token usage.
    """
    input_cost = (input_tokens / 1_000_000) * Config.INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * Config.OUTPUT_COST_PER_1M
    return input_cost + output_cost
