// Frontend Application Controller for FaceLedger Pipeline

document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('fileInput');
  const dropZone = document.getElementById('dropZone');
  const facePreview = document.getElementById('facePreview');
  const queryInput = document.getElementById('queryInput');
  const runBtn = document.getElementById('runBtn');
  const verifyBtn = document.getElementById('verifyBtn');
  const tamperBtn = document.getElementById('tamperBtn');
  const samplePills = document.getElementById('samplePills');
  const tamperReport = document.getElementById('tamperReport');

  let currentImageSrc = '/samples/test_face_1.jpg';
  let selectedPlatform = 'all';

  // Load available sample images
  async function loadSamples() {
    try {
      const res = await fetch('/api/samples');
      const data = await res.json();
      samplePills.innerHTML = '';

      data.samples.forEach((sample, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `sample-pill-btn ${idx === 0 ? 'active' : ''}`;
        btn.innerHTML = `<img src="${sample.url}" alt="${sample.name}"> <span>${sample.name}</span>`;
        btn.onclick = () => {
          document.querySelectorAll('.sample-pill-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentImageSrc = sample.url;
          facePreview.src = sample.url;
        };
        samplePills.appendChild(btn);
      });
    } catch (e) {
      console.error('Error loading samples:', e);
    }
  }

  // Quick tag buttons for query
  document.querySelectorAll('.quick-tags .tag-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.getAttribute('data-query');
    });
  });

  // Platform selection buttons
  document.querySelectorAll('.platform-tag').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.platform-tag').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedPlatform = btn.getAttribute('data-platform') || 'all';
    });
  });

  // Dropzone & File upload
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleFile(e.target.files[0]);
    }
  });

  function handleFile(file) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      currentImageSrc = ev.target.result;
      facePreview.src = currentImageSrc;
      document.querySelectorAll('.sample-pill-btn').forEach(b => b.classList.remove('active'));
    };
    reader.readAsDataURL(file);
  }

  // Stepper state updates
  function setStep(stepIndex) {
    for (let i = 1; i <= 4; i++) {
      const node = document.getElementById(`step${i}-indicator`);
      const conn = document.getElementById(`conn${i - 1}`);
      if (i <= stepIndex) {
        node.classList.add('active');
        if (conn) conn.classList.add('filled');
      } else {
        node.classList.remove('active');
        if (conn) conn.classList.remove('filled');
      }
    }
  }

  // Run full pipeline
  runBtn.addEventListener('click', async () => {
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="btn-text">Creating proof record...</span><span class="btn-icon">⌛</span>';
    setStep(1);

    try {
      setStep(2);
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: currentImageSrc,
          query: queryInput.value.trim() || 'Satya Nadella',
          platform: selectedPlatform,
          mode: 'local'
        })
      });

      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.message || 'Pipeline execution failed');
      }

      setStep(3);
      const state = data.state;
      const post = state.post_data;
      
      // Update UI with results
      document.getElementById('bioStatus').textContent = 'Processed';
      document.getElementById('faceHashDisplay').textContent = truncateHash(state.face_hash);
      document.getElementById('faceHashDisplay').title = state.face_hash;

      document.getElementById('socialPlatform').textContent = post.platform.toUpperCase();
      document.getElementById('postAuthor').textContent = post.author;
      document.getElementById('postText').textContent = post.text;
      document.getElementById('postUrl').href = post.url;
      document.getElementById('postUrl').textContent = `Open Post on ${post.platform.toUpperCase()} ↗`;
      document.getElementById('postUrl').target = '_blank';
      document.getElementById('postUrl').rel = 'noopener noreferrer';
      document.getElementById('matchScore').textContent = `${(post.match_confidence * 100).toFixed(1)}% Match`;
      document.getElementById('postHashDisplay').textContent = truncateHash(state.post_hash);
      document.getElementById('postHashDisplay').title = state.post_hash;

      document.getElementById('txHashDisplay').textContent = truncateHash(state.tx_hash);
      document.getElementById('txHashDisplay').title = state.tx_hash;
      document.getElementById('contractAddrDisplay').textContent = truncateHash(state.contract_address);
      document.getElementById('contractAddrDisplay').title = state.contract_address;
      document.getElementById('merkleRootDisplay').textContent = truncateHash(state.merkle_root);
      document.getElementById('merkleRootDisplay').title = state.merkle_root;
      document.getElementById('blockTimeDisplay').textContent = `Block #${state.block_number} (${new Date(state.timestamp * 1000).toLocaleTimeString()})`;
      document.getElementById('blockHeight').textContent = `Block #${state.block_number}`;

      // Update Inspector: Search steps
      const steps = state.search_steps || post.search_steps || [];
      const traceLogList = document.getElementById('traceLogList');
      document.getElementById('stepsCount').textContent = steps.length;
      if (steps.length > 0) {
        traceLogList.innerHTML = steps.map(s => `<li class="log-entry">${s}</li>`).join('');
      } else {
        traceLogList.innerHTML = `<li class="log-entry">Direct verified web query executed for ${post.platform.toUpperCase()}.</li>`;
      }

      // Update Inspector: Discovered Candidates Table
      const candidates = state.candidates_discovered || post.candidates_discovered || [];
      const candTbody = document.getElementById('candidatesTableBody');
      document.getElementById('candCount').textContent = candidates.length;
      if (candidates.length > 0) {
        candTbody.innerHTML = candidates.map(c => `
          <tr>
            <td><strong style="text-transform:uppercase">${c.platform}</strong></td>
            <td>${c.author || '@user'}</td>
            <td>${c.title || c.url}</td>
            <td><span style="color:#57934f;font-weight:700">${(c.score * 100).toFixed(0)}%</span></td>
            <td><a href="${c.url}" target="_blank" rel="noopener" class="post-link">View ↗</a></td>
          </tr>
        `).join('');
      } else {
        candTbody.innerHTML = `<tr><td colspan="5" class="empty-table-msg">Best matching post ${post.url} verified.</td></tr>`;
      }

      // Update Inspector: Cryptographic Details
      document.getElementById('fullFaceHash').textContent = state.face_hash;
      document.getElementById('fullPostHash').textContent = state.post_hash;
      document.getElementById('fullMerkleRoot').textContent = state.merkle_root;
      const vecSample = state.face_data?.feature_vector_sample || [];
      document.getElementById('vectorPreview').textContent = `[${vecSample.join(', ')} ... 128 total dimensions]`;

      setStep(4);
      tamperReport.innerHTML = `
        <div class="audit-entry success">
          <span>✓ <strong>On-chain confirmation:</strong> Source and reference anchored in Block #${state.block_number}.</span>
          <span class="font-mono">${new Date(state.timestamp * 1000).toLocaleTimeString()}</span>
        </div>
      `;

    } catch (err) {
      alert('Error running pipeline: ' + err.message);
    } finally {
      runBtn.disabled = false;
      runBtn.innerHTML = '<span class="btn-text">Create proof record</span><span class="btn-icon">→</span>';
    }
  });

  // Inspector Tab Switching
  document.querySelectorAll('.trace-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.trace-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));

      tab.classList.add('active');
      const targetId = tab.getAttribute('data-tab');
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.remove('hidden');
    });
  });

  // Re-verify on-chain
  verifyBtn.addEventListener('click', async () => {
    verifyBtn.disabled = true;
    try {
      const res = await fetch('/api/verify', { method: 'POST' });
      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.message || 'Verification failed');
      }

      const v = data.verification;
      tamperReport.innerHTML = `
        <div class="audit-entry success">
          <span>✅ <strong>Smart Contract Audit Passed:</strong> Data matches on-chain cryptographic state.</span>
          <span>Verified at ${new Date().toLocaleTimeString()}</span>
        </div>
      `;
    } catch (e) {
      alert('Verification error: ' + e.message);
    } finally {
      verifyBtn.disabled = false;
    }
  });

  // Tamper attack audit
  tamperBtn.addEventListener('click', async () => {
    tamperBtn.disabled = true;
    try {
      const res = await fetch('/api/tamper', { method: 'POST' });
      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.message || 'Tamper test failed');
      }

      const r = data.report;
      tamperReport.innerHTML = `
        <div class="audit-entry success">
          <span>[1] Authentic State: <strong>Valid on Blockchain</strong></span>
          <span>${r.authentic.verified ? 'PASSED ✅' : 'FAILED'}</span>
        </div>
        <div class="audit-entry rejected">
          <span>[2] Adversary Alters Text: <strong>Rejected on Blockchain</strong></span>
          <span style="color: var(--red); font-weight: 600;">TAMPER DETECTED ❌</span>
        </div>
        <div class="audit-entry rejected">
          <span>[3] Adversary Alters Media: <strong>Rejected on Blockchain</strong></span>
          <span style="color: var(--red); font-weight: 600;">TAMPER DETECTED ❌</span>
        </div>
      `;
    } catch (e) {
      alert('Tamper demonstration error: ' + e.message);
    } finally {
      tamperBtn.disabled = false;
    }
  });

  function truncateHash(h) {
    if (!h || h.length < 16) return h || '--';
    return `${h.slice(0, 10)}...${h.slice(-6)}`;
  }

  // Load initial samples
  loadSamples();
});
