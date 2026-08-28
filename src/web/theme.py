"""
Custom dark theme for the Douyin Translation Pipeline UI.

Premium SaaS-grade glassmorphism design with smooth transitions,
gradient accents, and micro-animations.

Color system:
- Background:  #0a0a12 (page), #12121e (surface), #1a1a2e (card/input), #222238 (elevated)
- Primary:     linear-gradient(135deg, #6366f1, #8b5cf6)
- Accent:      #22d3ee (cyan-400, progress/active)
- Success:     #10b981 (emerald-500)
- Warning:     #f59e0b (amber-500)
- Error:       #ef4444 (red-500)
- Text:        #e2e8f0 / #94a3b8 / #64748b
- Glass:       rgba(18, 18, 30, 0.8) + backdrop-blur(12px)
"""

CUSTOM_CSS = """
/* ══════════════════════════════════════════════════════════════════════
   IMPORTS & FONTS
   ══════════════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ══════════════════════════════════════════════════════════════════════
   ROOT VARIABLES
   ══════════════════════════════════════════════════════════════════════ */
:root {
    --bg-page: #0a0a12;
    --bg-surface: #0f0f1a;
    --bg-card: #12121e;
    --bg-elevated: #1a1a2e;
    --bg-input: #1a1a2e;
    --bg-hover: #222238;

    --glass-bg: rgba(18, 18, 30, 0.8);
    --glass-border: rgba(255, 255, 255, 0.06);
    --glass-border-hover: rgba(99, 102, 241, 0.3);
    --glass-glow: rgba(99, 102, 241, 0.1);

    --primary: #6366f1;
    --primary-light: #818cf8;
    --primary-dark: #4f46e5;
    --primary-gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
    --primary-muted: rgba(99, 102, 241, 0.15);
    --primary-glow: rgba(99, 102, 241, 0.4);

    --accent: #22d3ee;
    --accent-light: #67e8f9;
    --accent-muted: rgba(34, 211, 238, 0.12);
    --accent-glow: rgba(34, 211, 238, 0.3);

    --success: #10b981;
    --success-light: #34d399;
    --success-muted: rgba(16, 185, 129, 0.12);
    --warning: #f59e0b;
    --warning-muted: rgba(245, 158, 11, 0.12);
    --error: #ef4444;
    --error-light: #f87171;
    --error-muted: rgba(239, 68, 68, 0.12);

    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --text-faint: #475569;

    --border: rgba(255, 255, 255, 0.06);
    --border-subtle: rgba(255, 255, 255, 0.03);
    --border-hover: rgba(255, 255, 255, 0.12);
    --border-active: rgba(99, 102, 241, 0.5);

    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-pill: 9999px;

    --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2);
    --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
    --shadow-glow-primary: 0 0 24px rgba(99, 102, 241, 0.25);
    --shadow-glow-accent: 0 0 20px rgba(34, 211, 238, 0.2);
    --shadow-glow-success: 0 0 20px rgba(16, 185, 129, 0.2);

    --font-sans: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;

    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition: 250ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-slow: 400ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-spring: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ══════════════════════════════════════════════════════════════════════
   KEYFRAME ANIMATIONS
   ══════════════════════════════════════════════════════════════════════ */
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.3); }
    50% { box-shadow: 0 0 16px 4px rgba(34, 211, 238, 0.15); }
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.85); }
}

@keyframes spin-slow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes slide-in-right {
    from { opacity: 0; transform: translateX(12px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes slide-in-up {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes progress-stripe {
    0% { background-position: 0 0; }
    100% { background-position: 40px 0; }
}

@keyframes check-pop {
    0% { transform: scale(0); opacity: 0; }
    50% { transform: scale(1.2); }
    100% { transform: scale(1); opacity: 1; }
}

@keyframes border-glow-cycle {
    0%, 100% { border-color: rgba(34, 211, 238, 0.3); }
    50% { border-color: rgba(34, 211, 238, 0.6); }
}

@keyframes float-subtle {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-3px); }
}

@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* ══════════════════════════════════════════════════════════════════════
   GLOBAL OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
* {
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.08) transparent;
}

.gradio-container {
    background: var(--bg-page) !important;
    font-family: var(--font-sans) !important;
    max-width: 100% !important;
    padding: 0 !important;
    min-height: 100vh;
}

.dark {
    --background-fill-primary: var(--bg-surface) !important;
    --background-fill-secondary: var(--bg-card) !important;
    --border-color-primary: var(--border) !important;
}

/* Smooth transitions on everything inside Gradio */
.gradio-container *:not(.no-transition) {
    transition-property: background-color, border-color, color, box-shadow, opacity, transform;
    transition-duration: 250ms;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}

/* ══════════════════════════════════════════════════════════════════════
   APP HEADER - Glassmorphism sticky bar
   ══════════════════════════════════════════════════════════════════════ */
.app-header {
    background: rgba(10, 10, 18, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 1000;
}

.app-header h1 {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    letter-spacing: -0.02em;
}

.app-header .logo-icon {
    width: 34px;
    height: 34px;
    background: var(--primary-gradient);
    border-radius: var(--radius-sm);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    color: white;
    box-shadow: var(--shadow-glow-primary);
    animation: float-subtle 3s ease-in-out infinite;
}

.app-header .header-brand-text {
    background: linear-gradient(135deg, #e2e8f0, #94a3b8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.app-header .status-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 500;
    color: var(--success-light);
    background: var(--success-muted);
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    border: 1px solid rgba(16, 185, 129, 0.2);
}

.app-header .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
    animation: pulse-dot 2s ease-in-out infinite;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.app-header .version-tag {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg-elevated);
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border);
    margin-left: 4px;
    letter-spacing: 0.5px;
}

/* ══════════════════════════════════════════════════════════════════════
   TAB NAVIGATION - Pill-style tabs with gradient active indicator
   ══════════════════════════════════════════════════════════════════════ */
.tabs > .tab-nav {
    background: var(--bg-surface) !important;
    border-bottom: 1px solid var(--border) !important;
    padding: 8px 24px 0 !important;
    gap: 4px !important;
    display: flex !important;
}

.tabs > .tab-nav > button {
    background: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 20px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    position: relative !important;
    transition: all var(--transition) !important;
}

.tabs > .tab-nav > button:hover {
    color: var(--text-secondary) !important;
    background: rgba(255, 255, 255, 0.03) !important;
}

.tabs > .tab-nav > button.selected {
    color: white !important;
    background: rgba(99, 102, 241, 0.08) !important;
    border-bottom-color: transparent !important;
    font-weight: 600 !important;
}

/* Gradient underline for active tab */
.tabs > .tab-nav > button.selected::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 8px;
    right: 8px;
    height: 2px;
    background: var(--primary-gradient);
    border-radius: 2px 2px 0 0;
}

/* Tab content area */
.tabs > .tabitem {
    padding: 24px !important;
    animation: fade-in 0.3s ease;
}

/* ══════════════════════════════════════════════════════════════════════
   GLASS CARD - Shared glassmorphism panel
   ══════════════════════════════════════════════════════════════════════ */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 24px;
    transition: all var(--transition);
}

.glass-card:hover {
    border-color: var(--glass-border-hover);
    box-shadow: 0 8px 32px var(--glass-glow);
    transform: translateY(-2px);
}

/* Non-hoverable glass card variant */
.glass-card-static {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 24px;
}

/* Panel used inside tabs */
.panel {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-bottom: 16px;
    transition: all var(--transition);
}

.panel:hover {
    border-color: rgba(255, 255, 255, 0.08);
}

.panel-header {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
    letter-spacing: -0.01em;
}

.panel-header .panel-icon {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}

.panel-header .panel-icon.primary {
    background: var(--primary-muted);
    color: var(--primary-light);
}

.panel-header .panel-icon.accent {
    background: var(--accent-muted);
    color: var(--accent);
}

.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--border), transparent);
}

/* ══════════════════════════════════════════════════════════════════════
   FORM ELEMENTS - Elevated inputs with glow focus
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container textarea,
.gradio-container input[type="text"],
.gradio-container input[type="number"],
.gradio-container input[type="password"] {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-sans) !important;
    padding: 12px 16px !important;
    font-size: 14px !important;
    transition: all var(--transition) !important;
}

.gradio-container textarea:hover,
.gradio-container input[type="text"]:hover,
.gradio-container input[type="number"]:hover {
    border-color: var(--border-hover) !important;
}

.gradio-container textarea:focus,
.gradio-container input[type="text"]:focus,
.gradio-container input[type="number"]:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-muted), var(--shadow-glow-primary) !important;
    outline: none !important;
}

/* Label styling */
.gradio-container label span {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}

/* Info text */
.gradio-container .info {
    color: var(--text-muted) !important;
    font-size: 12px !important;
}

/* ══════════════════════════════════════════════════════════════════════
   BUTTONS - Gradient primary with glow, glass secondary
   ══════════════════════════════════════════════════════════════════════ */
/* Primary button - gradient with glow */
.gradio-container .primary,
.primary-btn,
button.primary {
    background: var(--primary-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-md) !important;
    padding: 11px 28px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: -0.01em !important;
    transition: all var(--transition) !important;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3) !important;
    position: relative !important;
    overflow: hidden !important;
}

.gradio-container .primary:hover,
.primary-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px var(--primary-glow), 0 0 40px rgba(99, 102, 241, 0.15) !important;
}

.gradio-container .primary:active,
.primary-btn:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 8px rgba(99, 102, 241, 0.3) !important;
}

/* Gradient shimmer on hover */
.gradio-container .primary::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: -100% !important;
    width: 100% !important;
    height: 100% !important;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent) !important;
    transition: left 0.5s ease !important;
}
.gradio-container .primary:hover::before {
    left: 100% !important;
}

/* Secondary button - glass style */
.gradio-container .secondary,
.secondary-btn {
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    transition: all var(--transition) !important;
}

.gradio-container .secondary:hover,
.secondary-btn:hover {
    background: var(--bg-hover) !important;
    border-color: var(--border-hover) !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* Big action button (Tab 1 submit) */
.btn-action-lg {
    font-size: 15px !important;
    padding: 14px 32px !important;
    border-radius: var(--radius-lg) !important;
    letter-spacing: 0 !important;
    min-height: 48px !important;
}

/* ══════════════════════════════════════════════════════════════════════
   PROGRESS TRACKER - Step cards with status icons and animations
   ══════════════════════════════════════════════════════════════════════ */
.pipeline-progress {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px 0;
}

.step-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    transition: all var(--transition);
    animation: slide-in-up 0.3s ease backwards;
    border: 1px solid transparent;
}

.step-row:nth-child(1) { animation-delay: 0ms; }
.step-row:nth-child(2) { animation-delay: 30ms; }
.step-row:nth-child(3) { animation-delay: 60ms; }
.step-row:nth-child(4) { animation-delay: 90ms; }
.step-row:nth-child(5) { animation-delay: 120ms; }
.step-row:nth-child(6) { animation-delay: 150ms; }
.step-row:nth-child(7) { animation-delay: 180ms; }
.step-row:nth-child(8) { animation-delay: 210ms; }
.step-row:nth-child(9) { animation-delay: 240ms; }
.step-row:nth-child(10) { animation-delay: 270ms; }
.step-row:nth-child(11) { animation-delay: 300ms; }

.step-row:hover {
    background: rgba(255, 255, 255, 0.02);
}

.step-row.step-running {
    background: rgba(34, 211, 238, 0.04);
    border-color: rgba(34, 211, 238, 0.15);
    animation: border-glow-cycle 2s ease-in-out infinite, slide-in-up 0.3s ease backwards;
}

.step-row.step-completed {
    background: rgba(16, 185, 129, 0.03);
}

.step-row.step-failed {
    background: rgba(239, 68, 68, 0.04);
    border-color: rgba(239, 68, 68, 0.15);
}

/* Step icon circles */
.step-icon {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    flex-shrink: 0;
    transition: all var(--transition);
}

.step-icon.queued {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-faint);
    border: 1.5px dashed rgba(255, 255, 255, 0.1);
}

.step-icon.running {
    background: var(--accent-muted);
    color: var(--accent);
    border: 1.5px solid rgba(34, 211, 238, 0.4);
    animation: pulse-glow 2s ease-in-out infinite;
}

.step-icon.running .spin-icon {
    display: inline-block;
    animation: spin-slow 1.5s linear infinite;
}

.step-icon.completed {
    background: var(--success-muted);
    color: var(--success);
    border: 1.5px solid rgba(16, 185, 129, 0.3);
    animation: check-pop 0.4s ease;
}

.step-icon.failed {
    background: var(--error-muted);
    color: var(--error);
    border: 1.5px solid rgba(239, 68, 68, 0.3);
}

/* Step labels */
.step-label {
    flex: 1;
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 400;
}

.step-label.running {
    color: var(--accent);
    font-weight: 600;
}

.step-label.completed {
    color: var(--success);
    font-weight: 500;
}

.step-label.failed {
    color: var(--error-light);
    font-weight: 500;
}

/* Step status message */
.step-status {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    letter-spacing: 0.02em;
}

/* Step elapsed time */
.step-time {
    font-size: 11px;
    color: var(--text-faint);
    font-family: var(--font-mono);
    min-width: 44px;
    text-align: right;
}

/* ══════════════════════════════════════════════════════════════════════
   CIRCULAR PROGRESS INDICATOR
   ══════════════════════════════════════════════════════════════════════ */
.circular-progress {
    position: relative;
    width: 80px;
    height: 80px;
    margin: 0 auto 16px;
}

.circular-progress svg {
    transform: rotate(-90deg);
    width: 80px;
    height: 80px;
}

.circular-progress .track {
    fill: none;
    stroke: rgba(255, 255, 255, 0.05);
    stroke-width: 6;
}

.circular-progress .fill {
    fill: none;
    stroke: url(#progressGradient);
    stroke-width: 6;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.circular-progress .percentage {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-mono);
}

/* ══════════════════════════════════════════════════════════════════════
   PROGRESS BARS - Animated gradient fill with stripes
   ══════════════════════════════════════════════════════════════════════ */
.progress-bar-track {
    height: 6px;
    background: rgba(255, 255, 255, 0.04);
    border-radius: var(--radius-pill);
    overflow: hidden;
    margin-top: 12px;
}

.progress-bar-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
}

.progress-bar-fill.running {
    background: linear-gradient(90deg, var(--primary), var(--accent));
    background-size: 200% 100%;
    animation: gradient-shift 2s ease infinite;
}

.progress-bar-fill.running::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: repeating-linear-gradient(
        -45deg,
        transparent,
        transparent 8px,
        rgba(255, 255, 255, 0.08) 8px,
        rgba(255, 255, 255, 0.08) 16px
    );
    animation: progress-stripe 1s linear infinite;
}

.progress-bar-fill.completed {
    background: linear-gradient(90deg, var(--success), #34d399);
}

.progress-bar-fill.failed {
    background: linear-gradient(90deg, var(--error), #f87171);
}

.progress-bar-fill.queued {
    background: rgba(255, 255, 255, 0.08);
}

/* ══════════════════════════════════════════════════════════════════════
   JOB CARDS (DASHBOARD) - Glass cards with left accent border
   ══════════════════════════════════════════════════════════════════════ */
.job-card {
    background: var(--glass-bg);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: all var(--transition);
    cursor: pointer;
    animation: slide-in-up 0.35s ease backwards;
    position: relative;
    overflow: hidden;
}

.job-card::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 0 3px 3px 0;
    transition: all var(--transition);
}

.job-card:hover {
    border-color: var(--glass-border-hover);
    box-shadow: 0 8px 32px var(--glass-glow);
    transform: translateY(-2px);
}

.job-card.running::before {
    background: linear-gradient(180deg, var(--accent), var(--primary));
    box-shadow: 0 0 12px var(--accent-glow);
}

.job-card.completed::before {
    background: var(--success);
    box-shadow: 0 0 8px var(--shadow-glow-success);
}

.job-card.failed::before {
    background: var(--error);
}

.job-card.queued::before {
    background: var(--text-faint);
}

.job-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.job-card-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}

/* Status badges / pills */
.job-card-badge {
    font-size: 11px;
    padding: 4px 12px;
    border-radius: var(--radius-pill);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.job-card-badge .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
}

.badge-running {
    background: var(--accent-muted);
    color: var(--accent);
    border: 1px solid rgba(34, 211, 238, 0.2);
}
.badge-running .badge-dot {
    background: var(--accent);
    animation: pulse-dot 1.5s ease-in-out infinite;
}

.badge-completed {
    background: var(--success-muted);
    color: var(--success);
    border: 1px solid rgba(16, 185, 129, 0.2);
}
.badge-completed .badge-dot {
    background: var(--success);
}

.badge-failed {
    background: var(--error-muted);
    color: var(--error);
    border: 1px solid rgba(239, 68, 68, 0.2);
}
.badge-failed .badge-dot {
    background: var(--error);
}

.badge-queued {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    border: 1px solid var(--border);
}
.badge-queued .badge-dot {
    background: var(--text-muted);
}

/* ══════════════════════════════════════════════════════════════════════
   STATS ROW - Dashboard stat cards with icon backgrounds
   ══════════════════════════════════════════════════════════════════════ */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 24px;
}

.stat-card {
    background: var(--glass-bg);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 20px;
    position: relative;
    overflow: hidden;
    transition: all var(--transition);
}

.stat-card:hover {
    border-color: var(--glass-border-hover);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.stat-card .stat-bg-icon {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 40px;
    opacity: 0.06;
    pointer-events: none;
}

.stat-value {
    font-size: 30px;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.1;
    letter-spacing: -0.03em;
    font-feature-settings: 'tnum';
}

.stat-label {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 500;
}

.stat-card.accent .stat-value {
    background: linear-gradient(135deg, var(--accent), var(--primary-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.stat-card.success .stat-value {
    color: var(--success);
}

.stat-card.warning .stat-value {
    color: var(--warning);
}

.stat-card.error .stat-value {
    color: var(--error);
}

/* ══════════════════════════════════════════════════════════════════════
   SRT EDITOR - Mono-spaced with syntax highlight feel
   ══════════════════════════════════════════════════════════════════════ */
.srt-editor-container textarea {
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
    line-height: 1.7 !important;
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    padding: 16px !important;
    color: var(--text-primary) !important;
}

.srt-editor-container textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-muted) !important;
}

/* SRT table display */
.srt-row {
    display: grid;
    grid-template-columns: 50px 130px 1fr 1fr;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
    align-items: center;
    font-size: 13px;
    transition: background var(--transition);
}

.srt-row:hover {
    background: rgba(255, 255, 255, 0.02);
}

.srt-index {
    color: var(--text-faint);
    font-family: var(--font-mono);
    font-size: 11px;
    text-align: center;
    opacity: 0.7;
}

.srt-time {
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 500;
}

.srt-original {
    color: var(--text-muted);
    font-size: 13px;
}

.srt-translated {
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 500;
}

/* ══════════════════════════════════════════════════════════════════════
   VIDEO PREVIEW
   ══════════════════════════════════════════════════════════════════════ */
.video-preview-container {
    display: flex;
    gap: 20px;
    align-items: flex-start;
}

.video-preview-container video {
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    background: #000;
    max-height: 480px;
    box-shadow: var(--shadow-lg);
}

/* Video card overlay */
.video-card {
    position: relative;
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: #0a0a12;
    border: 1px solid var(--border);
}

.video-card .play-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.4);
    opacity: 0;
    transition: opacity var(--transition);
    cursor: pointer;
}

.video-card:hover .play-overlay {
    opacity: 1;
}

.play-overlay .play-btn-circle {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: white;
    transition: all var(--transition);
}

.play-overlay .play-btn-circle:hover {
    background: rgba(255, 255, 255, 0.25);
    transform: scale(1.1);
}

/* ══════════════════════════════════════════════════════════════════════
   LANGUAGE PILLS - Selectable chips
   ══════════════════════════════════════════════════════════════════════ */
.lang-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.lang-pill {
    padding: 7px 18px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.02);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition);
    user-select: none;
}

.lang-pill:hover {
    border-color: var(--primary);
    color: var(--text-primary);
    background: var(--primary-muted);
    transform: translateY(-1px);
}

.lang-pill.selected {
    background: var(--primary-muted);
    border-color: var(--primary);
    color: var(--primary-light);
    font-weight: 600;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
}

/* ══════════════════════════════════════════════════════════════════════
   TTS VOICE CARDS
   ══════════════════════════════════════════════════════════════════════ */
.voice-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: all var(--transition);
    cursor: pointer;
}

.voice-card:hover {
    border-color: var(--glass-border-hover);
    box-shadow: 0 4px 16px var(--glass-glow);
    transform: translateY(-1px);
}

.voice-card.active {
    border-color: var(--primary);
    background: var(--primary-muted);
}

.voice-card .voice-icon {
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
    background: var(--primary-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.voice-card .voice-info {
    flex: 1;
}

.voice-card .voice-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.voice-card .voice-desc {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* Waveform animation for playing audio */
.waveform {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 20px;
}

.waveform .bar {
    width: 3px;
    border-radius: 2px;
    background: var(--accent);
    animation: wave-bar 0.8s ease-in-out infinite;
}

.waveform .bar:nth-child(1) { animation-delay: 0ms; height: 40%; }
.waveform .bar:nth-child(2) { animation-delay: 100ms; height: 70%; }
.waveform .bar:nth-child(3) { animation-delay: 200ms; height: 50%; }
.waveform .bar:nth-child(4) { animation-delay: 300ms; height: 90%; }
.waveform .bar:nth-child(5) { animation-delay: 400ms; height: 60%; }

@keyframes wave-bar {
    0%, 100% { transform: scaleY(0.4); }
    50% { transform: scaleY(1); }
}

/* Segmented control for TTS provider */
.segmented-control {
    display: inline-flex;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 3px;
    gap: 2px;
}

.segmented-control .seg-option {
    padding: 8px 20px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--transition);
    border: none;
    background: transparent;
}

.segmented-control .seg-option:hover {
    color: var(--text-secondary);
}

.segmented-control .seg-option.active {
    background: var(--primary-gradient);
    color: white;
    box-shadow: var(--shadow-sm);
}

/* ══════════════════════════════════════════════════════════════════════
   SETTINGS - Accordion & form styles
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container .accordion {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-lg) !important;
    overflow: hidden !important;
    margin-bottom: 12px !important;
    transition: all var(--transition) !important;
}

.gradio-container .accordion:hover {
    border-color: rgba(255, 255, 255, 0.08) !important;
}

/* Accordion header */
.gradio-container .accordion > .label-wrap {
    padding: 16px 20px !important;
    transition: all var(--transition) !important;
}

.gradio-container .accordion > .label-wrap:hover {
    background: rgba(255, 255, 255, 0.02) !important;
}

.gradio-container .accordion > .label-wrap span {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.01em !important;
}

/* Caption preview in settings */
.caption-preview-box {
    background: #000;
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    padding: 24px;
    min-height: 160px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    position: relative;
    overflow: hidden;
    margin-top: 12px;
}

.caption-preview-box::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.6));
    pointer-events: none;
}

.caption-preview-box .preview-label {
    position: absolute;
    top: 10px;
    right: 14px;
    font-size: 10px;
    color: var(--text-faint);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Success save message */
.save-success {
    padding: 10px 16px;
    background: var(--success-muted);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: var(--radius-md);
    color: var(--success-light);
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
    animation: slide-in-up 0.3s ease;
}

.save-success .check-icon {
    animation: check-pop 0.4s ease;
}

/* ══════════════════════════════════════════════════════════════════════
   EMPTY STATES
   ══════════════════════════════════════════════════════════════════════ */
.empty-state {
    text-align: center;
    padding: 60px 24px;
    color: var(--text-muted);
    animation: fade-in 0.5s ease;
}

.empty-state .empty-icon {
    font-size: 56px;
    margin-bottom: 16px;
    opacity: 0.3;
    animation: float-subtle 3s ease-in-out infinite;
}

.empty-state .empty-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.empty-state .empty-desc {
    font-size: 13px;
    color: var(--text-muted);
    max-width: 320px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ══════════════════════════════════════════════════════════════════════
   DROPDOWN OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container .wrap {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
}

.gradio-container .wrap:hover {
    border-color: var(--border-hover) !important;
}

.gradio-container .wrap:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-muted) !important;
}

/* ══════════════════════════════════════════════════════════════════════
   SLIDER OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container input[type="range"] {
    accent-color: var(--primary) !important;
}

/* ══════════════════════════════════════════════════════════════════════
   CHECKBOX / RADIO OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container input[type="checkbox"],
.gradio-container input[type="radio"] {
    accent-color: var(--primary) !important;
}

/* ══════════════════════════════════════════════════════════════════════
   MARKDOWN OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container .prose {
    color: var(--text-primary) !important;
}

.gradio-container .prose h1,
.gradio-container .prose h2,
.gradio-container .prose h3 {
    color: var(--text-primary) !important;
    letter-spacing: -0.02em !important;
}

/* ══════════════════════════════════════════════════════════════════════
   SCROLLBAR (Webkit)
   ══════════════════════════════════════════════════════════════════════ */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.14);
}

/* ══════════════════════════════════════════════════════════════════════
   TOOLTIPS
   ══════════════════════════════════════════════════════════════════════ */
.tooltip {
    position: relative;
    display: inline-block;
}

.tooltip .tooltip-text {
    visibility: hidden;
    opacity: 0;
    background: var(--bg-elevated);
    color: var(--text-primary);
    font-size: 12px;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-md);
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%) translateY(4px);
    white-space: nowrap;
    z-index: 999;
    transition: all var(--transition-fast);
}

.tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}

/* ══════════════════════════════════════════════════════════════════════
   RESPONSIVE
   ══════════════════════════════════════════════════════════════════════ */
@media (max-width: 768px) {
    .app-header {
        padding: 10px 16px;
    }

    .app-header h1 {
        font-size: 15px;
    }

    .tabs > .tab-nav {
        padding: 4px 12px 0 !important;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }

    .tabs > .tab-nav > button {
        padding: 8px 14px !important;
        font-size: 12px !important;
        white-space: nowrap;
    }

    .tabs > .tabitem {
        padding: 16px !important;
    }

    .stats-row {
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
    }

    .srt-row {
        grid-template-columns: 1fr;
        gap: 4px;
    }

    .video-preview-container {
        flex-direction: column;
    }

    .stat-value {
        font-size: 24px;
    }
}

/* ══════════════════════════════════════════════════════════════════════
   LOADING SKELETON
   ══════════════════════════════════════════════════════════════════════ */
.skeleton {
    background: linear-gradient(90deg,
        rgba(255,255,255,0.04) 25%,
        rgba(255,255,255,0.08) 50%,
        rgba(255,255,255,0.04) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s ease infinite;
    border-radius: var(--radius-sm);
}

/* ══════════════════════════════════════════════════════════════════════
   GROUP / ROW / COLUMN OVERRIDES
   ══════════════════════════════════════════════════════════════════════ */
.gradio-container .gr-group {
    background: transparent !important;
    border: none !important;
}

/* Block elements within tabs should blend */
.gradio-container .block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Ensure tab content areas have proper padding */
.gradio-container .tabitem > div {
    padding: 0 !important;
}

/* Fix Gradio internal paddings */
.gradio-container .gr-padded {
    padding: 0 !important;
}

/* ══════════════════════════════════════════════════════════════════════
   PROVIDER INFO BOX
   ══════════════════════════════════════════════════════════════════════ */
.provider-info {
    font-size: 13px;
    color: var(--text-secondary);
    padding: 14px 16px;
    background: var(--bg-elevated);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    line-height: 1.6;
}

.provider-info b {
    color: var(--text-primary);
}

.provider-info .tag {
    display: inline-block;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-left: 6px;
}

.provider-info .tag.gpu {
    background: var(--warning-muted);
    color: var(--warning);
    border: 1px solid rgba(245, 158, 11, 0.2);
}

.provider-info .tag.free {
    background: var(--success-muted);
    color: var(--success);
    border: 1px solid rgba(16, 185, 129, 0.2);
}

/* ══════════════════════════════════════════════════════════════════════
   ERROR ALERT BOX
   ══════════════════════════════════════════════════════════════════════ */
.error-box {
    font-size: 12px;
    color: var(--error-light);
    padding: 10px 14px;
    background: var(--error-muted);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: var(--radius-md);
    margin-top: 8px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
    line-height: 1.5;
    animation: slide-in-up 0.3s ease;
}

.error-box .error-icon {
    flex-shrink: 0;
    margin-top: 1px;
}
"""
