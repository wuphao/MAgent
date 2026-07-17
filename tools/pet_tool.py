class PETAmyloidTool:
    def run(self, pet_path):
        return {
            "global_suvr": 1.42,
            "centiloid": 72.5,
            "amyloid_status": "阳性",
            "probability": 0.91,
            "source": pet_path,
        }
