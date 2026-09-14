import urllib.request, json, concurrent.futures
from pathlib import Path
dois=['10.1038/s41591-024-03118-z','10.1038/s41591-022-01932-x','10.1038/s41591-023-02440-2','10.1038/s41746-025-02026-x','10.1038/s41746-026-02665-8','10.1038/s41586-023-06291-2','10.1371/journal.pdig.0000757','10.1038/s41531-025-00939-8','10.1038/s41746-025-02324-4','10.64898/2026.03.17.26348154','10.1016/j.inpsyc.2026.100221','10.1038/s41591-024-03196-z','10.1038/s41591-024-03097-1']
def fetch(doi):
 try:
  req=urllib.request.Request('https://api.crossref.org/works/'+doi,headers={'User-Agent':'AcademicReferenceVerification/1.0'})
  m=json.load(urllib.request.urlopen(req,timeout=40))['message']
  return {k:m.get(k) for k in ['DOI','title','author','container-title','volume','issue','page','article-number','published','published-online','type']}
 except Exception as e:return {'DOI':doi,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(fetch,dois))
Path(__file__).with_name('metadata.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for r in results: print(json.dumps(r,ensure_ascii=False))
