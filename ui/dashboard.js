"use strict";
const $ = selector => document.querySelector(selector);
const stageDefinitions = [
  ['export', 'RWE 数据导出'], ['ingest', '字段标准化与证据登记'],
  ['rwe_quality', '数据质量检查'], ['rwe_assessment', '量表来源分数'],
  ['rwe_longitudinal', '随访变化分析'], ['rwe_laboratory', '实验室与遗传记录'],
  ['rwe_modalities', '文本与影像可用性'], ['synthesis_report', '质询复核与综合报告']
];
const names = Object.fromEntries(stageDefinitions);
const statusNames = {pending:'待执行', running:'进行中', succeeded:'已完成', failed:'失败',
  skipped:'已跳过', no_data:'无可用数据', insufficient_points:'时间点不足',
  not_comparable:'不可比较', capability_unavailable:'未运行', success:'已完成',
  completed:'已完成', completed_with_limitations:'附限制完成', needs_metadata:'待补充信息'};
let activeJob = null, analysis = null, evidenceRefs = null, page = 0;
let polling = false;
const pageSize = 20;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function error(message) { $('#error').textContent = message; $('#error').hidden = !message; }
async function api(path, options) {
  const response = await fetch(path, {...options, signal: AbortSignal.timeout(20000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
  return data;
}
function selectTab(tab) {
  document.querySelectorAll('.tab').forEach(item => {
    const selected = item === tab;
    item.classList.toggle('active', selected);
    item.setAttribute('aria-selected', selected);
    item.tabIndex = selected ? 0 : -1;
    $('#' + item.dataset.tab).hidden = !selected;
  });
}
const tabs = [...document.querySelectorAll('.tab')];
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', event => {
    const keys = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length, Home:0, End:tabs.length-1};
    if (Object.hasOwn(keys, event.key)) { event.preventDefault(); selectTab(tabs[keys[event.key]]); tabs[keys[event.key]].focus(); }
  });
});

function renderSteps(job = {}) {
  const tasks = Object.fromEntries((job.tasks || []).map(task => [task.spec.task_id, task]));
  const container = $('#steps'); container.replaceChildren();
  let completed = 0;
  stageDefinitions.forEach(([id, title], index) => {
    let state = 'pending', detail = '';
    if (id === 'export' || id === 'ingest') {
      const order = ['export', 'ingest', 'analysis', 'done'];
      const position = order.indexOf(job.stage);
      const target = order.indexOf(id);
      if (position > target) state = 'succeeded';
      else if (position === target) { state = job.status === 'failed' ? 'failed' : 'running'; detail = job.message || ''; }
    } else if (tasks[id]) {
      const task = tasks[id]; state = task.state;
      if (task.result && state === 'succeeded') state = task.result.status || state;
      detail = statusNames[state] || state;
    }
    const done = !['pending', 'ready', 'running', 'retry_wait'].includes(state);
    if (done) completed++;
    const limited = ['no_data','insufficient_points','not_comparable','capability_unavailable'].includes(state);
    const row = node('div', undefined, 'step' + (state === 'pending' ? ' pending' : '') + (state === 'running' ? ' running' : '') + (limited ? ' limited' : '') + (state === 'failed' ? ' failed' : ''));
    row.append(node('span', state === 'failed' ? '!' : limited ? '−' : done ? '✓' : String(index+1), 'step-icon'));
    const body = node('div'); body.append(node('strong', title), node('p', detail || (statusNames[state] || state)));
    row.append(body); container.append(row);
  });
  $('#progress').textContent = `${completed} / ${stageDefinitions.length}`;
  $('#process-status').textContent = statusNames[job.status] || (job.status === 'queued' ? '排队中' : '待开始');
  $('#stage-message').textContent = job.status === 'failed' ? '本次运行失败' : completed === 8 ? '流程结束' : '流程进度';
}

function renderFindings() {
  const host = $('#overview'); host.replaceChildren();
  const snapshot = analysis.report_snapshot;
  const taskNames = new Map();
  analysis.tasks.forEach(task => (task.result?.findings || []).forEach(f => taskNames.set(f.finding_id, names[task.spec.task_id])));
  if (!snapshot.findings.length) host.append(node('p', '未生成可发布的分析发现。'));
  snapshot.findings.forEach(f => {
    const row = node('div', undefined, 'finding'), body = node('div');
    body.append(node('h3', taskNames.get(f.finding_id) || '复核发现'), node('p', f.proposition));
    if (f.support_refs.length) {
      const button = node('button', `查看 ${f.support_refs.length} 条证据`);
      button.addEventListener('click', () => {
        evidenceRefs = new Set(f.support_refs.map(ref => ref.observation_id)); page = 0;
        $('#evidence-search').value = ''; renderEvidence(); selectTab($('#tab-evidence'));
      }); body.append(button);
    }
    row.append(body, node('span', f.status === 'unresolved' ? '待复核' : '来源支持', 'tag' + (f.status === 'unresolved' ? ' warn' : '')));
    host.append(row);
  });
}
function renderEvidence() {
  if (!analysis) return;
  const search = $('#evidence-search').value.toLowerCase().trim();
  const items = analysis.evidence.filter(e => (!evidenceRefs || evidenceRefs.has(e.observation_id)) &&
    [e.form,e.field,e.date,e.value].join(' ').toLowerCase().includes(search));
  page = Math.max(0, Math.min(page, Math.ceil(items.length/pageSize)-1));
  $('#evidence-count').textContent = `${evidenceRefs ? '关联证据' : '全部证据'} · ${items.length} 条`;
  const table = node('table'), head = node('thead'), tr = node('tr');
  ['表单 / 字段','日期','来源值','JSON 定位'].forEach(text => tr.append(node('th',text))); head.append(tr); table.append(head);
  const body = node('tbody');
  items.slice(page*pageSize,(page+1)*pageSize).forEach(e => {
    const row = node('tr'), field = node('td'); field.append(node('strong',e.form), node('div',e.field));
    row.append(field, node('td',e.date || '未填写'), node('td',e.value == null ? '缺失' : String(e.value)), node('td',e.source.value_locator,'source')); body.append(row);
  });
  table.append(body); $('#evidence-table').replaceChildren(table);
  if (!items.length) $('#evidence-table').append(node('p','没有匹配证据。'));
  $('#page-label').textContent = `${page+1} / ${Math.max(1,Math.ceil(items.length/pageSize))}`;
  $('#prev-page').disabled = page === 0;
  $('#next-page').disabled = (page+1)*pageSize >= items.length;
}

function renderLongitudinal() {
  const container = $('#longitudinal'); container.replaceChildren();
  if (!analysis.series.length) { container.append(node('p','没有可用的来源分数。')); return; }
  const select = node('select',undefined,'score-select'); select.setAttribute('aria-label','选择量表指标');
  analysis.series.forEach((series,index) => { const option = node('option',series.label); option.value = index; select.append(option); });
  const chart = node('div'); container.append(select,chart);
  function draw() {
    const series = analysis.series[Number(select.value)]; chart.replaceChildren();
    const points = series.points.filter(p => p.date);
    if (points.length) {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 640 210'); svg.setAttribute('class','chart'); svg.setAttribute('role','img'); svg.setAttribute('aria-label',series.label+'来源分数分布，下方有完整数据表');
      const values = points.map(p => p.value), min = Math.min(...values), max = Math.max(...values);
      const times = points.map(p => Date.parse(p.date)), first = Math.min(...times), last = Math.max(...times);
      for (let i=0;i<3;i++) {
        const line = document.createElementNS(ns,'line');
        for (const [key,val] of Object.entries({x1:42,x2:612,y1:30+i*65,y2:30+i*65,stroke:'#e3e9e3'})) line.setAttribute(key,val);
        svg.append(line);
      }
      points.forEach(p => {
        const circle = document.createElementNS(ns,'circle'); circle.setAttribute('cx',first === last ? 320 : 50+(Date.parse(p.date)-first)/(last-first)*550);
        circle.setAttribute('cy',min === max ? 95 : 160-(p.value-min)/(max-min)*130); circle.setAttribute('r','5'); circle.setAttribute('fill','#27745a');
        const title = document.createElementNS(ns,'title'); title.textContent = `${p.date}：${p.value}`; circle.append(title); svg.append(circle);
      });
      [points[0].date,points[points.length-1].date].forEach((date,index) => {
        const label = document.createElementNS(ns,'text'); label.setAttribute('x', index ? '610':'45'); label.setAttribute('y','195'); label.setAttribute('fill','#74827c'); label.setAttribute('font-size','12'); label.setAttribute('text-anchor',index ? 'end':'start'); label.textContent = date; svg.append(label);
      });
      chart.append(svg);
    }
    chart.append(node('p','来源分数；未校验量表版本，不作临床变化判定。','chart-caption'));
    const table = node('table'), header = node('tr'); ['访视日期','来源分数'].forEach(t => header.append(node('th',t))); table.append(header);
    series.points.forEach(p => { const row = node('tr'); row.append(node('td',p.date || '日期缺失'),node('td',String(p.value))); table.append(row); });
    chart.append(table);
  }
  select.addEventListener('change',draw); draw();
}

function renderReview() {
  const host = $('#review'); host.replaceChildren();
  const snapshot = analysis.report_snapshot;
  host.append(node('p',`${snapshot.challenges.length} 项质询 · ${snapshot.review_outcomes.length} 项复核 · ${snapshot.withdrawn_finding_ids.length} 项撤回`));
  snapshot.challenges.forEach(c => {
    const row = node('div',undefined,'finding'); const body = node('div');
    body.append(node('h3','质询'),node('p',c.question));
    const outcome = snapshot.review_outcomes.find(o => o.challenge_id === c.challenge_id);
    body.append(node('p',outcome ? outcome.rationale : '尚未完成复核')); row.append(body); host.append(row);
  });
  const list = node('ul',undefined,'limited-list'); snapshot.limitations.forEach(text => list.append(node('li',text))); host.append(list);
}
function renderReport(value) {
  analysis = value; const report = analysis.report_snapshot;
  $('#report').hidden = false; $('#empty').hidden = true; $('#loading').hidden = true;
  $('#record-count').textContent = analysis.record_count;
  $('#observation-count').textContent = analysis.observation_count;
  $('#finding-count').textContent = report.findings.length;
  $('#report-status').textContent = statusNames[report.status] || report.status;
  $('#summary-title').textContent = report.status === 'failed' ? '报告未通过发布检查' : `已汇总 ${analysis.record_count} 条记录，形成 ${report.findings.length} 项发现`;
  $('#summary-text').textContent = analysis.forms.filter(f => f.count).map(f => `${f.name} ${f.count} 条`).join(' · ');
  $('#source-info').textContent = '导出于 ' + (analysis.exported_at ? new Date(analysis.exported_at).toLocaleString('zh-CN',{hour12:false}) : '未知时间');
  $('#footer-info').textContent = `报告 ${report.report_id}`;
  $('#export').disabled = false; $('#source-download').disabled = false;
  page = 0; evidenceRefs = null; $('#evidence-search').value = '';
  renderFindings(); renderEvidence(); renderLongitudinal(); renderReview();
}

async function poll(jobId) {
  if (polling) return;
  polling = true;
  let failures = 0;
  try {
    while (activeJob === jobId) {
      let job;
      try { job = await api('/api/runs/'+jobId); failures = 0; }
      catch (err) { if (++failures >= 3) throw err; await new Promise(r => setTimeout(r,1000)); continue; }
      renderSteps(job); $('#current-patient').textContent = job.patient_number;
      $('#loading-label').textContent = job.message;
      if (!['queued','running'].includes(job.status)) {
        if (job.analysis) renderReport(job.analysis);
        else { $('#loading').hidden = true; $('#empty').hidden = false; }
        if (job.status === 'failed') error(job.message);
        break;
      }
      $('#loading').hidden = false; $('#empty').hidden = true;
      await new Promise(r => setTimeout(r,650));
    }
  } catch (err) {
    error('连接中断：'+err.message+'。刷新页面可重新连接本次任务。'); $('#loading').hidden = true;
  } finally { polling = false; $('#start').disabled = false; $('#patient-id').disabled = false; }
}
$('#search').addEventListener('submit', async event => {
  event.preventDefault(); error(''); $('#start').disabled = true; $('#patient-id').disabled = true;
  $('#export').disabled = true; $('#source-download').disabled = true; $('#report').hidden = true; analysis = null;
  try {
    const patient = $('#patient-id').value.trim();
    const job = await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient_number:patient})});
    activeJob = job.job_id; localStorage.setItem('rwe-last-job',activeJob); renderSteps(job); await poll(activeJob);
  } catch (err) { error(err.message); $('#start').disabled = false; $('#patient-id').disabled = false; }
});
$('#export').addEventListener('click',() => { if (activeJob) window.location.href = '/api/runs/'+activeJob+'/report'; });
$('#source-download').addEventListener('click',() => { if (activeJob) window.location.href = '/api/runs/'+activeJob+'/source'; });
$('#evidence-search').addEventListener('input',() => { page=0; renderEvidence(); });
$('#clear-evidence').addEventListener('click',() => { evidenceRefs=null; page=0; $('#evidence-search').value=''; renderEvidence(); });
$('#prev-page').addEventListener('click',() => { page--; renderEvidence(); });
$('#next-page').addEventListener('click',() => { page++; renderEvidence(); });
renderSteps();
(async () => {
  try {
    await api('/api/health'); $('#connection').textContent = '本地运行';
    const jobId = localStorage.getItem('rwe-last-job');
    if (jobId && /^[a-f0-9]{32}$/.test(jobId)) {
      activeJob = jobId; $('#start').disabled=true; $('#patient-id').disabled=true; await poll(jobId);
      if (analysis) $('#patient-id').value = analysis.patient.patient_number;
    }
  } catch (err) { $('#connection').textContent='未连接'; error('请先运行 python run_dashboard.py，再打开本地页面。'); }
})();
