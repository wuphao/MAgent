import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const [pptxPath, outDir] = process.argv.slice(2);
await fs.mkdir(outDir, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(pptxPath));
const records = [];
for (const [i, slide] of deck.slides.items.entries()) {
  const n = String(i + 1).padStart(2, '0');
  const png = await deck.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(path.join(outDir, `slide-${n}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(path.join(outDir, `slide-${n}.layout.json`), await layout.text());
  const inspected = await deck.inspect({ target: slide, kind: 'slide,textbox,shape,image,table,chart,layout', maxChars: 30000 });
  records.push({ slide: i + 1, ndjson: inspected.ndjson });
}
await fs.writeFile(path.join(outDir, 'template-inspect.ndjson'), records.map(x => JSON.stringify(x)).join('\n'));
const montage = await deck.export({ format: 'webp', montage: true, scale: 1 });
await fs.writeFile(path.join(outDir, 'montage.webp'), new Uint8Array(await montage.arrayBuffer()));
console.log(JSON.stringify({ slides: deck.slides.items.length, outDir }));
