import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const [source, out, qaDir] = process.argv.slice(2);
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
const BLUE = '#0B5D9B', DARK = '#163A5F', MID = '#2D7DB8', PALE = '#EAF4FB';
const TEXT = '#263746', MUTED = '#5F7283', LINE = '#BFD6E6', WHITE = '#FFFFFF';
const FONT = 'Microsoft YaHei';

function addText(slide, text, x, y, w, h, size=20, color=TEXT, bold=false, align='left') {
  const s = slide.shapes.add({geometry:'textbox', position:{left:x,top:y,width:w,height:h}, fill:'none', line:{style:'solid',fill:'none',width:0}});
  s.text = text; s.text.style = {fontFamily:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle'};
  return s;
}
function title(slide, text, sub='') {
  addText(slide,text,54,82,900,48,30,DARK,true);
  slide.shapes.add({geometry:'rect',position:{left:54,top:133,width:82,height:4},fill:MID,line:{style:'solid',fill:'none',width:0}});
  if(sub) addText(slide,sub,154,111,1010,28,15,MUTED,false);
}
function card(slide, x,y,w,h, heading, body, accent=MID) {
  slide.shapes.add({geometry:'roundRect',position:{left:x,top:y,width:w,height:h},fill:WHITE,line:{style:'solid',fill:LINE,width:1},borderRadius:'rounded-lg',shadow:'shadow-sm'});
  slide.shapes.add({geometry:'rect',position:{left:x,top:y,width:7,height:h},fill:accent,line:{style:'solid',fill:'none',width:0}});
  addText(slide,heading,x+22,y+14,w-38,32,21,DARK,true);
  addText(slide,body,x+22,y+50,w-38,h-62,17,TEXT,false);
}
function pill(slide,text,x,y,w,color=MID){
  const p=slide.shapes.add({geometry:'roundRect',position:{left:x,top:y,width:w,height:34},fill:color,line:{style:'solid',fill:'none',width:0},borderRadius:'rounded-xl'});
  p.text=text;p.text.style={fontFamily:FONT,fontSize:16,color:WHITE,bold:true,alignment:'center',verticalAlignment:'middle'};
}
function clearContent(slide) {
  for (const s of [...slide.shapes.items]) {
    const r=s.position; const keep=(r.top<78 && r.width>1000);
    if(!keep) s.delete();
  }
  for (const im of [...slide.images.items]) {
    const r=im.position; const keep=((r.top<75)&&((r.width>1000)||(r.left<300)))||(r.top>640);
    if(!keep) im.delete();
  }
  for (const t of [...slide.tables.items]) t.delete();
  for (const c of [...slide.charts.items]) c.delete();
}

// Slide 1 — retain the supplied cover and correct the task wording.
for (const s of deck.slides.items[0].shapes.items) {
  if (s.text?.toString?.().includes('辅助诊疗系统')) s.text.replace('辅助诊疗系统','辅助诊断系统');
  if (s.position.width >= 1200 && s.position.height >= 700) s.position={left:0,top:0,width:1280,height:720};
}
for (const im of deck.slides.items[0].images.items) if (im.position.top < 0) im.position = {...im.position, top:0};

// Slide 2 — background.
{
  const s=deck.slides.items[1]; title(s,'神经退行性疾病诊断依赖多源证据','研究背景');
  card(s,60,170,350,190,'疾病特点','起病隐匿、进展缓慢、个体差异显著，AD病理改变往往早于临床症状。');
  card(s,465,170,350,190,'诊断依据','MRI/PET影像、认知量表、病史、人口学信息及纵向随访需要共同参与判断。','#4A90A4');
  card(s,870,170,350,190,'临床现实','模态可能缺失、采集时间不同，影像与认知证据还可能相互矛盾。','#E28B44');
  addText(s,'核心问题',60,410,180,42,24,BLUE,true);
  addText(s,'如何将分散的专业证据组织为可解释、可追溯、可降级运行的辅助诊断流程？',240,405,930,58,26,DARK,true);
  addText(s,'研究对象聚焦：阿尔茨海默病（AD）与轻度认知障碍（MCI）',60,520,1090,45,20,MUTED,false,'center');
}

// Slide 3 — multimodal research status.
{
  const s=deck.slides.items[2]; title(s,'影像模型已具备分类能力，但尚未覆盖完整临床决策','研究现状（一）：多模态深度学习');
  card(s,60,165,350,240,'影像深度学习','3D CNN、GCN与Transformer已用于CN、MCI、AD等分类，并逐步从单模态走向MRI/PET联合建模。');
  card(s,465,165,350,240,'DiaMond','采用多模态视觉Transformer与跨模态注意力处理三维T1 MRI和FDG-PET，可作为本研究的影像分析工具。','#4A90A4');
  card(s,870,165,350,240,'主要不足','最终结果往往被压缩为分类概率；临床量表利用不足；难解释模态冲突、缺失信息与结论依据。','#E28B44');
  addText(s,'本研究保留DiaMond的影像分析能力，研究重点放在“影像结果之后如何协作”。',80,465,1120,54,25,DARK,true,'center');
  addText(s,'代表研究：Liu et al., 2018；Qiu et al., 2022；DiaMond；MultimodalAD；UniCross',70,595,1140,28,13,MUTED,false);
}

// Slide 4 — agent research status.
{
  const s=deck.slides.items[3]; title(s,'医学多智能体证明了协作可行，但任务和数据仍不统一','研究现状（二）：医学多智能体');
  const xs=[55,350,645,940]; const hs=['MedAgents','MAM','CARE-AD','ADAgent'];
  const bs=[
    '多专家讨论医学问题\n优势：角色化推理\n局限：以医学问答为主',
    '模块化多模态诊断\n优势：角色分工与投票\n局限：非AD专用',
    '从纵向临床笔记预测AD风险\n优势：时间轨迹\n局限：影像证据较弱',
    'LLM规划并调用MRI/PET/临床工具\n优势：工具化\n局限：RWE病例状态不足'
  ];
  for(let i=0;i<4;i++) card(s,xs[i],170,260,280,hs[i],bs[i],i===3?'#E28B44':MID);
  addText(s,'这些工作用于架构定位，不直接比较论文准确率',85,495,1110,43,25,DARK,true,'center');
  addText(s,'原因：数据集、任务定义、标签和输出形式不同；跨论文性能数字不构成公平实验。',100,545,1080,38,18,MUTED,false,'center');
  addText(s,'参考：MedAgents (ACL 2024)；MAM (ACL 2025)；CARE-AD (npj Digital Medicine, 2025)；ADAgent',70,610,1140,24,13,MUTED,false);
}

// Slide 5 — gaps and question.
{
  const s=deck.slides.items[4]; title(s,'现有方法的缺口集中在证据组织，而非再训练一个更大的模型','问题提出');
  const ys=[160,262,364,466];
  const nums=['01','02','03','04'];
  const hs=['数据表示不统一','专业模型彼此割裂','冲突与缺失处理薄弱','结论缺少可追溯依据'];
  const bs=['影像、表单和随访记录缺少病例级统一表示。','影像模型、临床规则与LLM之间缺少标准化接口。','简单加权或投票难以说明信息为什么不一致。','医生难以核查具体证据、不确定性和知识来源。'];
  for(let i=0;i<4;i++){
    addText(s,nums[i],65,ys[i],62,52,28,MID,true,'center');
    addText(s,hs[i],145,ys[i],280,42,21,DARK,true);
    addText(s,bs[i],430,ys[i],750,42,18,TEXT,false);
    if(i<3)s.shapes.add({geometry:'rect',position:{left:145,top:ys[i]+67,width:1020,height:1},fill:LINE,line:{style:'solid',fill:'none',width:0}});
  }
  addText(s,'研究问题：在相同病例和相同DiaMond输出下，协作机制能否提升证据完整性、冲突识别与解释质量？',70,575,1140,50,22,DARK,true,'center');
}

// Slide 6 — goals.
{
  const s=deck.slides.items[5]; title(s,'研究目标聚焦于一个可验证的最小闭环','研究目标与内容');
  card(s,70,175,345,290,'目标一｜统一病例状态','将RWE数据、表单、DiaMond结果和后续随访映射为统一JSON，形成共享Case Memory。');
  card(s,468,175,345,290,'目标二｜专家智能体协作','构建影像、临床、认知和融合决策四个核心智能体，约束各自输入、工具和输出。','#4A90A4');
  card(s,866,175,345,290,'目标三｜可信输出与验证','输出结论、证据、冲突、不确定性和建议，并通过统一基线与消融实验验证。','#E28B44');
  pill(s,'第一阶段：完成AD/MCI辅助诊断闭环',230,520,390,BLUE);
  pill(s,'后续扩展：纵向随访与知识检索',660,520,390,'#4A90A4');
}

// Slide 7 — architecture.
{
  const s=deck.slides.items[6]; title(s,'共享病例状态把专业模型组织成可审计的协作流程','系统总体架构');
  const node=(x,y,w,h,txt,fill=WHITE,stroke=LINE)=>{const z=s.shapes.add({geometry:'roundRect',position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:stroke,width:1.5},borderRadius:'rounded-lg'});z.text=txt;z.text.style={fontFamily:FONT,fontSize:17,color:DARK,bold:true,alignment:'center',verticalAlignment:'middle'};return z;};
  // connectors first
  const arrows=[[230,225,345,225],[458,280,458,320],[570,225,640,225],[640,185,640,455],[640,185,690,185],[640,275,690,275],[640,365,690,365],[640,455,690,455],[910,185,960,185],[910,275,960,275],[910,365,960,365],[910,455,960,455],[960,185,960,455],[960,292,1030,292]];
  for(const [x1,y1,x2,y2] of arrows)s.shapes.add({geometry:'line',position:{left:x1,top:y1,width:x2-x1,height:y2-y1},line:{style:'solid',fill:MID,width:2}});
  node(55,185,175,80,'RWE病例数据\n临床表单',PALE,MID);
  node(345,170,225,110,'统一病例JSON\nCase Memory',PALE,BLUE);
  node(345,320,225,80,'状态更新与调度',WHITE,MID);
  node(690,150,220,70,'影像智能体\n调用DiaMond');
  node(690,240,220,70,'临床智能体');
  node(690,330,220,70,'认知智能体');
  node(690,420,220,70,'知识检索｜后续扩展',WHITE,'#8FB6C7');
  node(1030,240,190,105,'融合决策智能体\n一致性与冲突检测',PALE,BLUE);
  addText(s,'输出：辅助判断｜关键证据｜不确定性｜冲突说明｜补充建议',210,555,860,48,21,DARK,true,'center');
}

// Slide 8 — fair comparisons. Replace the inherited unrelated diagram but keep template chrome.
{
  const s=deck.slides.items[7]; clearContent(s); title(s,'实验比较的是协作机制，而不是跨论文“硬比准确率”','对比实验设计');
  const xs=[45,350,655,960];
  const hs=['DiaMond only','单智能体','多智能体投票','本文方法'];
  const bs=['仅使用影像分类结果\n建立影像性能下限','一个LLM读取全部病例\n验证角色拆分价值','各专家独立判断后投票\n验证简单协作局限','Case Memory＋证据融合\n＋冲突仲裁'];
  for(let i=0;i<4;i++)card(s,xs[i],170,275,235,hs[i],bs[i],i===3?'#E28B44':MID);
  addText(s,'公平原则',65,450,150,36,22,BLUE,true);
  addText(s,'同一批病例　｜　同一DiaMond输出　｜　同一标签与数据划分　｜　只改变智能体组织方式',210,445,980,46,20,DARK,true);
  addText(s,'评价维度',65,520,150,36,22,BLUE,true);
  addText(s,'分类性能　缺失模态鲁棒性　冲突识别　证据覆盖率　幻觉率　响应时间/调用次数',210,515,980,54,19,TEXT,false);
  addText(s,'补充：通过去掉Case Memory、冲突仲裁或某一专家智能体开展消融实验。',65,595,1120,28,16,MUTED,false,'center');
}

// Slide 9 — current progress.
{
  const s=deck.slides.items[8]; clearContent(s); title(s,'关键数据入口与影像模型已经跑通，下一步是闭环集成','当前进展与后续计划');
  const steps=[
    ['01','数据进入RWE','已完成'],['02','病例JSON获取','已完成'],['03','临床表单确定','已完成'],['04','DiaMond基本流程','已跑通'],['05','四类智能体接口','下一步'],['06','闭环与对比实验','后续']
  ];
  for(let i=0;i<6;i++){
    const x=55+i*202;
    if(i<5)s.shapes.add({geometry:'line',position:{left:x+145,top:260,width:57,height:0},line:{style:'solid',fill:LINE,width:2,endArrowType:'triangle'}});
    const done=i<4, fill=done?BLUE:WHITE, color=done?WHITE:DARK;
    const c=s.shapes.add({geometry:'ellipse',position:{left:x+45,top:205,width:92,height:92},fill,line:{style:'solid',fill:done?BLUE:LINE,width:2}});c.text=steps[i][0];c.text.style={fontFamily:FONT,fontSize:25,color,bold:true,alignment:'center',verticalAlignment:'middle'};
    addText(s,steps[i][1],x,320,180,48,17,DARK,true,'center');
    addText(s,steps[i][2],x,370,180,30,15,done?BLUE:MUTED,false,'center');
  }
  card(s,105,465,485,115,'近期交付','封装DiaMond接口；定义智能体输入输出Schema；实现共享病例状态与融合流程。',MID);
  card(s,690,465,485,115,'验证重点','统一数据上完成单智能体、投票型多智能体、本文方法及消融对比。','#E28B44');
}

// Slide 10 — close with the thesis, not a generic thank-you.
{
  const s=deck.slides.items[9];
  for (const sh of s.shapes.items) if (sh.position.width >= 1200 && sh.position.height >= 700) sh.position={left:0,top:0,width:1280,height:720};
  for (const im of s.images.items) if (im.position.top < 0) im.position = {...im.position, top:0};
  for (const sh of s.shapes.items) if(sh.text?.toString?.().trim()==='谢谢') {
    sh.text='不是让LLM直接“猜诊断”\n而是让专业模型协同并留下证据链';
    sh.position={left:52,top:354,width:780,height:120};
    sh.text.style={fontFamily:FONT,fontSize:34,color:WHITE,bold:true,alignment:'left',verticalAlignment:'middle'};
  }
  addText(s,'敬请各位老师批评指正',58,505,500,42,21,WHITE,false);
}

await fs.mkdir(qaDir,{recursive:true});
for(const [i,s] of deck.slides.items.entries()){
  const n=String(i+1).padStart(2,'0');
  const png=await deck.export({slide:s,format:'png',scale:1});
  await fs.writeFile(path.join(qaDir,`slide-${n}.png`),new Uint8Array(await png.arrayBuffer()));
  const layout=await s.export({format:'layout'}); await fs.writeFile(path.join(qaDir,`slide-${n}.layout.json`),await layout.text());
}
const montage=await deck.export({format:'webp',montage:true,scale:1});
await fs.writeFile(path.join(qaDir,'montage.webp'),new Uint8Array(await montage.arrayBuffer()));
const pptx=await PresentationFile.exportPptx(deck); await pptx.save(out);
console.log(JSON.stringify({out,slides:deck.slides.items.length,qaDir}));
