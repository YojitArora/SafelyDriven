/**
 * SafelyDriven - Driver Drowsiness Detection
 * Interaction Logic (Synced with Python Backend + Video Feed)
 */

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const panel = document.querySelector('.primary-panel');
    const videoPlaceholder = document.getElementById('video-placeholder');

    // New UI Elements
    const camDot = document.getElementById('cam-dot');
    const ardDot = document.getElementById('ard-dot');
    const earSlider = document.getElementById('ear-slider');
    const earVal = document.getElementById('ear-val');
    const marSlider = document.getElementById('mar-slider');
    const marVal = document.getElementById('mar-val');
    const sosPhoneInput = document.getElementById('sos-phone-input');
    const logList = document.getElementById('log-list');

    // Analytics Metrics
    const scoreVal = document.getElementById('score-val');
    const scoreBox = document.querySelector('.score-box');
    const earGaugeVal = document.getElementById('ear-gauge-val');
    const emotionVal = document.getElementById('emotion-val');
    const emotionScoreEl = document.getElementById('emotion-score');
    const stressAlert = document.getElementById('stress-alert');
    const sosAlert = document.getElementById('sos-alert');

    let isMonitoring = false;
    let pollInterval = null;

    // Chart.js Variables
    let analyticsChart = null;
    const maxDataPoints = 60; // 30 seconds at 500ms polling

    // Leaflet Map Variables
    let map = null;
    let userMarker = null;

    // --- Voice Alerts ---
    const synth = window.speechSynthesis;
    let spokenDrowsy = false;
    let spokenStress = false;
    let spokenSos = false;

    function speakAlert(text) {
        if (!synth) return;
        if (synth.speaking) synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        synth.speak(utterance);
    }

    function initChart() {
        const ctx = document.getElementById('analytics-chart');
        if(!ctx) return;
        
        analyticsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(maxDataPoints).fill(''),
                datasets: [
                    {
                        label: 'EAR',
                        data: Array(maxDataPoints).fill(0),
                        borderColor: '#10b981',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'MAR',
                        data: Array(maxDataPoints).fill(0),
                        borderColor: '#fbbf24',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1.0,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#9ca3af' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { display: false }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f3f4f6' } }
                }
            }
        });
    }

    function updateChart(ear, mar) {
        if(!analyticsChart) return;
        
        analyticsChart.data.datasets[0].data.shift();
        analyticsChart.data.datasets[0].data.push(ear);
        
        analyticsChart.data.datasets[1].data.shift();
        analyticsChart.data.datasets[1].data.push(mar);
        
        analyticsChart.update();
    }

    function initMap() {
        if(map) return; // already initialized
        const mapEl = document.getElementById('sos-map');
        if (!mapEl) return;
        
        map = L.map('sos-map').setView([0, 0], 2);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);

        // Try to get actual location
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(position => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                map.setView([lat, lng], 14);
                
                const customIcon = L.divIcon({
                    className: 'driver-marker',
                    html: '<div style="background-color: var(--accent); width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px var(--accent);"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                });
                
                userMarker = L.marker([lat, lng], {icon: customIcon}).addTo(map)
                    .bindPopup("Driver's Live Location").openPopup();
            });
        }
    }
    
    function setSOSMapAlert(isTriggered) {
        if(!map) return;
        const mapContainer = document.getElementById('sos-map');
        if(isTriggered) {
            mapContainer.style.boxShadow = "0 0 20px rgba(255, 0, 0, 0.8)";
            if(userMarker) {
                userMarker.getPopup().setContent("🚨 EMERGENCY SOS 🚨").openOn(map);
            }
        } else {
            mapContainer.style.boxShadow = "none";
            if(userMarker) {
                userMarker.getPopup().setContent("Driver's Live Location");
            }
        }
    }

    async function loadBlackBoxGallery() {
        const gallery = document.getElementById('black-box-gallery');
        if(!gallery) return;
        
        try {
            const res = await fetch('/event_logs');
            const data = await res.json();
            
            if(!data.snapshots || data.snapshots.length === 0) {
                gallery.innerHTML = '<p class="text-muted text-center" style="grid-column: 1 / -1; margin-top: 2rem;">No recent events recorded.</p>';
                return;
            }
            
            gallery.innerHTML = ''; // clear
            data.snapshots.forEach(filename => {
                const div = document.createElement('div');
                div.className = 'gallery-item';
                div.style.background = 'rgba(0,0,0,0.5)';
                div.style.borderRadius = '8px';
                div.style.overflow = 'hidden';
                div.style.border = '1px solid var(--glass-border)';
                
                const isAnger = filename.startsWith('anger');
                const badgeColor = isAnger ? 'var(--danger)' : '#fbbf24';
                const labelText = isAnger ? 'ANGER' : 'DROWSY';
                
                div.innerHTML = `
                    <div style="position: relative;">
                        <img src="/event_log/${filename}" style="width: 100%; display: block;" alt="${filename}">
                        <div style="position: absolute; top: 5px; left: 5px; background: rgba(0,0,0,0.7); padding: 2px 6px; border-radius: 4px; border: 1px solid ${badgeColor}; font-size: 0.6rem; color: ${badgeColor}; font-weight: bold;">${labelText}</div>
                    </div>
                    <div style="padding: 8px; font-size: 0.75rem; color: var(--text-muted); text-align: center; border-top: 1px solid rgba(255,255,255,0.05);">${filename}</div>
                `;
                gallery.appendChild(div);
            });
            
        } catch (e) {
            console.error("Failed to load block box events:", e);
        }
    }

    // Call Initialization functions
    initChart();
    initMap();
    loadBlackBoxGallery();
    
    // Wire up refresh logs button
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');
    if (refreshLogsBtn) {
        refreshLogsBtn.addEventListener('click', loadBlackBoxGallery);
    }

    // --- Sliders Logic ---
    async function updateThresholds(data) {
        try {
            await fetch('/update_thresholds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } catch (e) {
            console.error("Failed to update thresholds:", e);
        }
    }

    earSlider.addEventListener('change', (e) => {
        earVal.innerText = e.target.value;
        updateThresholds({ ear_thresh: e.target.value });
    });

    marSlider.addEventListener('change', (e) => {
        marVal.innerText = e.target.value;
        updateThresholds({ mar_thresh: e.target.value });
    });

    sosPhoneInput.addEventListener('change', (e) => {
        updateThresholds({ emergency_contact: e.target.value.trim() });
    });

    const reconnectBtn = document.getElementById('reconnect-btn');
    reconnectBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        reconnectBtn.innerText = "Connecting...";
        try {
            const res = await fetch('/reconnect_arduino', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                reconnectBtn.innerText = "Connected!";
                setTimeout(() => { reconnectBtn.innerText = "Reconnect"; }, 2000);
            } else {
                reconnectBtn.innerText = "Failed";
                setTimeout(() => { reconnectBtn.innerText = "Reconnect"; }, 2000);
            }
        } catch (err) {
            reconnectBtn.innerText = "Error";
            setTimeout(() => { reconnectBtn.innerText = "Reconnect"; }, 2000);
        }
    });

    // --- Polling Backend ---
    async function pollStatus() {
        if (!isMonitoring) return;

        try {
            // Update Status & Chart
            const res = await fetch('/status');
            const data = await res.json();

            if (data.is_monitoring) {
                camDot.classList.add('ok');
                ardDot.classList.toggle('ok', data.arduino_connected);

                // Update Analytics Widgets
                scoreVal.innerText = data.safety_score;
                earGaugeVal.innerText = data.ear.toFixed(2);
                
                // Update Line Chart
                updateChart(data.ear, data.mar);

                // Update Emotion Display
                if (data.emotion) {
                    emotionVal.innerText = data.emotion;
                    emotionScoreEl.innerText = data.emotion_score;
                }

                if (data.safety_score < 80) {
                    scoreBox.classList.add('danger');
                } else {
                    scoreBox.classList.remove('danger');
                }

                // Update Stress Alert
                if (data.is_stressed) {
                    stressAlert.classList.remove('d-none');
                    if (!spokenStress) {
                        speakAlert("Warning: High stress level detected.");
                        spokenStress = true;
                    }
                } else {
                    stressAlert.classList.add('d-none');
                    spokenStress = false;
                }

                // Update SOS Alert
                if (data.sos_triggered) {
                    sosAlert.classList.remove('d-none');
                    setSOSMapAlert(true);
                    if (!spokenSos) {
                        speakAlert("SOS triggered. Emergency contacts notified.");
                        spokenSos = true;
                    }
                } else {
                    sosAlert.classList.add('d-none');
                    setSOSMapAlert(false);
                    spokenSos = false;
                }

                // Drowsy Audio Alert
                if (data.drowsy_alarm_active) {
                    if (!spokenDrowsy) {
                        speakAlert("Please pull over and take a rest.");
                        spokenDrowsy = true;
                    }
                } else {
                    spokenDrowsy = false;
                }

                // Initialize Input Value Once if empty
                if (data.emergency_contact && !sosPhoneInput.value && document.activeElement !== sosPhoneInput) {
                    sosPhoneInput.value = data.emergency_contact;
                }
            }

            // Update Logs
            const logRes = await fetch('/logs');
            const logData = await logRes.json();

            // Rebuild log list natively
            logList.innerHTML = '';
            logData.logs.slice().reverse().forEach(log => {
                const li = document.createElement('li');
                li.className = `log-item ${log.level || 'info'}`;
                li.innerText = `${log.time} ${log.msg}`;
                logList.appendChild(li);
            });

        } catch (e) {
            console.error("Polling Error:", e);
            camDot.classList.remove('ok');
            ardDot.classList.remove('ok');
        }
    }

    async function toggleBackend(command) {
        try {
            const response = await fetch(`/${command}`, { method: 'POST' });
            const data = await response.json();
            console.log(`Backend ${command}:`, data);
            if (!response.ok) {
                alert(data.message || `Unable to ${command} monitoring.`);
                return false;
            }
            return true;
        } catch (error) {
            console.error(`Error toggling backend ${command}:`, error);
            alert("Connection Error: Is detector.py running in your terminal?");
            return false;
        }
    }

    async function startMonitoringUI() {
        const success = await toggleBackend('start');
        if (!success) {
            isMonitoring = false;
            startBtn.classList.remove('d-none');
            stopBtn.classList.add('d-none');
            return;
        }

        statusText.innerText = "Initializing Vision Engine...";
        statusDot.classList.add('active-dot');
        panel.classList.add('active');
        
        // Reset safety score in UI immediately
        const scoreVal = document.getElementById('score-val');
        const scoreBox = document.querySelector('.score-box');
        if (scoreVal) scoreVal.innerText = "100";
        if (scoreBox) scoreBox.classList.remove('danger');

        // Let the backend start up the camera
        setTimeout(() => {
            statusText.innerText = "System Active | Live EAR Tracking";
            // Replace placeholder with the live video feed from Flask
            videoPlaceholder.innerHTML = `
                <div class="scan-line"></div>
                <img src="/video_feed" class="live-stream" alt="Live Driver Feed" />
                <div class="overlay-data">
                    <span class="badge">LIVE</span>
                    <span class="badge">DRIVING MONITORING</span>
                </div>
            `;

            // Start Polling data
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(pollStatus, 500);

        }, 1000);
    }

    async function stopMonitoringUI() {
        await toggleBackend('stop');
        statusText.innerText = "System Ready";
        statusDot.classList.remove('active-dot');
        panel.classList.remove('active');

        // Revert to placeholder
        videoPlaceholder.innerHTML = `
            <div class="scan-line"></div>
            <div class="placeholder-content">
                <span class="icon">📷</span>
                <p>Camera feed will appear here</p>
            </div>
        `;

        if (pollInterval) clearInterval(pollInterval);
        camDot.classList.remove('ok');
        ardDot.classList.remove('ok');
    }

    startBtn.addEventListener('click', () => {
        if (!isMonitoring) {
            isMonitoring = true;
            startBtn.classList.add('d-none');
            stopBtn.classList.remove('d-none');
            startMonitoringUI();
        }
    });

    stopBtn.addEventListener('click', () => {
        if (isMonitoring) {
            isMonitoring = false;
            stopBtn.classList.add('d-none');
            startBtn.classList.remove('d-none');
            stopMonitoringUI();
        }
    });

    // Glass card mouse-move effect
    document.querySelectorAll('.glass').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });
});
