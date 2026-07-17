class BiomarkerTool:
    def run(self, biomarkers):
        abeta = biomarkers["abeta42"]
        ptau = biomarkers["p_tau"]

        return {
            "abeta_status": "偏低" if abeta < 500 else "正常",
            "ptau_status": "升高" if ptau > 60 else "正常",
            "abeta42": abeta,
            "p_tau": ptau,
        }
