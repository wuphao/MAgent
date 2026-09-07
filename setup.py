from setuptools import find_packages, setup


setup(
    name="multi-agent-rwe",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=["openpyxl>=3.1,<4", "pydantic>=2.11,<3"],
)
