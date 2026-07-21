import { Presentation } from '@oai/artifact-tool';
const p = Presentation.create({slideSize:{width:1280,height:720}});
const s=p.slides.add(); const sh=s.shapes.add({geometry:'rect',position:{left:0,top:0,width:10,height:10}});
console.log('slides',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)));
console.log('shapes',Object.getOwnPropertyNames(Object.getPrototypeOf(s.shapes)));
console.log('shape',Object.getOwnPropertyNames(Object.getPrototypeOf(sh)));
