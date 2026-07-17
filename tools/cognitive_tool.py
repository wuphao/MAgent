class CognitiveTool:
    def run(self, scores):
        mmse = scores["MMSE"]

        if mmse >= 27:
            level = "正常"
        elif mmse >= 24:
            level = "轻度受损"
        else:
            level = "重度受损"

        return {
            "mmse": mmse,
            "level": level,
        }
