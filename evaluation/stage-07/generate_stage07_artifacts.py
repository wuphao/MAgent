import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, 'src')
from multi_agent.capabilities.text_validation import TextEvidenceValidator, TextObservationExtractor
from multi_agent.ingestion.manifest import InputManifest
from multi_agent.ingestion.parsers.text import TextParser
from multi_agent.knowledge import ExactRetriever, KnowledgeDocumentLoader, KnowledgeIndex, RuleCandidateBuilder
from multi_agent.capabilities.imaging import DiamondAdapter, DiaMondCompatibilityValidator, ImagingInspector
from multi_agent.domain.requests import AnalysisRequest
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.plan_validator import PlanValidator
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.assets import AssetRepository
from multi_agent.storage.sqlite import SQLiteStore

base = Path('evaluation/stage-07')
base.mkdir(parents=True, exist_ok=True)
parser = TextParser(AssetRepository(SQLiteStore(base / 'text-assets.sqlite3'), base / 'assets'))
doc = parser.parse(InputManifest(project_id='stage07_eval', path=Path('tests/fixtures/stage07/clinical_note.txt'), source_namespace='clinical-note'))
observations = TextObservationExtractor().extract(doc, 'stage07_eval', 'subject_s001')
(base / 'text_extraction.json').write_text(json.dumps({
    'document': doc.model_dump(mode='json'),
    'observations': [item.model_dump(mode='json') for item in observations],
    'span_validation': [TextEvidenceValidator().validate_span(doc, span.locator, span.text) for span in doc.spans],
}, ensure_ascii=False, indent=2), encoding='utf-8')
knowledge_doc = KnowledgeDocumentLoader().load_markdown(Path('configs/knowledge/xx-v1-data-dictionary.md'), 'xx_v1_dictionary', '2026-09-07')
hits = ExactRetriever(KnowledgeIndex.from_documents([knowledge_doc])).search('xx-v1 total scoring definition')
candidates = RuleCandidateBuilder().from_hits('xx-v1 total scoring definition', hits)
(base / 'knowledge_retrieval.json').write_text(json.dumps({
    'document': knowledge_doc.model_dump(mode='json'),
    'hits': [hit.model_dump(mode='json') for hit in hits],
    'rule_candidates': [candidate.model_dump(mode='json') for candidate in candidates],
    'activation': {'status': 'candidate_only', 'reason': 'rules must be activated through instrument registry before changing scoring behavior'},
}, ensure_ascii=False, indent=2), encoding='utf-8')
missing = DiamondAdapter().validate_only(base / 'missing_mri.nii.gz', None, checkpoint_hash=None)
probe_mri = base / 'probe_mri.nii'
probe_pet = base / 'probe_pet.nii'
probe_mri.write_bytes(b'mri-v1')
probe_pet.write_bytes(b'pet-v1')
inspector = ImagingInspector()
compatible = DiaMondCompatibilityValidator().validate(
    inspector.inspect(probe_mri, 'MRI', sequence_identity='T1'),
    inspector.inspect(probe_pet, 'PET', tracer='FDG'),
    checkpoint_hash='checkpoint-demo-hash',
)
probe_mri.write_bytes(b'mri-v2')
changed = DiaMondCompatibilityValidator().validate(
    inspector.inspect(probe_mri, 'MRI', sequence_identity='T1'),
    inspector.inspect(probe_pet, 'PET', tracer='FDG'),
    checkpoint_hash='checkpoint-demo-hash',
)
(base / 'imaging_contract.json').write_text(json.dumps({
    'missing_or_unverified': missing,
    'compatible_probe': compatible.model_dump(mode='json'),
    'after_content_change': changed.model_dump(mode='json'),
    'cache_changed': compatible.cache_key != changed.cache_key,
    'real_runtime': 'not verified: requires real MRI/PET, model weights/checkpoint hash, runtime environment and resource log',
}, ensure_ascii=False, indent=2), encoding='utf-8')
capabilities = CapabilityRegistry.from_directory(Path('configs/capabilities'))
request = AnalysisRequest(project_id='stage07_eval', goal='multimodal_summary', as_of=datetime.now(timezone.utc))
plan = TemplatePlanner().plan(request, {spec.capability_id for spec in capabilities.available_for_production()}, {'xx_v1.total'})
(base / 'multimodal_plan.json').write_text(json.dumps({
    'request': request.model_dump(mode='json'),
    'plan': plan.model_dump(mode='json'),
    'validation': PlanValidator(capabilities).validate(request, plan).model_dump(mode='json'),
}, ensure_ascii=False, indent=2), encoding='utf-8')
