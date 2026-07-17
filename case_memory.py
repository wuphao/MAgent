def init_case_memory(raw_case):
    return {
        "case_id": raw_case["case_id"],
        "basic_info": raw_case["basic_info"],
        "raw_inputs": raw_case["raw_inputs"],
        "tool_results": {},
        "agent_outputs": {},
        "conflicts": [],
        "controller_output": {},
        "final_report": {},
    }
