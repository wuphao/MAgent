from agents.base_agent import BaseAgent
from agents.base_agent import BaseAgent
from tools.diamond_tool import DiamondTool
from tools.mri_tool import MRIAtrophyTool
from tools.pet_tool import PETAmyloidTool


class ImagingAgent(BaseAgent):
    name = "影像Agent"

    def call_tools(self, memory):
        pet = PETAmyloidTool().run(memory["raw_inputs"]["pet_path"])
        mri = MRIAtrophyTool().run(memory["raw_inputs"]["mri_path"])
        try:
            diamond = DiamondTool().run(memory["raw_inputs"])
        except Exception as exc:
            diamond = {"error": str(exc)}
        memory["tool_results"]["imaging"] = {"pet": pet, "mri": mri, "diamond": diamond}
        return {"pet": pet, "mri": mri, "diamond": diamond}

    def reason(self, tool_results):
        pet = tool_results["pet"]
        mri = tool_results["mri"]
        diamond = tool_results.get("diamond") or {}

        if diamond.get("risk_signal"):
            risk_signal = diamond["risk_signal"]
            abnormal = bool(diamond.get("abnormal", False))
            evidence = [
                f"DiaMond预测={diamond.get('pred_label', '未知')}",
                f"DiaMond概率={diamond.get('probabilities', {})}",
                f"全脑SUVR={pet['global_suvr']}",
                f"Centiloid={pet['centiloid']}",
                f"MRI海马萎缩={mri['hippocampal_atrophy']}",
            ]
        else:
            risk_signal = "高" if pet["amyloid_status"] == "阳性" else "低"
            abnormal = pet["amyloid_status"] == "阳性"
            evidence = [
                f"全脑SUVR={pet['global_suvr']}",
                f"Centiloid={pet['centiloid']}",
                f"MRI海马萎缩={mri['hippocampal_atrophy']}",
            ]

        default_output = {
            "风险信号": risk_signal,
            "证据": evidence,
            "异常": abnormal,
        }

        return self.llm_reason(
            system_prompt=(
                "你是阿尔茨海默病影像分析 Agent。"
                "请优先根据 DiaMond 模型预测结果，再结合 PET 和 MRI 结果给出简洁、结构化的中文判断。"
                "请使用中文键名：风险信号、证据、异常。"
            ),
            user_payload=(
                f"DiaMond 预测结果: {diamond}\n"
                f"PET 结果: {pet}\n"
                f"MRI 结果: {mri}\n"
                "请输出 JSON，键名使用：风险信号、证据、异常。"
            ),
            default_output=default_output,
        )
