/**
 * LiverScope AI — Frontend Application
 * Multi-Actor: Admin (CRUD Pasien + Deteksi) & Dokter (Diagnosa)
 * Vanilla JavaScript for Flask + HTML/CSS frontend
 */

// ============================================================
//  TOAST NOTIFICATION SYSTEM
// ============================================================
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'success', duration = 4000) {
    if (!this.container) this.init();
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || '📌'}</span>
      <span class="toast-msg">${message}</span>
      <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    this.container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
};

// ============================================================
//  LOADING OVERLAY
// ============================================================
const Loading = {
  overlay: null,
  steps: [
    { id: 'yolo', label: 'YOLOv11 — Mendeteksi region...' },
    { id: 'resnet', label: 'ResNet50 — Mengekstrak fitur...' },
    { id: 'xgboost', label: 'XGBoost — Mengklasifikasikan...' },
    { id: 'render', label: 'Merender hasil...' },
  ],

  show() {
    this.overlay = document.getElementById('loading-overlay');
    if (this.overlay) {
      this.overlay.classList.add('active');
      this.resetSteps();
      this.animateSteps();
    }
  },

  hide() {
    if (this.overlay) {
      this.steps.forEach(s => {
        const el = document.getElementById(`step-${s.id}`);
        if (el) { el.classList.remove('active'); el.classList.add('done'); }
      });
      setTimeout(() => {
        this.overlay.classList.remove('active');
      }, 400);
    }
  },

  resetSteps() {
    this.steps.forEach(s => {
      const el = document.getElementById(`step-${s.id}`);
      if (el) { el.classList.remove('active', 'done'); }
    });
  },

  animateSteps() {
    this.steps.forEach((s, i) => {
      setTimeout(() => {
        if (i > 0) {
          const prev = document.getElementById(`step-${this.steps[i - 1].id}`);
          if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
        }
        const el = document.getElementById(`step-${s.id}`);
        if (el) el.classList.add('active');
      }, i * 800);
    });
  }
};

// ============================================================
//  TAB SYSTEM
// ============================================================
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tabGroup = btn.closest('.tabs-container');
      tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      tabGroup.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = tabGroup.querySelector(`#${btn.dataset.tab}`);
      if (panel) panel.classList.add('active');
    });
  });
}

// ============================================================
//  LOAD USER INFO INTO SIDEBAR
// ============================================================
async function loadUserInfo() {
  try {
    const res = await fetch('/api/me');
    const data = await res.json();
    if (data.success) {
      const user = data.user;
      const nameEl = document.getElementById('user-name');
      const roleEl = document.getElementById('user-role');
      const avatarEl = document.getElementById('user-avatar');
      if (nameEl) nameEl.textContent = user.nama_lengkap;
      if (roleEl) {
        const roleLabels = { 'super_admin': 'Super Administrator', 'admin': 'Administrator', 'dokter': 'Dokter' };
        roleEl.textContent = roleLabels[user.role] || user.role;
      }
      if (avatarEl) avatarEl.textContent = user.nama_lengkap.charAt(0).toUpperCase();
    }
  } catch (e) {
    // Silent fail
  }
}

// ============================================================
//  FILE UPLOAD (Drag & Drop + Click)
// ============================================================
let selectedFile = null;
let _hasDetected = false;
let _fullResponseData = null;
let _originalImageObj = null;

function initUpload() {
  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('file-input');
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });

  zone.addEventListener('dragleave', () => {
    zone.classList.remove('drag-over');
  });

  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFile(files[0]);
  });

  input.addEventListener('change', () => {
    if (input.files.length > 0) handleFile(input.files[0]);
  });
}

function handleFile(file) {
  // Validate file type (MIME + extension)
  const validTypes = ['image/jpeg', 'image/png', 'image/tiff', 'image/bmp'];
  const validExts = /\.(jpg|jpeg|png|tiff|tif|bmp)$/i;
  const isValidMime = validTypes.includes(file.type);
  const isValidExt = validExts.test(file.name);

  if (!isValidMime && !isValidExt) {
    Toast.show('Format file tidak didukung! Hanya file gambar (JPG, PNG, TIFF, BMP) yang diperbolehkan.', 'error', 5000);
    // Reset input so the same file can be re-selected after correction
    const input = document.getElementById('file-input');
    if (input) input.value = '';
    return;
  }

  // Validate file size (max 50MB)
  const MAX_SIZE = 50 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    Toast.show('Ukuran file terlalu besar! Maksimal 50MB.', 'error', 5000);
    const input = document.getElementById('file-input');
    if (input) input.value = '';
    return;
  }

  selectedFile = file;
  showFilePreview(file);
}

function showFilePreview(file) {
  const previewArea = document.getElementById('file-preview-area');
  if (!previewArea) return;

  const reader = new FileReader();
  reader.onload = e => {
    previewArea.innerHTML = `
      <div class="file-preview">
        <img src="${e.target.result}" alt="Preview">
        <div class="file-info">
          <div class="file-name">${file.name}</div>
          <div class="file-size">${formatFileSize(file.size)}</div>
        </div>
        <button class="file-remove" onclick="removeFile()" title="Hapus">×</button>
      </div>
    `;
    const detectBtn = document.getElementById('detect-btn');
    if (detectBtn) detectBtn.style.display = 'flex';
  };
  reader.readAsDataURL(file);
}

function removeFile() {
  selectedFile = null;
  _hasDetected = false;
  _fullResponseData = null;
  _originalImageObj = null;
  const previewArea = document.getElementById('file-preview-area');
  if (previewArea) previewArea.innerHTML = '';
  const input = document.getElementById('file-input');
  if (input) input.value = '';
  const detectBtn = document.getElementById('detect-btn');
  if (detectBtn) detectBtn.style.display = 'none';
  const confSection = document.getElementById('inline-conf-section');
  if (confSection) confSection.style.display = 'none';
  const hint = document.getElementById('conf-redetect-hint');
  if (hint) hint.style.display = 'none';
  const results = document.getElementById('results-section');
  if (results) results.style.display = 'none';
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ============================================================
//  LOAD PATIENTS FOR DROPDOWN
// ============================================================
async function loadPatientsDropdown() {
  const select = document.getElementById('patient-select');
  if (!select) return;

  try {
    const res = await fetch('/api/patients');
    const data = await res.json();
    if (data.success && data.patients) {
      select.innerHTML = '<option value="">— Pilih pasien —</option>';
      data.patients.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.nama}${p.nik ? ' (' + p.nik + ')' : ''}`;
        select.appendChild(opt);
      });
    }
  } catch (e) {
    // Silent
  }
}

// ============================================================
//  XGBOOST CONFIDENCE FILTER SLIDER
// ============================================================
function initSlider() {
  const slider = document.getElementById('conf-slider');
  const value = document.getElementById('conf-value');
  if (!slider || !value) return;

  slider.addEventListener('input', () => {
    value.textContent = parseFloat(slider.value).toFixed(2);
    if (_hasDetected && _fullResponseData) {
      filterAndRender(parseFloat(slider.value));
    }
  });
}

// ============================================================
//  DETECTION API CALL
// ============================================================
async function runDetection() {
  if (!selectedFile) {
    Toast.show('Pilih gambar terlebih dahulu!', 'warning');
    return;
  }

  const patientSelect = document.getElementById('patient-select');
  const patientId = patientSelect ? patientSelect.value : '';
  if (!patientId) {
    Toast.show('Pilih pasien terlebih dahulu!', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('image', selectedFile);
  formData.append('patient_id', patientId);

  Loading.show();

  try {
    const response = await fetch('/api/detect', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
    Loading.hide();

    if (data.success) {
      _hasDetected = true;
      _fullResponseData = data;
      renderResults(data);
      Toast.show(`Deteksi selesai! ${data.detections.length} region ditemukan oleh YOLO.`, 'success');
      const hint = document.getElementById('conf-redetect-hint');
      if (hint) hint.style.display = 'inline';
    } else {
      Toast.show(`Error: ${data.error}`, 'error');
    }
  } catch (err) {
    Loading.hide();
    Toast.show(`Gagal menjalankan deteksi: ${err.message}`, 'error');
  }
}

// ============================================================
//  RENDER RESULTS
// ============================================================
function renderResults(data) {
  const section = document.getElementById('results-section');
  if (!section) return;
  section.style.display = 'block';
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });

  section.dataset.detectionId = data.detection_id || '';

  renderComparison(data.original_image, data.annotated_image);

  const slider = document.getElementById('conf-slider');
  const threshold = slider ? parseFloat(slider.value) : 0.10;
  filterAndRender(threshold);

  initTabs();
}

// ============================================================
//  CLIENT-SIDE XGBOOST CONFIDENCE FILTER
// ============================================================
function filterAndRender(threshold) {
  if (!_fullResponseData) return;

  const allDetections = _fullResponseData.detections;
  const filtered = allDetections.filter(d => d.xgb_conf >= threshold);

  const metrics = recalculateMetrics(filtered);
  renderMetrics(metrics, _fullResponseData.processing_time);

  const distribution = {};
  filtered.forEach(d => {
    distribution[d.xgb_class] = (distribution[d.xgb_class] || 0) + 1;
  });

  if (filtered.length > 0) {
    document.getElementById('tabs-section').style.display = 'block';
    renderDistributionChart(distribution, _fullResponseData.class_colors);
    renderClinicalInfo(filtered, _fullResponseData.class_descriptions);
    renderTable(filtered);
    renderCrops(filtered, _fullResponseData.class_colors);
    document.getElementById('save-section').style.display = 'block';
  } else {
    document.getElementById('tabs-section').style.display = 'none';
    document.getElementById('save-section').style.display = 'none';
  }

  drawFilteredAnnotations(filtered, _fullResponseData.class_colors);

  const badge = document.getElementById('filter-badge');
  if (badge) {
    const total = _fullResponseData.detections.length;
    badge.textContent = `${filtered.length} / ${total} region`;
  }
}

function recalculateMetrics(detections) {
  const total = detections.length;
  if (total === 0) {
    return {
      total_deteksi: 0, rata_conf_yolo: 0, rata_conf_xgb: 0,
      agreement_rate: 0, kelas_dominan: '-',
    };
  }

  const avgYolo = detections.reduce((s, d) => s + d.yolo_conf, 0) / total;
  const avgXgb = detections.reduce((s, d) => s + d.xgb_conf, 0) / total;
  const matches = detections.filter(d =>
    d.yolo_class.toLowerCase() === d.xgb_class.toLowerCase()
  ).length;
  const agreementRate = matches / total;

  const classCounts = {};
  detections.forEach(d => {
    classCounts[d.xgb_class] = (classCounts[d.xgb_class] || 0) + 1;
  });
  const dominantClass = Object.entries(classCounts)
    .sort((a, b) => b[1] - a[1])[0][0];

  return {
    total_deteksi: total,
    rata_conf_yolo: avgYolo,
    rata_conf_xgb: avgXgb,
    agreement_rate: agreementRate,
    kelas_dominan: dominantClass,
  };
}

function renderMetrics(metrics, processingTime) {
  const grid = document.getElementById('metrics-grid');
  if (!grid) return;

  const items = [
    { value: metrics.total_deteksi, label: 'Total Deteksi', format: 'number' },
    { value: metrics.rata_conf_yolo, label: 'Avg. Conf YOLO', format: 'percent' },
    { value: metrics.rata_conf_xgb, label: 'Avg. Conf XGBoost', format: 'percent' },
    { value: metrics.agreement_rate, label: 'Agreement Rate', format: 'percent' },
    { value: processingTime, label: 'Waktu Proses', format: 'time' },
  ];

  grid.innerHTML = items.map(item => {
    let display;
    if (item.format === 'percent') display = Math.round(item.value * 100) + '%';
    else if (item.format === 'time') display = item.value.toFixed(1) + 's';
    else display = item.value;

    return `
      <div class="metric-card fade-in-up">
        <div class="metric-value">${display}</div>
        <div class="metric-label">${item.label}</div>
      </div>
    `;
  }).join('');
}

function renderComparison(originalUrl, annotatedUrl) {
  const origImg = document.getElementById('original-image');
  if (origImg) origImg.src = originalUrl;

  _originalImageObj = new Image();
  _originalImageObj.onload = () => {
    if (_fullResponseData) {
      const slider = document.getElementById('conf-slider');
      const threshold = slider ? parseFloat(slider.value) : 0.10;
      const filtered = _fullResponseData.detections.filter(d => d.xgb_conf >= threshold);
      drawFilteredAnnotations(filtered, _fullResponseData.class_colors);
    }
  };
  _originalImageObj.src = originalUrl;

  document.getElementById('comparison-section').style.display = 'block';
  const confSection = document.getElementById('inline-conf-section');
  if (confSection) confSection.style.display = 'block';
}

function drawFilteredAnnotations(detections, classColors) {
  const canvas = document.getElementById('annotated-canvas');
  if (!canvas || !_originalImageObj || !_originalImageObj.naturalWidth) return;

  const ctx = canvas.getContext('2d');
  const imgW = _originalImageObj.naturalWidth;
  const imgH = _originalImageObj.naturalHeight;
  canvas.width = imgW;
  canvas.height = imgH;

  ctx.drawImage(_originalImageObj, 0, 0, imgW, imgH);

  detections.forEach(det => {
    const [x1, y1, x2, y2] = det.bbox;
    const color = classColors[det.xgb_class] || '#00ff00';
    const label = `${det.xgb_class}  ${Math.round(det.xgb_conf * 100)}%`;

    const scale = Math.max(1, Math.min(imgW, imgH) / 500);
    const lineWidth = Math.max(2, 3 * scale);
    const fontSize = Math.max(12, 16 * scale);
    const padding = Math.max(3, 4 * scale);

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

    ctx.font = `bold ${fontSize}px Inter, Arial, sans-serif`;
    const textMetrics = ctx.measureText(label);
    const textW = textMetrics.width + padding * 2;
    const textH = fontSize + padding * 2;

    ctx.fillStyle = color;
    ctx.fillRect(x1, y1 - textH, textW, textH);

    ctx.fillStyle = '#fff';
    ctx.fillText(label, x1 + padding, y1 - padding - 2);
  });
}

function renderDistributionChart(distribution, classColors) {
  const ctx = document.getElementById('distribution-chart');
  if (!ctx) return;

  const labels = Object.keys(distribution).filter(k => distribution[k] > 0);
  const values = labels.map(k => distribution[k]);
  const colors = labels.map(k => classColors[k] || '#888');

  if (window._distChart) window._distChart.destroy();

  window._distChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Jumlah',
        data: values,
        backgroundColor: colors.map(c => c + '44'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: 'Distribusi Kelas (XGBoost)',
          color: '#1e293b',
          font: { size: 14, weight: '600', family: 'Inter' },
          padding: { bottom: 16 },
        }
      },
      scales: {
        x: {
          ticks: { color: '#475569', font: { family: 'Inter', weight: '500' } },
          grid: { display: false },
        },
        y: {
          ticks: { color: '#475569', stepSize: 1, font: { family: 'Inter' } },
          grid: { color: 'rgba(148,163,184,0.12)' },
          title: { display: true, text: 'Jumlah', color: '#94a3b8', font: { family: 'Inter' } },
        }
      },
      animation: { duration: 800, easing: 'easeOutQuart' },
    }
  });
}

function renderClinicalInfo(detections, classDescriptions) {
  const container = document.getElementById('clinical-info');
  if (!container) return;

  const classes = [...new Set(detections.map(d => d.xgb_class))];
  container.innerHTML = classes.map(cls => `
    <div class="clinical-card">
      <h4>${cls}</h4>
      <p>${classDescriptions[cls] || ''}</p>
    </div>
  `).join('');
}

function renderTable(detections) {
  const tbody = document.getElementById('detections-tbody');
  if (!tbody) return;

  tbody.innerHTML = detections.map((d, i) => {
    const match = d.yolo_class.toLowerCase() === d.xgb_class.toLowerCase();
    return `
      <tr>
        <td>${i + 1}</td>
        <td>${d.yolo_class}</td>
        <td>${(d.yolo_conf * 100).toFixed(1)}%</td>
        <td><strong>${d.xgb_class}</strong></td>
        <td>${(d.xgb_conf * 100).toFixed(1)}%</td>
        <td>(${d.bbox[0]}, ${d.bbox[1]}) → (${d.bbox[2]}, ${d.bbox[3]})</td>
        <td><span class="badge ${match ? 'badge-match' : 'badge-mismatch'}">${match ? '✅ Match' : '⚠️ Beda'}</span></td>
      </tr>
    `;
  }).join('');
}

function renderCrops(detections, classColors) {
  const grid = document.getElementById('crops-grid');
  if (!grid) return;

  grid.innerHTML = detections.map((d, i) => {
    const match = d.yolo_class.toLowerCase() === d.xgb_class.toLowerCase();
    const color = classColors[d.xgb_class] || '#888';
    return `
      <div class="crop-card fade-in-up" style="animation-delay: ${i * 0.05}s;">
        <img src="${d.crop_url}" alt="Region ${i + 1}">
        <div class="crop-info">
          <span class="crop-class" style="color:${color}">${d.xgb_class}</span>
          <span class="crop-conf">${(d.xgb_conf * 100).toFixed(0)}%</span>
          <div class="crop-meta">
            ${match ? '✅' : '⚠️'} YOLO: ${d.yolo_class} (${(d.yolo_conf * 100).toFixed(0)}%)
            <br>📍 (${d.bbox[0]}, ${d.bbox[1]}) → (${d.bbox[2]}, ${d.bbox[3]})
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ============================================================
//  SAVE TO DATABASE
// ============================================================
async function saveToDatabase() {
  const section = document.getElementById('results-section');
  const detectionId = section ? section.dataset.detectionId : null;
  if (!detectionId) {
    Toast.show('Tidak ada hasil deteksi untuk disimpan!', 'warning');
    return;
  }

  const saveBtn = document.getElementById('save-btn');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '⏳ Menyimpan...';
  }

  try {
    const response = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ detection_id: detectionId }),
    });

    const data = await response.json();

    if (data.success) {
      Toast.show(`Berhasil disimpan ke database! (ID: ${data.analysis_id})`, 'success');
      if (saveBtn) {
        saveBtn.innerHTML = '✅ Tersimpan';
        saveBtn.classList.remove('btn-success');
        saveBtn.classList.add('btn-outline');
      }
    } else {
      Toast.show(`Gagal menyimpan: ${data.error}`, 'error');
      if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '💾 Simpan ke Database'; }
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
    if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '💾 Simpan ke Database'; }
  }
}

// ============================================================
//  CSV DOWNLOAD
// ============================================================
function downloadCSV() {
  const table = document.querySelector('#tab-table .data-table');
  if (!table) return;

  const rows = Array.from(table.querySelectorAll('tr'));
  const csv = rows.map(row => {
    return Array.from(row.querySelectorAll('th, td'))
      .map(cell => `"${cell.textContent.trim()}"`)
      .join(',');
  }).join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'hasil_deteksi_liver.csv';
  a.click();
  URL.revokeObjectURL(url);
  Toast.show('CSV berhasil diunduh!', 'success');
}

// ============================================================
//  PATIENTS CRUD (Admin)
// ============================================================
let _allPatients = [];

async function loadPatients() {
  const container = document.getElementById('patients-list');
  if (!container) return;

  try {
    const response = await fetch('/api/patients');
    const data = await response.json();

    if (!data.success || !data.patients || data.patients.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">👥</span>
          <h3>Belum Ada Data Pasien</h3>
          <p>Klik tombol "Tambah Pasien" untuk menambahkan data pasien baru.</p>
        </div>
      `;
      document.getElementById('patient-count').textContent = '0';
      _allPatients = [];
      return;
    }

    _allPatients = data.patients;
    document.getElementById('patient-count').textContent = data.patients.length;
    renderPatientsList(data.patients);

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">❌</span>
        <h3>Error</h3>
        <p>${err.message}</p>
      </div>
    `;
  }
}

function renderPatientsList(patients) {
  const container = document.getElementById('patients-list');
  if (!container) return;

  container.innerHTML = patients.map(p => {
    const gender = p.jenis_kelamin === 'Perempuan' ? '👩' : '👨';
    const info = [
      p.nik ? `NIK: ${p.nik}` : '',
      p.jenis_kelamin || '',
      p.telepon ? `📞 ${p.telepon}` : '',
    ].filter(Boolean).join(' • ');

    return `
      <div class="patient-card fade-in-up" id="patient-${p.id}">
        <div class="patient-info">
          <h4>${gender} ${p.nama}</h4>
          <p>${info || 'Tidak ada info tambahan'}</p>
        </div>
        <div class="patient-actions">
          <button class="btn btn-outline btn-sm" onclick="showEditModal(${p.id})">✏️ Edit</button>
          <button class="btn btn-danger btn-sm" onclick="confirmDeletePatient(${p.id}, '${p.nama.replace(/'/g, "\\'")}')">🗑️</button>
        </div>
      </div>
    `;
  }).join('');
}

function filterPatients() {
  const query = document.getElementById('search-input').value.toLowerCase();
  const filtered = _allPatients.filter(p =>
    p.nama.toLowerCase().includes(query) ||
    (p.nik && p.nik.toLowerCase().includes(query)) ||
    (p.telepon && p.telepon.includes(query))
  );
  renderPatientsList(filtered);
}

function showAddModal() {
  document.getElementById('modal-title').textContent = '➕ Tambah Pasien Baru';
  document.getElementById('patient-id').value = '';
  document.getElementById('p-nama').value = '';
  document.getElementById('p-nik').value = '';
  document.getElementById('p-telepon').value = '';
  document.getElementById('p-tanggal-lahir').value = '';
  document.getElementById('p-jenis-kelamin').value = 'Laki-laki';
  document.getElementById('p-alamat').value = '';
  clearValidationErrors();
  document.getElementById('patient-modal').classList.add('active');
}

async function showEditModal(id) {
  document.getElementById('modal-title').textContent = '✏️ Edit Data Pasien';
  clearValidationErrors();
  document.getElementById('patient-modal').classList.add('active');

  try {
    const res = await fetch(`/api/patients/${id}`);
    const data = await res.json();
    if (data.success) {
      const p = data.patient;
      document.getElementById('patient-id').value = p.id;
      document.getElementById('p-nama').value = p.nama || '';
      document.getElementById('p-nik').value = p.nik || '';
      document.getElementById('p-telepon').value = p.telepon || '';
      document.getElementById('p-tanggal-lahir').value = p.tanggal_lahir || '';
      document.getElementById('p-jenis-kelamin').value = p.jenis_kelamin || 'Laki-laki';
      document.getElementById('p-alamat').value = p.alamat || '';
    }
  } catch (e) {
    Toast.show('Gagal memuat data pasien', 'error');
  }
}

function closePatientModal() {
  document.getElementById('patient-modal').classList.remove('active');
}

async function savePatient(e) {
  e.preventDefault();
  const btn = document.getElementById('save-patient-btn');

  const id = document.getElementById('patient-id').value;
  const payload = {
    nama: document.getElementById('p-nama').value.trim(),
    nik: document.getElementById('p-nik').value.trim(),
    telepon: document.getElementById('p-telepon').value.trim(),
    tanggal_lahir: document.getElementById('p-tanggal-lahir').value.trim() || null,
    jenis_kelamin: document.getElementById('p-jenis-kelamin').value,
    alamat: document.getElementById('p-alamat').value.trim(),
  };

  // ── Client-side validation ──
  clearValidationErrors();
  let isValid = true;

  // Nama: tidak boleh kosong & tidak boleh ada angka
  if (!payload.nama) {
    setFieldError('fg-nama', 'err-nama', 'Nama lengkap harus diisi.');
    isValid = false;
  } else if (/\d/.test(payload.nama)) {
    setFieldError('fg-nama', 'err-nama', 'Nama tidak boleh mengandung angka.');
    isValid = false;
  }

  // NIK: jika diisi, harus tepat 16 digit angka
  if (payload.nik) {
    if (!/^\d+$/.test(payload.nik)) {
      setFieldError('fg-nik', 'err-nik', 'NIK hanya boleh berisi angka.');
      isValid = false;
    } else if (payload.nik.length !== 16) {
      setFieldError('fg-nik', 'err-nik', `NIK harus tepat 16 digit (saat ini ${payload.nik.length} digit).`);
      isValid = false;
    }
  }

  // Telepon: jika diisi, hanya angka & maks 13 karakter
  if (payload.telepon) {
    if (!/^\d+$/.test(payload.telepon)) {
      setFieldError('fg-telepon', 'err-telepon', 'No. telepon hanya boleh berisi angka.');
      isValid = false;
    } else if (payload.telepon.length > 13) {
      setFieldError('fg-telepon', 'err-telepon', 'No. telepon maksimal 13 digit.');
      isValid = false;
    }
  }

  if (!isValid) {
    Toast.show('Mohon perbaiki data yang tidak valid.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Menyimpan...';

  try {
    const url = id ? `/api/patients/${id}` : '/api/patients';
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (data.success) {
      Toast.show(id ? 'Data pasien berhasil diperbarui!' : 'Pasien baru berhasil ditambahkan!', 'success');
      closePatientModal();
      loadPatients();
    } else {
      Toast.show(`Gagal: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }

  btn.disabled = false;
  btn.innerHTML = '💾 Simpan';
}

// ── Validation Helpers ──
function setFieldError(groupId, errorId, message) {
  const group = document.getElementById(groupId);
  const errorEl = document.getElementById(errorId);
  if (group) group.classList.add('has-error');
  if (errorEl) {
    const span = errorEl.querySelector('span');
    if (span) span.textContent = message;
  }
}

function clearValidationErrors() {
  document.querySelectorAll('.form-group.has-error').forEach(el => el.classList.remove('has-error'));
}

// ── Real-time input filtering ──
function initPatientFormValidation() {
  const nikInput = document.getElementById('p-nik');
  const teleponInput = document.getElementById('p-telepon');
  const namaInput = document.getElementById('p-nama');

  if (nikInput) {
    nikInput.addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '');
      const fg = document.getElementById('fg-nik');
      if (fg) fg.classList.remove('has-error');
    });
  }

  if (teleponInput) {
    teleponInput.addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '');
      const fg = document.getElementById('fg-telepon');
      if (fg) fg.classList.remove('has-error');
    });
  }

  if (namaInput) {
    namaInput.addEventListener('input', function () {
      const fg = document.getElementById('fg-nama');
      if (fg) fg.classList.remove('has-error');
    });
  }
}

let _deletePatientId = null;

function confirmDeletePatient(id, name) {
  _deletePatientId = id;
  document.getElementById('delete-patient-name').textContent = name;
  document.getElementById('confirm-overlay').classList.add('active');
}

function cancelDeletePatient() {
  _deletePatientId = null;
  document.getElementById('confirm-overlay').classList.remove('active');
}

async function executeDeletePatient() {
  if (!_deletePatientId) return;
  try {
    const res = await fetch(`/api/patients/${_deletePatientId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      Toast.show('Pasien berhasil dihapus!', 'success');
      loadPatients();
    } else {
      Toast.show(`Gagal: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }
  _deletePatientId = null;
  document.getElementById('confirm-overlay').classList.remove('active');
}

// ============================================================
//  HISTORY PAGE (Admin)
// ============================================================
async function loadHistory() {
  const container = document.getElementById('history-list');
  if (!container) return;

  try {
    const response = await fetch('/api/history');
    const data = await response.json();

    if (!data.success || !data.analyses || data.analyses.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">📭</span>
          <h3>Belum Ada Riwayat</h3>
          <p>Lakukan deteksi dan simpan hasilnya terlebih dahulu.</p>
          <br>
          <a href="/admin/detect" class="btn btn-primary">🔍 Mulai Deteksi</a>
        </div>
      `;
      document.getElementById('history-count').textContent = '0';
      return;
    }

    document.getElementById('history-count').textContent = data.analyses.length;

    container.innerHTML = data.analyses.map(a => {
      const date = a.created_at ? new Date(a.created_at).toLocaleString('id-ID', {
        day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
      }) : '-';

      const diagStatus = a.has_diagnosis
        ? '<span class="badge badge-done">✅ Sudah Didiagnosa</span>'
        : '<span class="badge badge-waiting">⏳ Menunggu Diagnosa</span>';

      return `
        <div class="history-card fade-in-up" id="history-${a.id}">
          <div class="history-header">
            <div>
              <div class="history-filename">📄 ${a.filename}</div>
              ${a.patient_name ? `<div class="history-patient">👤 ${a.patient_name}${a.patient_nik ? ' (' + a.patient_nik + ')' : ''}</div>` : ''}
              <div class="history-date">🕐 ${date}</div>
            </div>
            <div>${diagStatus}</div>
          </div>
          <div class="history-stats">
            <span class="history-stat">🔍 <strong>${a.total_detections}</strong> deteksi</span>
            <span class="history-stat">🏷️ Dominan: <strong>${a.dominant_class}</strong></span>
            <span class="history-stat">⏱️ ${a.processing_time.toFixed(1)}s</span>
            <span class="history-stat">📊 YOLO: <strong>${Math.round(a.avg_conf_yolo * 100)}%</strong></span>
            <span class="history-stat">📊 XGB: <strong>${Math.round(a.avg_conf_xgb * 100)}%</strong></span>
            <span class="history-stat">🤝 Agreement: <strong>${Math.round(a.agreement_rate * 100)}%</strong></span>
          </div>
          <div class="history-actions">
            <button class="btn btn-outline btn-sm" onclick="showDetail(${a.id})">🔎 Detail</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete(${a.id}, '${a.filename.replace(/'/g, "\\'")}')">🗑️ Hapus</button>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">❌</span>
        <h3>Error</h3>
        <p>${err.message}</p>
      </div>
    `;
  }
}

// ============================================================
//  DETAIL MODAL (Admin history)
// ============================================================
async function showDetail(id) {
  const modal = document.getElementById('detail-modal');
  const body = document.getElementById('modal-body');
  if (!modal || !body) return;

  body.innerHTML = '<div style="text-align:center; padding:2.5rem;"><div class="loading-spinner" style="margin:0 auto;"></div><p class="loading-text" style="margin-top:0.85rem;">Memuat detail...</p></div>';
  modal.classList.add('active');

  try {
    const response = await fetch(`/api/history/${id}`);
    const data = await response.json();

    if (!data.success) {
      body.innerHTML = `<p style="color:var(--error); text-align:center;">Error: ${data.error}</p>`;
      return;
    }

    const a = data.analysis;
    const dets = data.detections;
    const diag = data.diagnosis;

    let html = '';

    // Patient info
    if (a.patient_name) {
      html += `<div class="detail-section">
        <h3>👤 Informasi Pasien</h3>
        <div class="patient-info-grid">
          <div class="patient-info-item"><label>Nama</label><span>${a.patient_name}</span></div>
          ${a.patient_nik ? `<div class="patient-info-item"><label>NIK</label><span>${a.patient_nik}</span></div>` : ''}
          ${a.patient_gender ? `<div class="patient-info-item"><label>Jenis Kelamin</label><span>${a.patient_gender}</span></div>` : ''}
        </div>
      </div>`;
    }

    // Diagnosis
    if (diag) {
      html += `<div class="existing-diagnosis">
        <h4>✅ Diagnosa oleh ${diag.doctor_name || 'Dokter'}</h4>
        <p><span class="diag-label">Diagnosa:</span> ${diag.diagnosa}</p>
        <p><span class="diag-label">Tindakan:</span> ${diag.tindakan}</p>
        ${diag.catatan ? `<p><span class="diag-label">Catatan:</span> ${diag.catatan}</p>` : ''}
      </div>`;
    }

    // Images
    if (a.image_path || a.annotated_image_path) {
      html += '<div class="comparison-grid">';
      if (a.image_path) {
        html += `<div class="comparison-panel">
          <div class="comparison-label">📷 Gambar Asli</div>
          <img src="/uploads/${a.image_path.replace('uploads/', '')}" alt="Original">
        </div>`;
      }
      if (a.annotated_image_path) {
        html += `<div class="comparison-panel">
          <div class="comparison-label">🔍 Hasil Deteksi</div>
          <img src="/uploads/${a.annotated_image_path.replace('uploads/', '')}" alt="Annotated">
        </div>`;
      }
      html += '</div>';
    }

    // Detections table
    if (dets && dets.length > 0) {
      html += '<h4 style="color:var(--text-primary); margin: 1.25rem 0 0.85rem; font-weight:700;">📋 Detail Deteksi</h4>';
      html += '<div class="data-table-wrap"><table class="data-table"><thead><tr>';
      html += '<th>No.</th><th>YOLO</th><th>Conf YOLO</th><th>XGBoost</th><th>Conf XGB</th><th>Lokasi</th>';
      html += '</tr></thead><tbody>';
      dets.forEach((d, i) => {
        html += `<tr>
          <td>${i + 1}</td>
          <td>${d.yolo_class}</td>
          <td>${(d.yolo_conf * 100).toFixed(1)}%</td>
          <td><strong>${d.xgb_class}</strong></td>
          <td>${(d.xgb_conf * 100).toFixed(1)}%</td>
          <td>(${d.bbox_x1},${d.bbox_y1})→(${d.bbox_x2},${d.bbox_y2})</td>
        </tr>`;
      });
      html += '</tbody></table></div>';

      // Crop images
      const cropsWithPath = dets.filter(d => d.crop_image_path);
      if (cropsWithPath.length > 0) {
        html += '<h4 style="color:var(--text-primary); margin: 1.25rem 0 0.85rem; font-weight:700;">🔎 Region Terdeteksi</h4>';
        html += '<div class="crop-grid">';
        cropsWithPath.forEach(d => {
          html += `<div class="crop-card">
            <img src="/uploads/${d.crop_image_path.replace('uploads/', '')}" alt="${d.xgb_class}">
            <div class="crop-info">
              <span class="crop-class">${d.xgb_class}</span>
              <span class="crop-conf">${(d.xgb_conf * 100).toFixed(0)}%</span>
            </div>
          </div>`;
        });
        html += '</div>';
      }
    }

    body.innerHTML = html;

  } catch (err) {
    body.innerHTML = `<p style="color:var(--error); text-align:center;">Error: ${err.message}</p>`;
  }
}

function closeModal() {
  const modal = document.getElementById('detail-modal');
  if (modal) modal.classList.remove('active');
}

// ============================================================
//  DELETE CONFIRMATION (Admin history)
// ============================================================
let deleteTargetId = null;

function confirmDelete(id, filename) {
  deleteTargetId = id;
  const overlay = document.getElementById('confirm-overlay');
  const nameEl = document.getElementById('delete-filename');
  if (nameEl) nameEl.textContent = filename;
  if (overlay) overlay.classList.add('active');
}

function cancelDelete() {
  deleteTargetId = null;
  const overlay = document.getElementById('confirm-overlay');
  if (overlay) overlay.classList.remove('active');
}

async function executeDelete() {
  if (!deleteTargetId) return;
  const overlay = document.getElementById('confirm-overlay');

  try {
    const response = await fetch(`/api/history/${deleteTargetId}`, { method: 'DELETE' });
    const data = await response.json();

    if (data.success) {
      Toast.show('Berhasil dihapus!', 'success');
      const card = document.getElementById(`history-${deleteTargetId}`);
      if (card) {
        card.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => { card.remove(); loadHistory(); }, 300);
      }
    } else {
      Toast.show(`Gagal menghapus: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }

  deleteTargetId = null;
  if (overlay) overlay.classList.remove('active');
}

// ============================================================
//  DOCTOR DASHBOARD
// ============================================================
let _allAnalyses = [];
let _currentFilter = 'all';

async function loadDoctorDashboard() {
  const container = document.getElementById('doctor-list');
  if (!container) return;

  try {
    const response = await fetch('/api/history');
    const data = await response.json();

    if (!data.success || !data.analyses || data.analyses.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">📭</span>
          <h3>Belum Ada Hasil Analisis</h3>
          <p>Admin belum melakukan deteksi atau menyimpan hasilnya.</p>
        </div>
      `;
      document.getElementById('total-count').textContent = '0';
      return;
    }

    _allAnalyses = data.analyses;
    document.getElementById('total-count').textContent = data.analyses.length;
    renderDoctorList(_allAnalyses);

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">❌</span>
        <h3>Error</h3>
        <p>${err.message}</p>
      </div>
    `;
  }
}

function filterByStatus(status, btnEl) {
  _currentFilter = status;
  document.querySelectorAll('.status-filter-btn').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  let filtered;
  if (status === 'waiting') {
    filtered = _allAnalyses.filter(a => !a.has_diagnosis);
  } else if (status === 'done') {
    filtered = _allAnalyses.filter(a => a.has_diagnosis);
  } else {
    filtered = _allAnalyses;
  }

  renderDoctorList(filtered);
}

function renderDoctorList(analyses) {
  const container = document.getElementById('doctor-list');
  if (!container) return;

  if (analyses.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">📋</span>
        <h3>Tidak Ada Data</h3>
        <p>Tidak ada analisis yang sesuai filter.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = analyses.map(a => {
    const date = a.created_at ? new Date(a.created_at).toLocaleString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }) : '-';

    const statusBadge = a.has_diagnosis
      ? '<span class="badge badge-done">✅ Sudah Didiagnosa</span>'
      : '<span class="badge badge-waiting">⏳ Menunggu Diagnosa</span>';

    return `
      <div class="doctor-card fade-in-up" onclick="window.location.href='/doctor/results/${a.id}'">
        <div class="card-header">
          <div>
            <div class="card-patient">👤 ${a.patient_name || 'Pasien tidak diketahui'}</div>
            <div class="card-date">📄 ${a.filename} • 🕐 ${date}</div>
          </div>
          <div>${statusBadge}</div>
        </div>
        <div class="card-stats">
          <span>🔍 <strong>${a.total_detections}</strong> deteksi</span>
          <span>🏷️ Dominan: <strong>${a.dominant_class}</strong></span>
          <span>📊 XGB: <strong>${Math.round(a.avg_conf_xgb * 100)}%</strong></span>
          <span>🤝 Agreement: <strong>${Math.round(a.agreement_rate * 100)}%</strong></span>
        </div>
      </div>
    `;
  }).join('');
}

// ============================================================
//  DOCTOR DETAIL PAGE
// ============================================================
async function loadDoctorDetail() {
  const container = document.getElementById('detail-content');
  if (!container || typeof ANALYSIS_ID === 'undefined') return;

  try {
    const response = await fetch(`/api/history/${ANALYSIS_ID}`);
    const data = await response.json();

    if (!data.success) {
      container.innerHTML = `<div class="empty-state"><span class="empty-icon">❌</span><h3>Error</h3><p>${data.error}</p></div>`;
      return;
    }

    const a = data.analysis;
    const dets = data.detections;
    const diag = data.diagnosis;

    let html = '';

    // Hero
    html += `<div class="hero-header" style="background: linear-gradient(135deg, #065f46 0%, #059669 40%, #0891b2 100%);">
      <h1><span class="hero-icon">🩺</span>Detail Hasil Analisis</h1>
      <p class="hero-subtitle">Analisis file: ${a.filename}</p>
      <div class="hero-badge">ID: ${a.id} • ${a.total_detections} deteksi • ${a.processing_time.toFixed(1)}s</div>
    </div>`;

    // Patient Info
    if (a.patient_name) {
      html += `<div class="detail-section">
        <h3>👤 Informasi Pasien</h3>
        <div class="patient-info-grid">
          <div class="patient-info-item"><label>Nama</label><span>${a.patient_name}</span></div>
          ${a.patient_nik ? `<div class="patient-info-item"><label>NIK / No. RM</label><span>${a.patient_nik}</span></div>` : ''}
          ${a.patient_gender ? `<div class="patient-info-item"><label>Jenis Kelamin</label><span>${a.patient_gender}</span></div>` : ''}
          ${a.patient_dob ? `<div class="patient-info-item"><label>Tanggal Lahir</label><span>${a.patient_dob}</span></div>` : ''}
          ${a.patient_alamat ? `<div class="patient-info-item"><label>Alamat</label><span>${a.patient_alamat}</span></div>` : ''}
          ${a.patient_telepon ? `<div class="patient-info-item"><label>Telepon</label><span>${a.patient_telepon}</span></div>` : ''}
        </div>
      </div>`;
    }

    // Existing Diagnosis
    if (diag) {
      html += `<div class="existing-diagnosis">
        <h4>✅ Diagnosa oleh ${diag.doctor_name || 'Dokter'}</h4>
        <p><span class="diag-label">Diagnosa:</span> ${diag.diagnosa}</p>
        <p><span class="diag-label">Tindakan:</span> ${diag.tindakan}</p>
        ${diag.catatan ? `<p><span class="diag-label">Catatan:</span> ${diag.catatan}</p>` : ''}
        <p style="font-size: 0.72rem; color: var(--text-muted); margin-top: 0.5rem;">
          Terakhir diperbarui: ${diag.updated_at ? new Date(diag.updated_at).toLocaleString('id-ID') : '-'}
        </p>
      </div>`;
    }

    // Diagnosis Form
    html += `<div class="diagnosis-form">
      <h3>🩺 ${diag ? 'Perbarui' : 'Berikan'} Diagnosa</h3>
      <form onsubmit="submitDiagnosis(event)">
        <div class="form-group">
          <label for="diag-diagnosa">Diagnosa <span style="color: var(--error);">*</span></label>
          <textarea id="diag-diagnosa" rows="3" placeholder="Tuliskan diagnosa berdasarkan hasil deteksi..." required>${diag ? diag.diagnosa : ''}</textarea>
        </div>
        <div class="form-group">
          <label for="diag-tindakan">Tindakan <span style="color: var(--error);">*</span></label>
          <select id="diag-tindakan" required>
            <option value="">— Pilih tindakan —</option>
            <option value="Observasi lanjutan" ${diag && diag.tindakan === 'Observasi lanjutan' ? 'selected' : ''}>Observasi lanjutan</option>
            <option value="Biopsi ulang" ${diag && diag.tindakan === 'Biopsi ulang' ? 'selected' : ''}>Biopsi ulang</option>
            <option value="Terapi medikamentosa" ${diag && diag.tindakan === 'Terapi medikamentosa' ? 'selected' : ''}>Terapi medikamentosa</option>
            <option value="Rujuk ke spesialis hepatologi" ${diag && diag.tindakan === 'Rujuk ke spesialis hepatologi' ? 'selected' : ''}>Rujuk ke spesialis hepatologi</option>
            <option value="Tindakan bedah" ${diag && diag.tindakan === 'Tindakan bedah' ? 'selected' : ''}>Tindakan bedah</option>
            <option value="Lainnya" ${diag && diag.tindakan === 'Lainnya' ? 'selected' : ''}>Lainnya</option>
          </select>
        </div>
        <div class="form-group">
          <label for="diag-catatan">Catatan Tambahan</label>
          <textarea id="diag-catatan" rows="2" placeholder="Catatan tambahan (opsional)">${diag && diag.catatan ? diag.catatan : ''}</textarea>
        </div>
        <div style="text-align: right;">
          <button type="submit" class="btn btn-primary" id="submit-diag-btn">💾 ${diag ? 'Perbarui' : 'Simpan'} Diagnosa</button>
        </div>
      </form>
    </div>`;

    // Metrics
    html += `<div class="detail-section">
      <h3>📊 Ringkasan Metrik</h3>
      <div class="metrics-grid stagger">
        <div class="metric-card"><div class="metric-value">${a.total_detections}</div><div class="metric-label">Total Deteksi</div></div>
        <div class="metric-card"><div class="metric-value">${Math.round(a.avg_conf_yolo * 100)}%</div><div class="metric-label">Avg. YOLO</div></div>
        <div class="metric-card"><div class="metric-value">${Math.round(a.avg_conf_xgb * 100)}%</div><div class="metric-label">Avg. XGBoost</div></div>
        <div class="metric-card"><div class="metric-value">${Math.round(a.agreement_rate * 100)}%</div><div class="metric-label">Agreement</div></div>
        <div class="metric-card"><div class="metric-value">${a.processing_time.toFixed(1)}s</div><div class="metric-label">Waktu</div></div>
      </div>
    </div>`;

    // Images
    if (a.image_path || a.annotated_image_path) {
      html += '<div class="comparison-grid">';
      if (a.image_path) {
        html += `<div class="comparison-panel">
          <div class="comparison-label">📷 Gambar Asli</div>
          <img src="/uploads/${a.image_path.replace('uploads/', '')}" alt="Original">
        </div>`;
      }
      if (a.annotated_image_path) {
        html += `<div class="comparison-panel">
          <div class="comparison-label">🔍 Hasil Deteksi</div>
          <img src="/uploads/${a.annotated_image_path.replace('uploads/', '')}" alt="Annotated">
        </div>`;
      }
      html += '</div>';
    }

    // Detections table
    if (dets && dets.length > 0) {
      html += '<div class="detail-section">';
      html += '<h3>📋 Detail Deteksi per Region</h3>';
      html += '<div class="data-table-wrap"><table class="data-table"><thead><tr>';
      html += '<th>No.</th><th>YOLO</th><th>Conf YOLO</th><th>XGBoost</th><th>Conf XGB</th><th>Lokasi</th><th>Status</th>';
      html += '</tr></thead><tbody>';
      dets.forEach((d, i) => {
        const match = d.yolo_class.toLowerCase() === d.xgb_class.toLowerCase();
        html += `<tr>
          <td>${i + 1}</td>
          <td>${d.yolo_class}</td>
          <td>${(d.yolo_conf * 100).toFixed(1)}%</td>
          <td><strong>${d.xgb_class}</strong></td>
          <td>${(d.xgb_conf * 100).toFixed(1)}%</td>
          <td>(${d.bbox_x1},${d.bbox_y1})→(${d.bbox_x2},${d.bbox_y2})</td>
          <td><span class="badge ${match ? 'badge-match' : 'badge-mismatch'}">${match ? '✅ Match' : '⚠️ Beda'}</span></td>
        </tr>`;
      });
      html += '</tbody></table></div>';

      // Crops
      const cropsWithPath = dets.filter(d => d.crop_image_path);
      if (cropsWithPath.length > 0) {
        html += '<h4 style="margin-top:1.25rem; margin-bottom:0.75rem; font-weight:700;">🔎 Region Terdeteksi</h4>';
        html += '<div class="crop-grid">';
        cropsWithPath.forEach(d => {
          html += `<div class="crop-card">
            <img src="/uploads/${d.crop_image_path.replace('uploads/', '')}" alt="${d.xgb_class}">
            <div class="crop-info">
              <span class="crop-class">${d.xgb_class}</span>
              <span class="crop-conf">${(d.xgb_conf * 100).toFixed(0)}%</span>
            </div>
          </div>`;
        });
        html += '</div>';
      }
      html += '</div>';
    }

    container.innerHTML = html;

  } catch (err) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">❌</span><h3>Error</h3><p>${err.message}</p></div>`;
  }
}

async function submitDiagnosis(e) {
  e.preventDefault();
  const btn = document.getElementById('submit-diag-btn');
  btn.disabled = true;
  btn.innerHTML = '⏳ Menyimpan...';

  const payload = {
    analysis_id: parseInt(ANALYSIS_ID),
    diagnosa: document.getElementById('diag-diagnosa').value.trim(),
    tindakan: document.getElementById('diag-tindakan').value,
    catatan: document.getElementById('diag-catatan').value.trim(),
  };

  try {
    const res = await fetch('/api/diagnosis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (data.success) {
      Toast.show('Diagnosa berhasil disimpan!', 'success');
      // Reload to show updated diagnosis
      setTimeout(() => loadDoctorDetail(), 800);
    } else {
      Toast.show(`Gagal: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }

  btn.disabled = false;
  btn.innerHTML = '💾 Simpan Diagnosa';
}

// ============================================================
//  SIDEBAR TOGGLE (Mobile)
// ============================================================
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) sidebar.classList.toggle('open');
}

document.addEventListener('click', e => {
  const sidebar = document.querySelector('.sidebar');
  const toggle = document.querySelector('.sidebar-toggle');
  if (sidebar && sidebar.classList.contains('open') &&
      !sidebar.contains(e.target) && toggle && !toggle.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

// ============================================================
//  USER MANAGEMENT (Super Admin)
// ============================================================
let _allUsers = [];

async function loadUsers() {
  const container = document.getElementById('users-list');
  if (!container) return;

  try {
    const response = await fetch('/api/users');
    const data = await response.json();

    if (!data.success || !data.users || data.users.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">👤</span>
          <h3>Belum Ada Data Akun</h3>
          <p>Klik tombol "Tambah Akun" untuk menambahkan akun baru.</p>
        </div>
      `;
      document.getElementById('user-count').textContent = '0';
      _allUsers = [];
      return;
    }

    _allUsers = data.users;
    // Exclude super_admin from count display
    const nonSA = data.users.filter(u => u.role !== 'super_admin');
    document.getElementById('user-count').textContent = nonSA.length;
    renderUsersList(nonSA);

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">❌</span>
        <h3>Error</h3>
        <p>${err.message}</p>
      </div>
    `;
  }
}

function renderUsersList(users) {
  const container = document.getElementById('users-list');
  if (!container) return;

  container.innerHTML = users.map(u => {
    const roleIcon = u.role === 'admin' ? '🛠️' : '🩺';
    const roleLabel = u.role === 'admin' ? 'Admin' : 'Dokter';
    const roleBadgeClass = u.role === 'admin' ? 'role-badge-admin' : 'role-badge-dokter';
    const isSA = u.role === 'super_admin';

    if (isSA) return ''; // Don't show super_admin in the list

    return `
      <div class="patient-card fade-in-up" id="user-${u.id}">
        <div class="patient-info">
          <h4>${roleIcon} ${u.nama_lengkap} <span class="role-badge ${roleBadgeClass}">${roleLabel}</span></h4>
          <p>Username: <strong>${u.username}</strong></p>
        </div>
        <div class="patient-actions">
          <button class="btn btn-outline btn-sm" onclick="showEditUserModal(${u.id})">✏️ Edit</button>
          <button class="btn btn-danger btn-sm" onclick="confirmDeleteUser(${u.id}, '${u.nama_lengkap.replace(/'/g, "\\'")}')">🗑️</button>
        </div>
      </div>
    `;
  }).join('');
}

function filterUsers() {
  const query = document.getElementById('search-user-input').value.toLowerCase();
  const nonSA = _allUsers.filter(u => u.role !== 'super_admin');
  const filtered = nonSA.filter(u =>
    u.nama_lengkap.toLowerCase().includes(query) ||
    u.username.toLowerCase().includes(query) ||
    u.role.toLowerCase().includes(query)
  );
  renderUsersList(filtered);
}

function showAddUserModal() {
  document.getElementById('user-modal-title').textContent = '➕ Tambah Akun Baru';
  document.getElementById('u-id').value = '';
  document.getElementById('u-nama').value = '';
  document.getElementById('u-username').value = '';
  document.getElementById('u-role').value = 'admin';
  document.getElementById('u-password').value = '';
  document.getElementById('u-password').required = true;
  document.getElementById('pw-required-star').style.display = 'inline';
  document.getElementById('pw-hint').textContent = 'Minimal 8 karakter';
  document.getElementById('user-modal').classList.add('active');
}

async function showEditUserModal(id) {
  document.getElementById('user-modal-title').textContent = '✏️ Edit Akun';
  document.getElementById('u-password').value = '';
  document.getElementById('u-password').required = false;
  document.getElementById('pw-required-star').style.display = 'none';
  document.getElementById('pw-hint').textContent = 'Kosongkan jika tidak ingin mengubah password';
  document.getElementById('user-modal').classList.add('active');

  try {
    const res = await fetch(`/api/users/${id}`);
    const data = await res.json();
    if (data.success) {
      const u = data.user;
      document.getElementById('u-id').value = u.id;
      document.getElementById('u-nama').value = u.nama_lengkap || '';
      document.getElementById('u-username').value = u.username || '';
      document.getElementById('u-role').value = u.role || 'admin';
    }
  } catch (e) {
    Toast.show('Gagal memuat data akun', 'error');
  }
}

function closeUserModal() {
  document.getElementById('user-modal').classList.remove('active');
}

async function saveUser(e) {
  e.preventDefault();
  const btn = document.getElementById('save-user-btn');

  const id = document.getElementById('u-id').value;
  const payload = {
    nama_lengkap: document.getElementById('u-nama').value.trim(),
    username: document.getElementById('u-username').value.trim(),
    role: document.getElementById('u-role').value,
    password: document.getElementById('u-password').value,
  };

  // Client validation
  if (!payload.nama_lengkap) {
    Toast.show('Nama lengkap harus diisi.', 'warning');
    return;
  }
  if (/\d/.test(payload.nama_lengkap)) {
    Toast.show('Nama lengkap tidak boleh mengandung angka.', 'warning');
    return;
  }
  if (!payload.username) {
    Toast.show('Username harus diisi.', 'warning');
    return;
  }
  if (!id && !payload.password) {
    Toast.show('Password harus diisi untuk akun baru.', 'warning');
    return;
  }
  if (payload.password && payload.password.length < 8) {
    Toast.show('Password minimal 8 karakter.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Menyimpan...';

  try {
    const url = id ? `/api/users/${id}` : '/api/users';
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (data.success) {
      Toast.show(id ? 'Akun berhasil diperbarui!' : 'Akun baru berhasil ditambahkan!', 'success');
      closeUserModal();
      loadUsers();
    } else {
      Toast.show(`Gagal: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }

  btn.disabled = false;
  btn.innerHTML = '💾 Simpan';
}

let _deleteUserId = null;

function confirmDeleteUser(id, name) {
  _deleteUserId = id;
  document.getElementById('delete-user-name').textContent = name;
  document.getElementById('confirm-user-overlay').classList.add('active');
}

function cancelDeleteUser() {
  _deleteUserId = null;
  document.getElementById('confirm-user-overlay').classList.remove('active');
}

async function executeDeleteUser() {
  if (!_deleteUserId) return;
  try {
    const res = await fetch(`/api/users/${_deleteUserId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      Toast.show('Akun berhasil dihapus!', 'success');
      loadUsers();
    } else {
      Toast.show(`Gagal: ${data.error}`, 'error');
    }
  } catch (err) {
    Toast.show(`Error: ${err.message}`, 'error');
  }
  _deleteUserId = null;
  document.getElementById('confirm-user-overlay').classList.remove('active');
}

// ============================================================
//  INITIALIZATION
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
  loadUserInfo();
  initUpload();
  initSlider();
  initTabs();

  // Load patients dropdown on detection page
  if (document.getElementById('patient-select')) {
    loadPatientsDropdown();
  }

  // Patients management page
  if (document.getElementById('patients-list')) {
    loadPatients();
    initPatientFormValidation();
  }

  // History page (admin)
  if (document.getElementById('history-list')) {
    loadHistory();
  }

  // Doctor dashboard
  if (document.getElementById('doctor-list')) {
    loadDoctorDashboard();
  }

  // Doctor detail page
  if (document.getElementById('detail-content') && typeof ANALYSIS_ID !== 'undefined') {
    loadDoctorDetail();
  }

  // Super admin users management page
  if (document.getElementById('users-list')) {
    loadUsers();
  }
});
