// ---- Ket noi backend that ----
let ENGINES = {};

function setChipState(group, val, ready, label, cls){
  const c = document.querySelector('.chips[data-group=' + group + '] .chip[data-v=' + val + ']');
  if (!c) return;
  const tag = c.querySelector('.tag');
  tag.className = 'tag ' + (ready ? (cls || 'free') : 'off');
  tag.textContent = label;
}

function selectChip(group, val){
  const g = document.querySelector('.chips[data-group=' + group + ']');
  const c = g && g.querySelector('.chip[data-v=' + val + ']');
  if (!c || c.querySelector('.tag.off')) return;
  g.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
  c.classList.add('on');
}

// Hoi backend xem engine nao dung duoc, khoa nhung cai chua san sang
(async () => {
  try {
    const j = await (await fetch('/api/health')).json();
    ENGINES = j.engines || {};
    setChipState('asr', 'whisper', ENGINES.whisper_gpu,
                 ENGINES.whisper_gpu ? 'GPU · MIỄN PHÍ' : 'KHÔNG CÓ GPU', 'gpu');
    setChipState('asr', 'gemini', ENGINES.gemini,
                 ENGINES.gemini ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    setChipState('mt', 'gemini', ENGINES.gemini,
                 ENGINES.gemini ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    setChipState('mt', 'deepseek', ENGINES.deepseek,
                 ENGINES.deepseek ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    // Whisper chay GPU vua nhanh vua khong ton tien -> uu tien chon san
    if (ENGINES.whisper_gpu) selectChip('asr', 'whisper');
    calcCost();
  } catch (e) {
    console.warn('Khong ket noi duoc backend:', e);
  }
})();

const RESULT_LABEL = {
  final_video:       ['🎬', 'Video hoàn chỉnh', true],
  translated_srt:    ['📝', 'Phụ đề tiếng Việt (.srt)', false],
  script_plain:      ['📄', 'Kịch bản tiếng Việt (.txt)', true],
  script_bilingual:  ['📑', 'Kịch bản song ngữ (.txt)', false],
};

function baseName(p){ return String(p).split('/').pop().split(BS).pop(); }

function showResults(result){
  const grid = $('#outs');
  grid.innerHTML = '';
  Object.entries(result || {}).forEach(([k, p]) => {
    const m = RESULT_LABEL[k];
    if (!m) return;
    const d = document.createElement('div');
    d.className = 'out' + (m[2] ? ' star' : '');
    d.innerHTML = '<div class="out-ico">' + m[0] + '</div>' +
      '<div class="out-meta"><div class="out-name"></div>' +
      '<div class="out-size">' + m[1] + '</div></div>' +
      '<a class="out-btn" download>Tải</a>';
    d.querySelector('.out-name').textContent = baseName(p);
    d.querySelector('a').href = '/api/file?path=' + encodeURIComponent(p);
    grid.appendChild(d);
  });
  if (result && result.translated_srt) loadSubPreview(result.translated_srt);
  showPlayer(result && result.final_video);
}

// Phat video ket qua ngay tren trang. inline=1 de server khong dat
// Content-Disposition attachment; Starlette ho tro Range nen tua duoc.
function showPlayer(videoPath){
  const box = $('#player'), vid = $('#vid');
  if (!videoPath) { box.classList.remove('show'); vid.removeAttribute('src'); return; }
  const url = '/api/file?inline=1&path=' + encodeURIComponent(videoPath);
  vid.src = url;
  $('#vid-name').textContent = baseName(videoPath);
  $('#vid-dl').href = '/api/file?path=' + encodeURIComponent(videoPath);
  box.classList.add('show');
}

$('#vid-full').onclick = () => {
  const v = $('#vid');
  if (v.requestFullscreen) v.requestFullscreen();
  else if (v.webkitEnterFullscreen) v.webkitEnterFullscreen();   // Safari/iOS
};

// Doc file SRT vua tao, do vao bang xem truoc
async function loadSubPreview(srtPath){
  const body = $('#subprev');
  body.innerHTML = '';
  try {
    const txt = await (await fetch('/api/file?path=' + encodeURIComponent(srtPath))).text();
    const cues = txt.split(/\r?\n\r?\n/).map(b => {
      const lines = b.trim().split(/\r?\n/);
      if (lines.length < 3) return null;
      return { ts: (lines[1].split(' --> ')[0] || '').slice(0, 8),
               text: lines.slice(2).join(' ') };
    }).filter(Boolean);
    $('#cue-count').textContent = cues.length + ' CÂU';
    cues.slice(0, 60).forEach(c => {
      const d = document.createElement('div');
      d.className = 'srow';
      d.style.gridTemplateColumns = '74px 1fr';
      d.innerHTML = '<div class="tc"></div><div></div>';
      d.children[0].textContent = c.ts;
      d.children[1].textContent = c.text;
      body.appendChild(d);
    });
  } catch (e) {
    body.innerHTML = '<div class="srow"><div></div><div>Không đọc được phụ đề</div></div>';
  }
}

function failRun(msg){
  logLine(msg, 'err');
  clearInterval(timer);
  state.running = false;
  $('#go').disabled = false;
}

// Bo tien to "[19:30:47] [Transcriber] " cho log de doc
function handleLog(line){
  const clean = line.replace(/^\[[\d:\- ]+\]\s*/, '').replace(/^\[\w+\]\s*/, '');
  const cls = /loi|error|fail|warn|⚠/i.test(line) ? 'warn' : '';
  logLine(clean || line, cls);
}

function finishRun(d){
  clearInterval(timer);
  $$('.step').forEach((s, i) => setStep(i, 'done'));
  $('#barfill').style.width = '100%';
  showResults(d.result);
  $('#panel-done').classList.add('show');
  $('#panel-done').scrollIntoView({ behavior: 'smooth', block: 'center' });
  state.running = false;
  $('#go').disabled = false;
}

$('#go').onclick = async () => {
  if (state.running) return;
  state.running = true;
  $('#go').disabled = true;
  $('#panel-run').classList.add('show');
  $('#panel-done').classList.remove('show');
    showPlayer(null);
  $('#log').innerHTML = '';
  $$('.step').forEach((s, i) => setStep(i, ''));
  $('#barfill').style.width = '0';
  $('#panel-run').scrollIntoView({ behavior: 'smooth', block: 'center' });
  startTimer();

  try {
    // 1) Lay duong dan tren may chu. File keo-tha phai upload truoc vi
    //    trinh duyet khong tiet lo duong dan that.
    let path = state.path;
    if (state.url) {
      logLine('Nguồn: ' + state.url.slice(0, 72));
    } else if (!path && state.file) {
      logLine('Đang tải video lên máy chủ...');
      const fd = new FormData();
      fd.append('file', state.file);
      const r = await fetch('/api/upload', { method: 'POST', body: fd });
      if (!r.ok) return failRun('Tải lên thất bại: ' + (await r.text()));
      const j = await r.json();
      path = j.path;
      logLine('Đã nhận ' + j.name + ' (' + fmtSize(j.size) + ')', 'ok');
    }
    if (!path && !state.url) return failRun('Chưa chọn video hoặc dán link');

    // 2) Tao job
    const outs = outputs();
    const wantVoice = $('#voice').value !== 'none';
    const body = {
      path: path || '',
      url: state.url || '',
      lang: 'vi',
      src_lang: $('#src-lang').value,
      voice: wantVoice ? $('#voice').value : null,
      make_voice: wantVoice,
      export_script: outs.includes('script_vi') || outs.includes('script_bi'),
      separate_audio: false,
      blur_old_captions: false,
    };
    const rj = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!rj.ok) return failRun('Không tạo được job: ' + (await rj.text()));
    const job = await rj.json();
    logLine('Bắt đầu xử lý — job ' + job.job_id);

    // 3) Nghe tien trinh qua SSE
    const es = new EventSource('/api/jobs/' + job.job_id + '/events');
    es.onmessage = ev => {
      const d = JSON.parse(ev.data);
      if (d.type === 'log') handleLog(d.line);
      else if (d.type === 'step') {
        for (let i = 0; i < d.index; i++) setStep(i, 'done');
        setStep(d.index, 'active');
      }
      else if (d.type === 'done') finishRun(d);
      else if (d.type === 'error') failRun(d.message);
      else if (d.type === 'end') es.close();
    };
    es.onerror = () => es.close();
  } catch (e) {
    failRun('Lỗi: ' + e.message);
  }
};

// ---- Cai dat API key ----
// Server chi tra 4 ky tu cuoi cua key, khong bao gio tra key day du.

function paintKeys(keys){
  let anySet = false;
  ['gemini', 'deepseek', 'revid'].forEach(name => {
    const k = (keys || {})[name] || {};
    const st = $('#st-' + name);
    const inp = $('#key-' + name);
    if (k.set) {
      anySet = true;
      st.textContent = 'ĐÃ LƯU';
      st.className = 'st ok';
      inp.placeholder = k.masked || 'đã lưu';
      inp.value = '';
    } else {
      st.textContent = 'CHƯA CÓ';
      st.className = 'st';
    }
  });
  $('#key-warn').classList.toggle('show', !anySet);
  return anySet;
}

async function loadSettings(openIfEmpty){
  try {
    const j = await (await fetch('/api/settings')).json();
    const anySet = paintKeys(j.keys);
    if (openIfEmpty && !anySet) $('#settings').classList.add('show');
  } catch (e) {
    console.warn('khong doc duoc cai dat:', e);
  }
}

$$('[data-save]').forEach(btn => btn.onclick = async () => {
  const name = btn.dataset.save;
  const inp = $('#key-' + name);
  const value = inp.value.trim();
  if (!value) { inp.focus(); return; }
  const old = btn.textContent;
  btn.textContent = '...';
  btn.disabled = true;
  try {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, value: value }),
    });
    if (!r.ok) throw new Error(await r.text());
    const j = await r.json();
    paintKeys(j.keys);
    // Key moi co the mo khoa engine -> ve lai cac chip
    ENGINES = j.engines || ENGINES;
    setChipState('mt', 'gemini', ENGINES.gemini, ENGINES.gemini ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    setChipState('mt', 'deepseek', ENGINES.deepseek, ENGINES.deepseek ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    setChipState('asr', 'gemini', ENGINES.gemini, ENGINES.gemini ? 'SẴN SÀNG' : 'CHƯA CÓ KEY');
    calcCost();
    btn.textContent = '✓ Đã lưu';
    setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 1600);
  } catch (e) {
    btn.textContent = 'Lỗi';
    setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 2000);
  }
});

$('#btn-gear').onclick = () => $('#settings').classList.toggle('show');
$('#btn-gear-close').onclick = () => $('#settings').classList.remove('show');

loadSettings(true);   // lan dau chua co key thi tu mo bang cai dat

// ---- Kiem tra va cai ban cap nhat ----

function paintUpdate(d){
  const box = $('#upd'), title = $('#upd-title'), sub = $('#upd-sub');
  const cur = (d.current || {}).version || 'không rõ';

  if (!d.ok) {
    box.classList.remove('new');
    title.textContent = 'Phiên bản ' + cur;
    sub.textContent = d.error || 'Không kiểm tra được bản mới';
    return;
  }
  if (d.has_update) {
    const lat = d.latest || {};
    box.classList.add('new');
    title.textContent = 'Có bản mới: ' + lat.version;
    sub.textContent = (lat.notes || '') + (lat.date ? '  ·  ' + lat.date : '');
  } else {
    box.classList.remove('new');
    title.textContent = 'Đang dùng bản mới nhất';
    sub.textContent = 'Phiên bản ' + cur;
  }
}

async function checkUpdate(){
  try {
    paintUpdate(await (await fetch('/api/update/check')).json());
  } catch (e) {
    paintUpdate({ ok: false, error: e.message, current: {} });
  }
}

$('#btn-upd').onclick = async () => {
  const btn = $('#btn-upd');
  const ok = confirm(
    'Cập nhật app lên bản mới?\n\n' +
    'Được giữ nguyên: API key, thư mục output, cấu hình của bạn.\n' +
    'Bản cũ được sao lưu vào thư mục backup/ trước khi thay.\n\n' +
    'Xong phải tắt và mở lại app.');
  if (!ok) return;

  btn.disabled = true;
  btn.textContent = 'Đang tải...';
  try {
    const r = await fetch('/api/update/apply', { method: 'POST' });
    if (!r.ok) throw new Error((await r.text()).slice(0, 200));
    const d = await r.json();
    $('#upd').classList.remove('new');
    $('#upd-title').textContent = 'Đã cập nhật lên ' + d.version;
    $('#upd-sub').textContent =
      'Hãy TẮT VÀ MỞ LẠI app để dùng bản mới.' +
      (d.config_note ? '  ' + d.config_note : '');
    btn.textContent = 'Xong — mở lại app';
    alert('Cập nhật xong!\n\nĐã thay: ' + (d.replaced || []).join(', ') +
          '\nSao lưu tại: ' + d.backup +
          '\n\nHãy đóng cửa sổ đen rồi bấm lại "Dich Video Viet.bat".');
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Thử lại';
    $('#upd-sub').textContent = 'Lỗi: ' + e.message;
  }
};

checkUpdate();
