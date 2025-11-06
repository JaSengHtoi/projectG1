
from flask import Flask, render_template_string, jsonify, request, send_file
import os
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import base64
import json

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

IMGBB_API_KEY = os.getenv('IMGBB_API_KEY', '') 
METADATA_FILE = 'photos_metadata.json'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_metadata(metadata_list):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata_list, f, indent=2)

def get_image_metadata_from_bytes(image_bytes, filename):
  
    try:
        metadata = {
            'filename': filename,
            'size': len(image_bytes),
            'size_mb': round(len(image_bytes) / (1024 * 1024), 2),
            'size_kb': round(len(image_bytes) / 1024, 2),
            'timestamp': int(datetime.now().timestamp())
        }
        
        now = datetime.now()
        metadata['created'] = now.strftime('%Y-%m-%d %H:%M:%S')
        metadata['year'] = now.year
        metadata['month'] = now.month
        metadata['day'] = now.day
        metadata['date_str'] = now.strftime('%B %d, %Y')
        metadata['time_str'] = now.strftime('%I:%M %p')
        
        with Image.open(BytesIO(image_bytes)) as img:
            metadata['width'] = img.width
            metadata['height'] = img.height
            metadata['format'] = img.format
            metadata['mode'] = img.mode
           
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTime':
                        try:
                            dt = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                            metadata['created'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                            metadata['year'] = dt.year
                            metadata['month'] = dt.month
                            metadata['date_str'] = dt.strftime('%B %d, %Y')
                            metadata['time_str'] = dt.strftime('%I:%M %p')
                        except:
                            pass
                    elif tag == 'Make':
                        metadata['camera_make'] = str(value).strip()
                    elif tag == 'Model':
                        metadata['camera_model'] = str(value).strip()
                    elif tag == 'LensModel':
                        metadata['lens'] = str(value).strip()
                    elif tag == 'FNumber':
                        metadata['aperture'] = f"f/{float(value)}"
                    elif tag == 'ExposureTime':
                        metadata['shutter_speed'] = str(value)
                    elif tag == 'ISOSpeedRatings':
                        metadata['iso'] = str(value)
        
        return metadata
    except Exception as e:
        print(f"Error extracting metadata: {str(e)}")
        return None

def upload_to_imgbb(image_bytes, filename):
    """Upload image to ImgBB (Free hosting)"""
    try:
        if not IMGBB_API_KEY:
            return None, "ImgBB API key not configured"
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": image_base64,
            "name": filename
        }
        
        response = requests.post(url, data=payload, timeout=30)
        result = response.json()
        
        if result.get('success'):
            data = result['data']
            return {
                'url': data['url'],
                'display_url': data['display_url'],
                'delete_url': data['delete_url'],
                'thumb_url': data.get('thumb', {}).get('url', data['url']),
                'id': data['id']
            }, None
        else:
            return None, result.get('error', {}).get('message', 'Upload failed')
            
    except Exception as e:
        return None, str(e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>G1N8CSF Gallery Pro Cloud</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            overflow-x: hidden;
        }

        .header {
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(20px);
            padding: 2rem;
            text-align: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffd700 0%, #ff6b9d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
            letter-spacing: 3px;
        }

        .header .badge {
            display: inline-block;
            background: linear-gradient(135deg, #00ff87, #60efff);
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-top: 0.5rem;
            font-weight: 600;
            color: #000;
        }

        .setup-notice {
            max-width: 800px;
            margin: 2rem auto;
            padding: 1.5rem;
            background: rgba(255, 193, 7, 0.2);
            border: 2px solid rgba(255, 193, 7, 0.5);
            border-radius: 15px;
            text-align: center;
        }

        .setup-notice h3 {
            margin-bottom: 1rem;
            color: #ffc107;
        }

        .setup-notice p {
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }

        .setup-notice code {
            background: rgba(0, 0, 0, 0.3);
            padding: 0.2rem 0.5rem;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .upload-zone {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border: 3px dashed rgba(255, 255, 255, 0.3);
            border-radius: 20px;
            padding: 3rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 2rem;
        }

        .upload-zone:hover {
            border-color: #00ff87;
            background: rgba(0, 255, 135, 0.1);
            transform: translateY(-5px);
        }

        .upload-zone i {
            font-size: 4rem;
            margin-bottom: 1rem;
            display: block;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            padding: 1.5rem;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            text-align: center;
            transition: all 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }

        .stat-number {
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffd700, #ff6b9d);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .controls {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 2rem;
            justify-content: center;
        }

        .btn {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 0.8rem 1.5rem;
            border-radius: 50px;
            color: #fff;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.95rem;
            font-weight: 600;
        }

        .btn:hover {
            background: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
        }

        .btn.active {
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-color: transparent;
        }

        .filter-pills {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 2rem;
            justify-content: center;
        }

        .filter-pill {
            background: rgba(255, 255, 255, 0.12);
            backdrop-filter: blur(10px);
            padding: 0.6rem 1.5rem;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .filter-pill:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .filter-pill.active {
            background: linear-gradient(135deg, #f093fb, #f5576c);
            border-color: rgba(255, 255, 255, 0.4);
        }

        .gallery {
            columns: 4;
            column-gap: 1.5rem;
        }

        @media (max-width: 1200px) { .gallery { columns: 3; } }
        @media (max-width: 800px) { .gallery { columns: 2; } }
        @media (max-width: 500px) { .gallery { columns: 1; } }

        .gallery-item {
            break-inside: avoid;
            margin-bottom: 1.5rem;
            position: relative;
            cursor: pointer;
            animation: fadeIn 0.6s ease backwards;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .gallery-item img {
            width: 100%;
            border-radius: 15px;
            transition: all 0.3s ease;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }

        .gallery-item:hover img {
            transform: scale(1.03);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
        }

        .item-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,0.9) 100%);
            border-radius: 15px;
            opacity: 0;
            transition: all 0.3s ease;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }

        .gallery-item:hover .item-overlay {
            opacity: 1;
        }

        .lightbox {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.98);
            z-index: 1000;
        }

        .lightbox.active { display: flex; }

        .lightbox-container {
            display: flex;
            width: 100%;
            height: 100%;
        }

        .lightbox-main {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            padding: 2rem;
        }

        .lightbox-img {
            max-width: 90%;
            max-height: 90vh;
            border-radius: 10px;
            box-shadow: 0 30px 100px rgba(0, 0, 0, 0.8);
        }

        .lightbox-sidebar {
            width: 400px;
            background: rgba(0, 0, 0, 0.9);
            backdrop-filter: blur(30px);
            padding: 2rem;
            overflow-y: auto;
            border-left: 1px solid rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 1000px) {
            .lightbox-sidebar { display: none; }
        }

        .info-section {
            margin-bottom: 2rem;
        }

        .info-title {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #ffd700, #ff6b9d);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 0.8rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .action-btns {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
        }

        .action-btn {
            flex: 1;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border: none;
            padding: 1rem;
            border-radius: 10px;
            color: #fff;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .action-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
        }

        .action-btn.danger {
            background: linear-gradient(135deg, #ff416c, #ff4b2b);
        }

        .lightbox-close {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #fff;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            font-size: 2rem;
            cursor: pointer;
            transition: all 0.3s ease;
            z-index: 10;
        }

        .lightbox-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #fff;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            font-size: 2rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .nav-prev { left: 20px; }
        .nav-next { right: 420px; }

        @media (max-width: 1000px) {
            .nav-next { right: 20px; }
        }

        .mobile-actions {
            display: none;
        }

        @media (max-width: 1000px) {
            .mobile-actions {
                display: flex;
                position: absolute;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                gap: 1rem;
                z-index: 20;
            }

            .mobile-action-btn {
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(10px);
                border: 2px solid rgba(255, 255, 255, 0.3);
                color: #fff;
                padding: 1rem 2rem;
                border-radius: 50px;
                font-weight: 600;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .mobile-action-btn.download {
                background: linear-gradient(135deg, #667eea, #764ba2);
            }

            .mobile-action-btn.delete {
                background: linear-gradient(135deg, #ff416c, #ff4b2b);
            }
        }

        .loading {
            text-align: center;
            padding: 3rem;
        }

        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.2);
            border-top: 4px solid #fff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 5rem 2rem;
            opacity: 0.7;
        }

        .empty-state i {
            font-size: 5rem;
            margin-bottom: 1rem;
            display: block;
        }

        #fileInput { display: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1><i class="fas fa-cloud"></i> G1N8CSF GALLERY PRO</h1>
        <p>CLOUD PHOTO MANAGEMENT</p>
    </div>

    <div class="setup-notice" id="setupNotice">
        <h3><i class="fas fa-info-circle"></i> Setup Required</h3>
        <p><strong>Get Free ImgBB API Key:</strong></p>
        <p>1. Visit <a href="https://api.imgbb.com/" target="_blank" style="color: #00ff87;">https://api.imgbb.com/</a></p>
        <p>2. Click "Get API Key" (No credit card needed!)</p>
        <p>3. Add to <code>.env</code> file: <code>IMGBB_API_KEY=your_key_here</code></p>
        <p>4. Restart server</p>
    </div>

    <div class="container">
        <div class="upload-zone" onclick="document.getElementById('fileInput').click()">
            <i class="fas fa-cloud-upload-alt"></i>
            <h3>Upload to Free Cloud Storage</h3>
            <p>Click or drag & drop • JPG, PNG, GIF, WebP • Max 16MB</p>
            <input type="file" id="fileInput" multiple accept="image/*">
        </div>

        <div class="stats-grid" id="stats"></div>

        <div class="controls">
            <button class="btn active" onclick="setView('masonry')"><i class="fas fa-th"></i> Masonry</button>
            <button class="btn" onclick="setView('grid')"><i class="fas fa-grip-horizontal"></i> Grid</button>
            <button class="btn" onclick="sortPhotos('date')"><i class="fas fa-calendar"></i> Date</button>
            <button class="btn" onclick="sortPhotos('name')"><i class="fas fa-sort-alpha-down"></i> Name</button>
            <button class="btn" onclick="sortPhotos('size')"><i class="fas fa-weight-hanging"></i> Size</button>
            <button class="btn" onclick="refreshGallery()"><i class="fas fa-sync"></i> Refresh</button>
        </div>

        <div class="filter-pills" id="filterPills"></div>

        <div id="loading" class="loading" style="display: none;">
            <div class="spinner"></div>
            <p>Processing...</p>
        </div>

        <div id="gallery" class="gallery"></div>
    </div>

    <div id="lightbox" class="lightbox">
        <div class="lightbox-container">
            <div class="lightbox-main">
                <button class="lightbox-close" onclick="closeLightbox()">×</button>
                <button class="lightbox-nav nav-prev" onclick="prevImage()">‹</button>
                <button class="lightbox-nav nav-next" onclick="nextImage()">›</button>
                <img id="lightboxImg" class="lightbox-img" src="" alt="">
                
                <div class="mobile-actions">
                    <button class="mobile-action-btn download" onclick="downloadCurrentPhoto()">
                        <i class="fas fa-download"></i> Download
                    </button>
                    <button class="mobile-action-btn delete" onclick="deleteCurrentPhoto()">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            </div>
            <div class="lightbox-sidebar" id="lightboxInfo"></div>
        </div>
    </div>

    <script>
        let photos = [];
        let currentIndex = 0;
        let currentView = 'masonry';
        let currentFilter = 'all';

        document.getElementById('fileInput').addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files.length) return;

            const formData = new FormData();
            for (let file of files) formData.append('files', file);

            document.getElementById('loading').style.display = 'block';

            try {
                const res = await fetch('/upload', { method: 'POST', body: formData });
                const data = await res.json();
                
                if (data.success) {
                    await loadPhotos();
                    document.getElementById('setupNotice').style.display = 'none';
                } else {
                    alert('Upload failed: ' + data.message);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
                e.target.value = '';
            }
        });

        async function loadPhotos() {
            document.getElementById('loading').style.display = 'block';
            try {
                const res = await fetch('/photos');
                photos = await res.json();
                if (photos.length > 0) {
                    document.getElementById('setupNotice').style.display = 'none';
                }
                updateStats();
                updateFilters();
                displayPhotos();
            } catch (err) {
                console.error(err);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        function updateStats() {
            const totalSize = photos.reduce((sum, p) => sum + (p.size || 0), 0);
            const years = new Set(photos.map(p => p.year));
            const months = new Set(photos.map(p => `${p.year}-${p.month}`));
            
            document.getElementById('stats').innerHTML = `
                <div class="stat-card">
                    <div class="stat-number">${photos.length}</div>
                    <div class="stat-label"><i class="fas fa-images"></i> Total Photos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${years.size}</div>
                    <div class="stat-label"><i class="fas fa-calendar-alt"></i> Years</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${months.size}</div>
                    <div class="stat-label"><i class="fas fa-calendar-week"></i> Months</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${(totalSize / (1024*1024)).toFixed(1)}</div>
                    <div class="stat-label"><i class="fas fa-cloud"></i> MB Free</div>
                </div>
            `;
        }

        function updateFilters() {
            const byYear = {};
            photos.forEach(p => {
                if (!byYear[p.year]) byYear[p.year] = [];
                byYear[p.year].push(p);
            });

            let html = `<div class="filter-pill ${currentFilter === 'all' ? 'active' : ''}" onclick="filterByYear('all')">
                <i class="fas fa-folder-open"></i> All Photos (${photos.length})
            </div>`;

            Object.keys(byYear).sort().reverse().forEach(year => {
                html += `<div class="filter-pill ${currentFilter === year ? 'active' : ''}" onclick="filterByYear('${year}')">
                    <i class="fas fa-calendar"></i> ${year} (${byYear[year].length})
                </div>`;
            });

            document.getElementById('filterPills').innerHTML = html;
        }

        function filterByYear(year) {
            currentFilter = year;
            updateFilters();
            displayPhotos();
        }

        function displayPhotos() {
            const gallery = document.getElementById('gallery');
            let filtered = currentFilter === 'all' ? photos : photos.filter(p => p.year == currentFilter);

            if (!filtered.length) {
                gallery.innerHTML = '<div class="empty-state"><i class="fas fa-image"></i><p>No photos found</p></div>';
                return;
            }

            gallery.innerHTML = filtered.map((p, i) => {
                const idx = photos.indexOf(p);
                return `
                    <div class="gallery-item" onclick="openLightbox(${idx})" style="animation-delay: ${i * 0.05}s">
                        <img src="${p.url}" alt="${p.filename}" loading="lazy">
                        <div class="item-overlay">
                            <div class="item-info">
                                <strong>${p.filename}</strong>
                                <div><i class="fas fa-calendar"></i> ${p.date_str}</div>
                                <div><i class="fas fa-clock"></i> ${p.time_str}</div>
                                <div><i class="fas fa-ruler-combined"></i> ${p.width}×${p.height}</div>
                                <div><i class="fas fa-cloud"></i> ${p.size_mb} MB</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            gallery.style.display = currentView === 'grid' ? 'grid' : 'block';
            gallery.style.gridTemplateColumns = currentView === 'grid' ? 'repeat(auto-fill, minmax(300px, 1fr))' : '';
        }

        function openLightbox(idx) {
            currentIndex = idx;
            const p = photos[idx];
            document.getElementById('lightboxImg').src = p.url;
            
            let cameraInfo = '';
            if (p.camera_make || p.camera_model) {
                cameraInfo = `
                    <div class="info-section">
                        <div class="info-title"><i class="fas fa-camera"></i> Camera</div>
                        ${p.camera_make ? `<div class="info-row"><span class="info-label">Make</span><span class="info-value">${p.camera_make}</span></div>` : ''}
                        ${p.camera_model ? `<div class="info-row"><span class="info-label">Model</span><span class="info-value">${p.camera_model}</span></div>` : ''}
                        ${p.lens ? `<div class="info-row"><span class="info-label">Lens</span><span class="info-value">${p.lens}</span></div>` : ''}
                    </div>
                `;
            }

            let exifInfo = '';
            if (p.aperture || p.shutter_speed || p.iso) {
                exifInfo = `
                    <div class="info-section">
                        <div class="info-title"><i class="fas fa-cog"></i> Settings</div>
                        ${p.aperture ? `<div class="info-row"><span class="info-label">Aperture</span><span class="info-value">${p.aperture}</span></div>` : ''}
                        ${p.shutter_speed ? `<div class="info-row"><span class="info-label">Shutter</span><span class="info-value">${p.shutter_speed}s</span></div>` : ''}
                        ${p.iso ? `<div class="info-row"><span class="info-label">ISO</span><span class="info-value">${p.iso}</span></div>` : ''}
                    </div>
                `;
            }

            document.getElementById('lightboxInfo').innerHTML = `
                <div class="info-section">
                    <div class="info-title"><i class="fas fa-info-circle"></i> Details</div>
                    <div class="info-row"><span class="info-label">Filename</span><span class="info-value">${p.filename}</span></div>
                    <div class="info-row"><span class="info-label">Format</span><span class="info-value">${p.format || 'N/A'}</span></div>
                    <div class="info-row"><span class="info-label">Size</span><span class="info-value">${p.width} × ${p.height} px</span></div>
                    <div class="info-row"><span class="info-label">File Size</span><span class="info-value">${p.size_mb} MB</span></div>
                </div>

                <div class="info-section">
                    <div class="info-title"><i class="fas fa-calendar-day"></i> Date & Time</div>
                    <div class="info-row"><span class="info-label">Date</span><span class="info-value">${p.date_str}</span></div>
                    <div class="info-row"><span class="info-label">Time</span><span class="info-value">${p.time_str}</span></div>
                    <div class="info-row"><span class="info-label">Year</span><span class="info-value">${p.year}</span></div>
                </div>

                <div class="info-section">
                    <div class="info-title"><i class="fas fa-cloud"></i> Free Hosting</div>
                    <div class="info-row"><span class="info-label">Service</span><span class="info-value">ImgBB</span></div>
                    <div class="info-row"><span class="info-label">ID</span><span class="info-value">${p.id || 'N/A'}</span></div>
                </div>

                ${cameraInfo}
                ${exifInfo}

                <div class="action-btns">
                    <button class="action-btn" onclick="downloadPhoto('${p.url}', '${p.filename}')">
                        <i class="fas fa-download"></i> Download
                    </button>
                    <button class="action-btn danger" onclick="deletePhoto('${p.id}')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            `;
            
            document.getElementById('lightbox').classList.add('active');
        }

        function closeLightbox() {
            document.getElementById('lightbox').classList.remove('active');
        }

        function nextImage() {
            currentIndex = (currentIndex + 1) % photos.length;
            openLightbox(currentIndex);
        }

        function prevImage() {
            currentIndex = (currentIndex - 1 + photos.length) % photos.length;
            openLightbox(currentIndex);
        }

        function downloadPhoto(url, filename) {
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            link.target = '_blank';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function downloadCurrentPhoto() {
            const p = photos[currentIndex];
            downloadPhoto(p.url, p.filename);
        }

        async function deletePhoto(id) {
            if (!confirm(`Delete "${photos[currentIndex].filename}"?\n\nThis will permanently remove from cloud!`)) return;

            document.getElementById('loading').style.display = 'block';

            try {
                const res = await fetch('/delete/' + id, { 
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                
                if (data.success) {
                    closeLightbox();
                    await loadPhotos();
                } else {
                    alert('Failed to delete: ' + data.message);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        function deleteCurrentPhoto() {
            const p = photos[currentIndex];
            deletePhoto(p.id);
        }

        function setView(view) {
            currentView = view;
            document.querySelectorAll('.controls .btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            displayPhotos();
        }

        function sortPhotos(type) {
            if (type === 'date') {
                photos.sort((a, b) => b.timestamp - a.timestamp);
            } else if (type === 'name') {
                photos.sort((a, b) => a.filename.localeCompare(b.filename));
            } else if (type === 'size') {
                photos.sort((a, b) => b.size - a.size);
            }
            displayPhotos();
        }

        function refreshGallery() {
            loadPhotos();
        }

        document.addEventListener('keydown', (e) => {
            if (!document.getElementById('lightbox').classList.contains('active')) return;
            if (e.key === 'ArrowRight') nextImage();
            if (e.key === 'ArrowLeft') prevImage();
            if (e.key === 'Escape') closeLightbox();
        });

        document.getElementById('lightbox').addEventListener('click', (e) => {
            if (e.target.id === 'lightbox') closeLightbox();
        });

        loadPhotos();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/photos')
def get_photos():

    try:
        photos = load_metadata()
        photos.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return jsonify(photos)
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify([])

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        if not IMGBB_API_KEY:
            return jsonify({
                'success': False, 
                'message': 'ImgBB API key not configured. Please add IMGBB_API_KEY to .env file'
            }), 400
        
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        metadata_list = load_metadata()
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_bytes = file.read()
                
                metadata = get_image_metadata_from_bytes(image_bytes, filename)
                if not metadata:
                    continue
                
                upload_result, error = upload_to_imgbb(image_bytes, filename)
                
                if upload_result:
                    metadata['url'] = upload_result['url']
                    metadata['display_url'] = upload_result['display_url']
                    metadata['delete_url'] = upload_result['delete_url']
                    metadata['thumb_url'] = upload_result['thumb_url']
                    metadata['id'] = upload_result['id']
                    
                    metadata_list.append(metadata)
                    uploaded_files.append(filename)
                    
                    print(f"Uploaded {filename} to ImgBB")
                else:
                    print(f"Failed to upload {filename}: {error}")
        
        save_metadata(metadata_list)
        
        if uploaded_files:
            return jsonify({
                'success': True,
                'message': f'{len(uploaded_files)} files uploaded successfully',
                'files': uploaded_files
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No files were uploaded'
            }), 400
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/download/<path:url>')
def download_file(url):
    try:
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/delete/<photo_id>', methods=['DELETE'])
def delete_file(photo_id):
    try:
        print(f"Deleting photo: {photo_id}")
        
        metadata_list = load_metadata()
        
        original_count = len(metadata_list)
        metadata_list = [p for p in metadata_list if p.get('id') != photo_id]
        
        if len(metadata_list) < original_count:
            save_metadata(metadata_list)
            print(f"Successfully removed photo {photo_id} from metadata")
            return jsonify({
                'success': True, 
                'message': 'Photo removed from gallery (ImgBB file still exists)'
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Photo not found'}), 404
        
    except Exception as e:
        print(f"Delete error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("=" * 70)
    print("🎉 G1N8CSF GALLERY PRO -  CLOUD EDITION")
    print("=" * 70)
    print(f"✨ Server running at: http://localhost:5000")

    print("\n🚀 Starting server...\n")  
    app.run(debug=True, host='0.0.0.0', port=5000)
