class MRIAtrophyTool:
    def run(self, mri_path):
        return {
            "hippocampal_atrophy": "轻度",
            "score": 1,
            "source": mri_path,
        }
