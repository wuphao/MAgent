import os,sys,runpy
from pathlib import Path
base=Path(__file__).resolve().parent
os.environ['PATH']=r'C:\Program Files\LibreOffice\program;C:\Users\wph\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin;'+os.environ['PATH']
sys.argv=['render_docx.py',str(base.parent/'神经退行性疾病人工智能辅助诊疗研究现状.docx'),'--output_dir',str(base/'render'),'--emit_pdf']
runpy.run_path(r'C:\Users\wph\.codex\plugins\cache\openai-primary-runtime\documents\26.909.12148\skills\documents\render_docx.py',run_name='__main__')
