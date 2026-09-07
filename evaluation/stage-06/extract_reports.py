import json
from pathlib import Path
run_path = Path('evaluation/stage-06/run_with_review.json')
doc = json.loads(run_path.read_text(encoding='utf-8'))
synthesis = next(task for task in doc['tasks'] if task['spec']['task_id'] == 'synthesis_report')
output = synthesis['result']['output']
base = Path('evaluation/stage-06')
(base / 'report_snapshot.json').write_text(json.dumps(output['report_snapshot'], ensure_ascii=False, indent=2), encoding='utf-8')
(base / 'report.json').write_text(output['report_json'], encoding='utf-8')
(base / 'report.md').write_text(output['report_markdown'], encoding='utf-8')
(base / 'report.txt').write_text(output['report_text'], encoding='utf-8')
(base / 'challenge_trace.json').write_text(json.dumps({
    'challenges': output['report_snapshot']['challenges'],
    'review_outcomes': output['report_snapshot']['review_outcomes'],
    'withdrawn_finding_ids': output['report_snapshot']['withdrawn_finding_ids'],
}, ensure_ascii=False, indent=2), encoding='utf-8')
