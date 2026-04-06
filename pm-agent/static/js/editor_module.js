/**
 * Fortimove Image Editor Module
 * redesign_editor.html에서 추출 → 워크벤치 Step 4에 임베드
 * 모든 상태를 FMEditor 네임스페이스에 격리
 */
const FMEditor = {
    // ── 상태 ───────────────────────────────────
    redesignId: null,
    API: '',
    EDITOR_API: '/api/editor',
    SECTION_NAMES: { hero: 'Hero', benefits: '혜택', problem_solution: '문제해결', faq: 'FAQ', spec: '스펙' },

    images: [],
    currentIdx: 0,
    textLayers: [],
    selectedLayer: null,
    history: [],
    historyIdx: -1,
    currentTool: null,
    brushStrokes: [],
    isDragging: false,
    dragOffset: { x: 0, y: 0 },
    layerIdCounter: 0,
    initialized: false,

    // ── 초기화 / 정리 ──────────────────────────
    init(redesignId) {
        if (FMEditor.initialized && FMEditor.redesignId === redesignId) return;

        FMEditor.redesignId = redesignId;
        FMEditor.API = `/api/redesign/${redesignId}`;
        FMEditor.images = [];
        FMEditor.currentIdx = 0;
        FMEditor.textLayers = [];
        FMEditor.selectedLayer = null;
        FMEditor.history = [];
        FMEditor.historyIdx = -1;
        FMEditor.currentTool = null;
        FMEditor.brushStrokes = [];
        FMEditor.layerIdCounter = 0;

        document.getElementById('edRedesignId').textContent = redesignId;
        document.getElementById('edDownloadZip').onclick = () => {
            window.open(`${FMEditor.API}/download`, '_blank');
        };

        // 브러시 크기 이벤트
        const brushEl = document.getElementById('edBrushSize');
        if (brushEl) {
            brushEl.oninput = (e) => {
                document.getElementById('edBrushSizeLabel').textContent = e.target.value;
            };
        }

        // 배경 클릭 → 선택 해제
        const container = document.getElementById('edContainer');
        container.onclick = (e) => {
            if (e.target === document.getElementById('edBgImage') || e.target === container) {
                FMEditor.textLayers.forEach(l => l.el.classList.remove('selected'));
                FMEditor.selectedLayer = null;
                FMEditor.updateTextEditPanel();
            }
        };

        FMEditor.initialized = true;
        FMEditor.loadRedesign();
    },

    destroy() {
        FMEditor.clearAllTextLayers();
        FMEditor.initialized = false;
    },

    // ── 데이터 로드 ────────────────────────────
    async loadRedesign() {
        const res = await fetch(FMEditor.API);
        const data = await res.json();

        if (data.status === 'processing') {
            FMEditor.showLoading('이미지 생성 중...');
            setTimeout(() => FMEditor.loadRedesign(), 3000);
            return;
        }
        FMEditor.hideLoading();
        if (data.status !== 'completed') return;

        const rRes = await fetch(`${FMEditor.API}/result`);
        const rData = await rRes.json();
        FMEditor.images = rData.images || [];
        FMEditor.renderThumbs();
        if (FMEditor.images.length) FMEditor.loadImage(0);

        // Step 5 정보 업데이트
        if (typeof WB !== 'undefined') {
            document.getElementById('s5Images').textContent = FMEditor.images.length + '장';
            WB.populateStep5();
        }
    },

    renderThumbs() {
        const el = document.getElementById('edThumbList');
        const html = FMEditor.images.map((img, i) => `
            <div class="ed-thumb ${i === FMEditor.currentIdx ? 'active' : ''}"
                 onclick="FMEditor.loadImage(${i})"
                 draggable="true" data-idx="${i}"
                 ondragstart="FMEditor.onThumbDragStart(event,${i})"
                 ondragover="FMEditor.onThumbDragOver(event)"
                 ondragenter="event.target.closest('.ed-thumb')?.classList.add('drag-over')"
                 ondragleave="event.target.closest('.ed-thumb')?.classList.remove('drag-over')"
                 ondrop="FMEditor.onThumbDrop(event,${i})">
                <button class="ed-thumb-delete" onclick="event.stopPropagation();FMEditor.deleteImage(${i})" title="삭제">×</button>
                <img src="${FMEditor.API}/image/${img.filename}?t=${Date.now()}">
                <span>${FMEditor.SECTION_NAMES[img.section_type] || img.section_type}</span>
            </div>
        `).join('');
        el.innerHTML = html + `<div class="ed-thumb-add" onclick="document.getElementById('edImageUpload')?.click()" title="이미지 추가">+</div>`;
    },

    // ── 이미지 관리 ───────────────────────────────
    dragSrcIdx: null,

    onThumbDragStart(e, idx) {
        FMEditor.dragSrcIdx = idx;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', idx);
    },

    onThumbDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    },

    async onThumbDrop(e, targetIdx) {
        e.preventDefault();
        e.target.closest('.ed-thumb')?.classList.remove('drag-over');
        if (FMEditor.dragSrcIdx === null || FMEditor.dragSrcIdx === targetIdx) return;
        const [moved] = FMEditor.images.splice(FMEditor.dragSrcIdx, 1);
        FMEditor.images.splice(targetIdx, 0, moved);
        if (FMEditor.currentIdx === FMEditor.dragSrcIdx) FMEditor.currentIdx = targetIdx;
        FMEditor.renderThumbs();
        FMEditor.dragSrcIdx = null;
        try {
            const order = JSON.stringify(FMEditor.images.map(img => img.filename));
            const fd = new FormData();
            fd.append('order', order);
            await fetch(`${FMEditor.API}/images/reorder`, { method: 'POST', body: fd });
        } catch (e) { FMEditor.toast('순서 저장 오류'); }
    },

    async deleteImage(idx) {
        const img = FMEditor.images[idx];
        if (!img || !confirm('이미지를 삭제하시겠습니까?')) return;
        try {
            const res = await fetch(`${FMEditor.API}/images/${img.filename}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('삭제 실패');
            FMEditor.images.splice(idx, 1);
            if (FMEditor.currentIdx >= FMEditor.images.length) FMEditor.currentIdx = Math.max(0, FMEditor.images.length - 1);
            FMEditor.renderThumbs();
            if (FMEditor.images.length) FMEditor.loadImage(FMEditor.currentIdx);
            FMEditor.toast('이미지 삭제됨');
        } catch (e) { FMEditor.toast('삭제 오류'); }
    },

    async uploadImage(file) {
        try {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('section_type', 'custom');
            const res = await fetch(`${FMEditor.API}/images/upload`, { method: 'POST', body: fd });
            if (!res.ok) throw new Error('업로드 실패');
            const data = await res.json();
            FMEditor.images.push(data.image);
            FMEditor.renderThumbs();
            FMEditor.loadImage(FMEditor.images.length - 1);
            FMEditor.toast('이미지 추가됨');
        } catch (e) { FMEditor.toast('업로드 오류'); }
    },

    loadImage(idx) {
        FMEditor.currentIdx = idx;
        FMEditor.renderThumbs();
        FMEditor.clearAllTextLayers();
        FMEditor.selectedLayer = null;
        FMEditor.updateTextEditPanel();
        FMEditor.brushStrokes = [];

        const bgImg = document.getElementById('edBgImage');
        bgImg.onload = () => { FMEditor.saveHistory(); };
        bgImg.src = `${FMEditor.API}/image/${FMEditor.images[idx].filename}?t=${Date.now()}`;
    },

    // ── 텍스트 레이어 시스템 ────────────────────
    addTextLayer(text, x, y, opts) {
        const id = `edtl-${++FMEditor.layerIdCounter}`;
        const layer = {
            id,
            text: text || '텍스트를 입력하세요',
            x: x || 50, y: y || 50,
            fontSize: opts?.fontSize || 24,
            fontWeight: opts?.fontWeight || 'bold',
            color: opts?.color || '#ffffff',
            bgColor: opts?.bgColor || '#000000',
            bgEnabled: opts?.bgEnabled || false,
        };

        const el = document.createElement('div');
        el.className = 'ed-text-layer';
        el.id = id;
        el.innerHTML = `
            <span class="text-content">${layer.text}</span>
            <div class="resize-handle"></div>
            <div class="delete-btn" onclick="event.stopPropagation();FMEditor.deleteLayer('${id}')">×</div>
        `;
        FMEditor.applyLayerStyle(el, layer);

        el.addEventListener('mousedown', e => FMEditor.startDrag(e, id));
        el.addEventListener('dblclick', e => { e.stopPropagation(); FMEditor.editLayerInline(id); });
        el.addEventListener('click', e => { e.stopPropagation(); FMEditor.selectLayer(id); });

        document.getElementById('edContainer').appendChild(el);
        layer.el = el;
        FMEditor.textLayers.push(layer);
        FMEditor.selectLayer(id);
        return id;
    },

    applyLayerStyle(el, layer) {
        el.style.left = layer.x + 'px';
        el.style.top = layer.y + 'px';
        el.style.fontSize = layer.fontSize + 'px';
        el.style.fontWeight = layer.fontWeight;
        el.style.color = layer.color;
        el.style.fontFamily = "'Nanum Gothic', sans-serif";
        el.style.lineHeight = '1.4';
        el.style.whiteSpace = 'pre-wrap';

        if (layer.bgEnabled) {
            el.style.background = layer.bgColor + 'cc';
            el.style.borderRadius = '6px';
            el.style.padding = '8px 12px';
        } else {
            el.style.background = 'transparent';
        }
        el.querySelector('.text-content').textContent = layer.text;
    },

    selectLayer(id) {
        FMEditor.textLayers.forEach(l => l.el.classList.remove('selected'));
        FMEditor.selectedLayer = FMEditor.textLayers.find(l => l.id === id) || null;
        if (FMEditor.selectedLayer) FMEditor.selectedLayer.el.classList.add('selected');
        FMEditor.updateTextEditPanel();
    },

    updateTextEditPanel() {
        const panel = document.getElementById('edTextEditPanel');
        if (!FMEditor.selectedLayer) { panel.style.display = 'none'; return; }
        panel.style.display = 'block';
        document.getElementById('edSelText').value = FMEditor.selectedLayer.text;
        document.getElementById('edSelFontSize').value = FMEditor.selectedLayer.fontSize;
        document.getElementById('edSelFontWeight').value = FMEditor.selectedLayer.fontWeight;
        document.getElementById('edSelColor').value = FMEditor.selectedLayer.color;
        document.getElementById('edSelBgColor').value = FMEditor.selectedLayer.bgColor;
        document.getElementById('edSelBgEnabled').checked = FMEditor.selectedLayer.bgEnabled;
    },

    applyTextEdit() {
        if (!FMEditor.selectedLayer) return;
        FMEditor.selectedLayer.text = document.getElementById('edSelText').value;
        FMEditor.selectedLayer.fontSize = parseInt(document.getElementById('edSelFontSize').value);
        FMEditor.selectedLayer.fontWeight = document.getElementById('edSelFontWeight').value;
        FMEditor.selectedLayer.color = document.getElementById('edSelColor').value;
        FMEditor.selectedLayer.bgColor = document.getElementById('edSelBgColor').value;
        FMEditor.selectedLayer.bgEnabled = document.getElementById('edSelBgEnabled').checked;
        FMEditor.applyLayerStyle(FMEditor.selectedLayer.el, FMEditor.selectedLayer);
        FMEditor.saveHistory();
        FMEditor.toast('텍스트 적용됨');
    },

    editLayerInline(id) {
        const layer = FMEditor.textLayers.find(l => l.id === id);
        if (!layer) return;
        const newText = prompt('텍스트 수정:', layer.text);
        if (newText !== null) {
            layer.text = newText;
            FMEditor.applyLayerStyle(layer.el, layer);
            FMEditor.updateTextEditPanel();
            FMEditor.saveHistory();
        }
    },

    deleteLayer(id) {
        const idx = FMEditor.textLayers.findIndex(l => l.id === id);
        if (idx === -1) return;
        FMEditor.textLayers[idx].el.remove();
        FMEditor.textLayers.splice(idx, 1);
        if (FMEditor.selectedLayer?.id === id) { FMEditor.selectedLayer = null; FMEditor.updateTextEditPanel(); }
        FMEditor.saveHistory();
        FMEditor.toast('텍스트 삭제됨');
    },

    deleteSelectedText() {
        if (FMEditor.selectedLayer) FMEditor.deleteLayer(FMEditor.selectedLayer.id);
    },

    clearAllTextLayers() {
        FMEditor.textLayers.forEach(l => l.el.remove());
        FMEditor.textLayers = [];
    },

    // ── 드래그 ─────────────────────────────────
    startDrag(e, id) {
        if (e.target.classList.contains('delete-btn') || e.target.classList.contains('resize-handle')) return;
        FMEditor.selectLayer(id);
        const layer = FMEditor.textLayers.find(l => l.id === id);
        if (!layer) return;

        FMEditor.isDragging = true;
        const rect = layer.el.getBoundingClientRect();
        FMEditor.dragOffset.x = e.clientX - rect.left;
        FMEditor.dragOffset.y = e.clientY - rect.top;

        const onMove = ev => {
            if (!FMEditor.isDragging) return;
            const container = document.getElementById('edContainer').getBoundingClientRect();
            layer.x = ev.clientX - container.left - FMEditor.dragOffset.x;
            layer.y = ev.clientY - container.top - FMEditor.dragOffset.y;
            layer.el.style.left = layer.x + 'px';
            layer.el.style.top = layer.y + 'px';
        };
        const onUp = () => {
            FMEditor.isDragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            FMEditor.saveHistory();
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        e.preventDefault();
    },

    // ── 도구 ───────────────────────────────────
    setTool(tool) {
        FMEditor.currentTool = FMEditor.currentTool === tool ? null : tool;
        document.getElementById('edBtnSelect').classList.toggle('active', FMEditor.currentTool === 'select');
        document.getElementById('edBtnBrush').classList.toggle('active', FMEditor.currentTool === 'brush');
    },

    // ── 히스토리 ───────────────────────────────
    saveHistory() {
        FMEditor.historyIdx++;
        FMEditor.history = FMEditor.history.slice(0, FMEditor.historyIdx);
        FMEditor.history.push(JSON.stringify(FMEditor.textLayers.map(l => ({
            id: l.id, text: l.text, x: l.x, y: l.y,
            fontSize: l.fontSize, fontWeight: l.fontWeight,
            color: l.color, bgColor: l.bgColor, bgEnabled: l.bgEnabled
        }))));
    },
    undo() { if (FMEditor.historyIdx > 0) { FMEditor.historyIdx--; FMEditor.restoreHistory(); } },
    redo() { if (FMEditor.historyIdx < FMEditor.history.length - 1) { FMEditor.historyIdx++; FMEditor.restoreHistory(); } },
    restoreHistory() {
        FMEditor.clearAllTextLayers();
        const layers = JSON.parse(FMEditor.history[FMEditor.historyIdx]);
        layers.forEach(l => FMEditor.addTextLayer(l.text, l.x, l.y, l));
    },

    // ── AI 편집 ────────────────────────────────
    async callImageAPI(endpoint, formData) {
        FMEditor.showLoading();
        try {
            const imgEl = document.getElementById('edBgImage');
            const canvas = document.createElement('canvas');
            canvas.width = imgEl.naturalWidth;
            canvas.height = imgEl.naturalHeight;
            canvas.getContext('2d').drawImage(imgEl, 0, 0);
            const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));

            if (!formData) formData = new FormData();
            formData.set('file', blob, 'image.png');

            const res = await fetch(`${FMEditor.EDITOR_API}/${endpoint}`, { method: 'POST', body: formData });
            if (!res.ok) throw new Error(await res.text());
            const resultBlob = await res.blob();
            document.getElementById('edBgImage').src = URL.createObjectURL(resultBlob);
            FMEditor.saveHistory();
            FMEditor.toast('완료');
        } catch (e) { FMEditor.toast('오류: ' + e.message); }
        FMEditor.hideLoading();
    },

    aiTranslate() {
        const f = new FormData();
        f.append('moodtone', 'premium');
        FMEditor.callImageAPI('translate', f);
    },
    aiRemoveBg(c) { const f = new FormData(); f.append('bg_color', c); FMEditor.callImageAPI('remove-bg', f); },
    aiRemoveText() { FMEditor.callImageAPI('remove-text'); },
    aiEraseSelection() {
        // 워크벤치에서는 영역선택 도구가 standalone 에디터에서만 지원
        FMEditor.toast('영역선택 AI 지우기는 상세페이지 전용 에디터에서 사용하세요');
    },

    resizeImage() {
        const w = document.getElementById('edResizeW').value;
        const h = document.getElementById('edResizeH').value;
        if (!w || !h) return FMEditor.toast('가로/세로 입력 필요');
        const f = new FormData(); f.append('width', w); f.append('height', h);
        FMEditor.callImageAPI('resize', f);
    },

    cropSelection() { FMEditor.toast('영역 선택 후 자르기'); },

    async applyBrushErase() {
        if (!FMEditor.brushStrokes.length) {
            FMEditor.toast('먼저 AI지우개 브러시로 지울 영역을 칠하세요');
            return;
        }
        FMEditor.showLoading('AI 지우개 처리 중...');
        try {
            const imgEl = document.getElementById('edBgImage');
            const scaleX = imgEl.naturalWidth / imgEl.clientWidth;
            const scaleY = imgEl.naturalHeight / imgEl.clientHeight;
            const srcCanvas = document.createElement('canvas');
            srcCanvas.width = imgEl.naturalWidth;
            srcCanvas.height = imgEl.naturalHeight;
            srcCanvas.getContext('2d').drawImage(imgEl, 0, 0);
            const imgBlob = await new Promise(r => srcCanvas.toBlob(r, 'image/png'));
            const maskCanvas = document.createElement('canvas');
            maskCanvas.width = imgEl.naturalWidth;
            maskCanvas.height = imgEl.naturalHeight;
            const mctx = maskCanvas.getContext('2d');
            mctx.fillStyle = '#000000';
            mctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
            mctx.fillStyle = '#ffffff';
            for (const s of FMEditor.brushStrokes) {
                mctx.beginPath();
                mctx.arc(s.x * scaleX, s.y * scaleY, s.r * scaleX, 0, Math.PI * 2);
                mctx.fill();
            }
            const maskBlob = await new Promise(r => maskCanvas.toBlob(r, 'image/png'));
            const fd = new FormData();
            fd.append('file', imgBlob, 'image.png');
            fd.append('mask', maskBlob, 'mask.png');
            const res = await fetch(`${FMEditor.EDITOR_API}/ai-erase`, { method: 'POST', body: fd });
            if (!res.ok) throw new Error(await res.text());
            const resultBlob = await res.blob();
            document.getElementById('edBgImage').src = URL.createObjectURL(resultBlob);
            FMEditor.clearBrush();
            FMEditor.saveHistory();
            FMEditor.toast('AI 지우기 완료');
        } catch (e) { FMEditor.toast('AI 지우기 오류: ' + e.message); }
        FMEditor.hideLoading();
    },
    clearBrush() { FMEditor.brushStrokes = []; FMEditor.toast('초기화'); },

    async regenerateAll() {
        if (!confirm('전체 재생성하시겠습니까?')) return;
        await fetch(`${FMEditor.API}/regenerate`, { method: 'POST' });
        FMEditor.showLoading('재생성 중...');
        setTimeout(() => FMEditor.loadRedesign(), 3000);
    },

    // ── 저장 (텍스트 레이어 합성) ───────────────
    async saveFinal() {
        FMEditor.showLoading('저장 중...');
        try {
            const imgEl = document.getElementById('edBgImage');
            const canvas = document.createElement('canvas');
            canvas.width = imgEl.naturalWidth;
            canvas.height = imgEl.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(imgEl, 0, 0);

            const scaleX = imgEl.naturalWidth / imgEl.clientWidth;
            const scaleY = imgEl.naturalHeight / imgEl.clientHeight;

            for (const layer of FMEditor.textLayers) {
                const x = layer.x * scaleX;
                const y = layer.y * scaleY;
                const size = layer.fontSize * scaleX;

                ctx.font = `${layer.fontWeight} ${size}px sans-serif`;

                if (layer.bgEnabled) {
                    ctx.fillStyle = layer.bgColor + 'cc';
                    const lines = layer.text.split('\n');
                    const lineH = size * 1.4;
                    const maxW = Math.max(...lines.map(l => ctx.measureText(l).width));
                    const pad = 12 * scaleX;
                    ctx.beginPath();
                    ctx.roundRect(x - pad, y - pad, maxW + pad * 2, lines.length * lineH + pad * 2, 8 * scaleX);
                    ctx.fill();
                }

                ctx.fillStyle = layer.color;
                const lines = layer.text.split('\n');
                const lineH = size * 1.4;
                lines.forEach((line, i) => {
                    ctx.fillText(line, x, y + size + i * lineH);
                });
            }

            const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));

            const form = new FormData();
            form.append('section', FMEditor.images[FMEditor.currentIdx]?.section_type || 'hero');
            form.append('image', blob, 'final.png');
            await fetch(`${FMEditor.API}/edit-section`, { method: 'POST', body: form });

            // 로컬 다운로드
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = FMEditor.images[FMEditor.currentIdx]?.filename || 'edited.png';
            a.click();

            FMEditor.toast('저장 완료');
        } catch (e) { FMEditor.toast('저장 실패: ' + e.message); }
        FMEditor.hideLoading();
    },

    // ── UI 유틸 ────────────────────────────────
    showLoading(t) {
        if (typeof WB !== 'undefined') WB.showLoading(t);
    },
    hideLoading() {
        if (typeof WB !== 'undefined') WB.hideLoading();
    },
    toast(m) {
        if (typeof WB !== 'undefined') WB.toast(m);
    },
};
