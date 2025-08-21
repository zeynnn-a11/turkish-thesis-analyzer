document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    // PDF yükleme
    const uploadRes = await fetch('/upload-pdf/', {
        method: 'POST',
        body: formData
    });
    const uploadData = await uploadRes.json();
    document.getElementById('result').innerText = JSON.stringify(uploadData, null, 2);
});
// PDF yükleme ve metin çıkarma
document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    // PDF'i yükle
    const uploadRes = await fetch('/upload-pdf/', {
        method: 'POST',
        body: formData
    });
    const uploadData = await uploadRes.json();

    // Metni çıkar
    const extractForm = new FormData();
    extractForm.append('filename', uploadData.filename);
    extractForm.append('method', 'pypdf2');
    const extractRes = await fetch('/extract-text/', {
        method: 'POST',
        body: extractForm
    });
    const extractData = await extractRes.json();
    document.getElementById('pdfText').value = extractData.text;
});

// Özetleme butonu
document.getElementById('summarizeBtn').addEventListener('click', async function() {
    const text = document.getElementById('pdfText').value;
    if (!text.trim()) {
        alert("Özetlenecek metin yok!");
        return;
    }
    document.getElementById('summaryResult').innerText = "Özetleniyor, lütfen bekleyin...";

    const analyzeForm = new FormData();
    analyzeForm.append('text', text);

    const analyzeRes = await fetch('/analyze/', {
        method: 'POST',
        body: analyzeForm
    });
    const analyzeData = await analyzeRes.json();

    // Sonuçları göster
    document.getElementById('summaryResult').innerHTML = "<b>Özet:</b> " + analyzeData.ozet;
    document.getElementById('keywordsResult').innerHTML = "<b>RAKE Anahtar Kelimeler:</b> " + analyzeData.rake_keywords.join(", ") +
        "<br><b>YAKE Anahtar Kelimeler:</b> " + analyzeData.yake_keywords.join(", ");
    document.getElementById('categoryResult').innerHTML = "<b>Kategori (Kural):</b> " + analyzeData.kategori_kural +
        "<br><b>Kategori (ML):</b> " + analyzeData.kategori_ml;
});

// Eğer loading göstermek istiyorsanız, HTML dosyanıza şunu ekleyin:
// <div id="loading" style="display:none;">İşlem yapılıyor, lütfen bekleyin...</div>