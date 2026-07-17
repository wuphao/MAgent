class FollowUpTool:
    def run(self, followup):
        delta = followup["baseline_mmse"] - followup["current_mmse"]

        if delta >= 2:
            trend = "下降"
        elif delta == 1:
            trend = "轻度下降"
        else:
            trend = "稳定"

        return {
            "delta_mmse": delta,
            "trend": trend,
        }
