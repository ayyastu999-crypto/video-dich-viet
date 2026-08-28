const $ = s => document.querySelector(s);

const FILE_META = {
  final_video:      ['🎬', 'Video hoàn chỉnh'],
  translated_srt:   ['📝', 'Phụ đề tiếng Việt'],
  original_srt:     ['🈶', 'Phụ đề gốc'],
  script_plain:     ['📄', 'Kịch bản tiếng Việt'],
  script_bilingual: ['📑', 'Kịch bản song ngữ'],
  tts_audio:        ['🎙️', 'Giọng đọc'],
};

const fmtSize = b => b > 1073741824 ? (b / 1073741824).toFixed(1) + ' GB'
                   : b > 1048576   ? (b / 1048576).toFixed(0) + ' MB'
                   : Math.max(1, Math.round(b / 1024)) + ' KB';

const fmtDur = s => !s ? null
  : Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0');

function fmtDate(iso){
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const p = n => String(n).padStart(2, '0');
  return p(d.getDate()) + '/' + p(d.getMonth() + 1) + '/' + d.getFullYear()
       + ' · ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

const fileUrl = (p, inline) =>
  '/api/file?' + (inline ? 'inline=1&' : '') + 'path=' + encodeURIComponent(p);

function renderStats(projects){
  const totalSec  = projects.reduce((a, p) => a + (p.duration || 0), 0);
  const totalSize = projects.reduce((a, p) => a + (p.size || 0), 0);
  const stats = [
    [String(projects.length), 'video đã dịch'],
    [totalSec  ? Math.round(totalSec / 60) + ' phút' : '—', 'tổng thời lượng'],
    [totalSize ? fmtSize(totalSize) : '—', 'dung lượng'],
  ];
  const box = $('#stats');
  box.innerHTML = '';
  stats.forEach(([val, label]) => {
    const d = document.createElement('div');
    d.className = 'stat';
    d.innerHTML = '<b></b><span></span>';
    d.querySelector('b').textContent = val;
    d.querySelector('span').textContent = label;
    box.appendChild(d);
  });
}

function renderProject(p){
  const el = document.createElement('div');
  el.className = 'proj';

  const bits = [fmtDate(p.finished_at), fmtDur(p.duration),
                p.cues ? p.cues + ' câu' : null,
                p.size ? fmtSize(p.size) : null].filter(Boolean);

  el.innerHTML =
    '<div class="proj-head">' +
      '<div class="thumb">🎞️</div>' +
      '<div class="proj-meta"><div class="proj-title"></div>' +
        '<div class="proj-sub"></div></div>' +
      '<span class="chev">▸</span>' +
    '</div>' +
    '<div class="proj-body"><div class="slot"></div>' +
      '<div class="files"></div><div class="path"></div></div>';

  el.querySelector('.proj-title').textContent = p.title || p.id;
  el.querySelector('.path').textContent = p.dir || '';

  const sub = el.querySelector('.proj-sub');
  bits.forEach((b, i) => {
    if (i) { const s = document.createElement('i'); s.textContent = '·'; sub.appendChild(s); }
    const s = document.createElement('span'); s.textContent = b; sub.appendChild(s);
  });
  const grid = el.querySelector('.files');
  Object.entries(p.files || {}).forEach(([key, path]) => {
    const m = FILE_META[key];
    if (!m) return;
    const a = document.createElement('a');
    a.className = 'file';
    a.href = fileUrl(path, false);
    a.setAttribute('download', '');
    a.innerHTML = '<span></span><b></b>';
    a.children[0].textContent = m[0];
    a.children[1].textContent = m[1];
    grid.appendChild(a);
  });

  // Chi nap video khi mo the ra, tranh tai het moi video cung luc
  el.querySelector('.proj-head').onclick = () => {
    const opening = !el.classList.contains('open');
    el.classList.toggle('open', opening);
    const slot = el.querySelector('.slot');
    if (opening && p.files && p.files.final_video && !slot.firstChild) {
      const v = document.createElement('video');
      v.controls = true;
      v.preload = 'metadata';
      v.playsInline = true;
      v.src = fileUrl(p.files.final_video, true);
      slot.appendChild(v);
    }
  };

  return el;
}

async function load(){
  const list = $('#list');
  try {
    const j = await (await fetch('/api/history')).json();
    const projects = j.projects || [];
    renderStats(projects);

    if (!projects.length) {
      list.innerHTML = '<div class="empty"><div>📼</div>' +
        '<h3>Chưa có video nào</h3>' +
        '<p>Dịch xong video đầu tiên, nó sẽ hiện ở đây kèm toàn bộ file kết quả.</p>' +
        '<a href="/">Dịch video đầu tiên</a></div>';
      return;
    }
    list.innerHTML = '';
    projects.forEach(p => list.appendChild(renderProject(p)));
  } catch (e) {
    list.innerHTML = '<div class="empty"><div>⚠️</div>' +
      '<h3>Không đọc được lịch sử</h3><p></p></div>';
    list.querySelector('p').textContent = e.message;
  }
}

load();
