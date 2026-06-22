# =============================================================================
# SENTIA ACADEMIC — Plataforma Institucional de Analítica y Prevención
# Archivo: app.py  |  Versión: 4.0.0 (Multi-Rol + Dashboard Institucional UNAL)
# Framework: Streamlit + pysentimiento (RoBERTuito, optimizado para español)
# Universidad Nacional de Colombia — Sede Bogotá
# =============================================================================
#
# NOVEDADES v4.0.0:
#   • Layout pantalla completa (wide) y tipografía escalada para máxima legibilidad.
#   • Multi-rol: diferenciación Estudiante / Psicólogo–Coordinador (admin_psico).
#   • Dashboard institucional para el psicólogo: gráfico temporal del IRE global
#     agregado de forma anónima por semana, con picos de parciales y finales.
#   • KPIs globales del psicólogo: IRE promedio de la comunidad, emoción negativa
#     más recurrente, total de evaluaciones y estudiantes activos.
#   • Historial de estudiante + botón de exportación a CSV.
#   • Canales reales de Bienestar Universitario UNAL (Sede Bogotá) en todas las
#     alertas de riesgo medio y alto.
#   • Orientación personalizada ampliada: 6–8 tarjetas de recomendación que
#     cruzan el Nivel de Riesgo con la Emoción Dominante (Miedo/Ansiedad,
#     Tristeza, Ira/Frustración).
#
# CREDENCIALES ADMIN PRE-REGISTRADAS:
#   Usuario:    admin_psico
#   Contraseña: Psico@UNAL2024
#   (Cambia la contraseña en ADMIN_PASSWORD_INIT antes de desplegar en producción)
#
# INSTALACIÓN:
#   pip install -r requirements.txt
# EJECUCIÓN LOCAL:
#   streamlit run app.py
# =============================================================================

import hashlib
import random
import sqlite3
import statistics
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# ==============================================================================
# INICIALIZACIÓN DEL ESTADO DE SESIÓN  (antes de set_page_config)
# ==============================================================================

st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("user_id", None)
st.session_state.setdefault("username", None)

# ==============================================================================
# CONFIGURACIÓN GLOBAL DE LA PÁGINA
# ==============================================================================

st.set_page_config(
    page_title="Sentia Academic · UNAL",
    page_icon="◈",
    layout="wide",                  # ← Requerimiento 1: pantalla completa
    initial_sidebar_state="expanded" if st.session_state.logged_in else "collapsed",
)

# ==============================================================================
# CONSTANTES DEL SISTEMA
# ==============================================================================

# ── Base de datos ──────────────────────────────────────────────────────────────
DB_PATH: str = "sentia.db"

# ── Credenciales del administrador (psicólogo / coordinador de bienestar) ─────
ADMIN_USERNAME: str       = "admin_psico"
ADMIN_PASSWORD_INIT: str  = "Psico@UNAL2024"   # Cambiar antes de producción

# ── Opciones de navegación ─────────────────────────────────────────────────────
OPCION_EVALUACION: str = "📝 Nueva Evaluación"
OPCION_HISTORIAL:  str = "📊 Historial y Tendencias"
OPCION_DASHBOARD:  str = "🏛️ Dashboard Institucional"

# ── Umbrales del Índice de Riesgo Emocional (IRE) ─────────────────────────────
IRE_BAJO_MAX:  int = 39   # 0 – 39  → Riesgo Bajo
IRE_MEDIO_MAX: int = 69   # 40 – 69 → Riesgo Medio
                           # > 69    → Riesgo Alto

# ── Pesos del algoritmo de combinación ────────────────────────────────────────
PESO_SENTIMIENTO: float = 0.60
PESO_EMOCION:     float = 0.40

# ── Pesos internos de emociones de riesgo ─────────────────────────────────────
PESO_TRISTEZA: float = 0.45
PESO_MIEDO:    float = 0.35
PESO_IRA:      float = 0.20

# ── Amplificación por co-ocurrencia ───────────────────────────────────────────
UMBRAL_AMPLIF_SENTIM: float = 0.60
UMBRAL_AMPLIF_EMOC:   float = 0.50
FACTOR_AMPLIF:        float = 1.15

# ── Factor protector de la alegría ────────────────────────────────────────────
PESO_FACTOR_PROTECTOR: float = 0.10

# ── Umbral de tendencia (historial) ───────────────────────────────────────────
UMBRAL_CAMBIO_TENDENCIA: float = 5.0

# ── Canales institucionales reales — Bienestar Universitario UNAL Bogotá ──────
# Requerimiento 5: contactos explícitos y realistas de la UNAL
RECURSOS_APOYO: Dict[str, Dict[str, str]] = {
    "Acompañamiento Integral · Bienestar UNAL": {
        "contacto": "acompanamiento_bog@unal.edu.co",
        "extra":    "Dirección de Bienestar Universitario · Ciudad Universitaria, Bogotá",
    },
    "Unidad de Salud · Bienestar UNAL Bogotá": {
        "contacto": "saludbienestar.bog@unal.edu.co",
        "extra":    "Área de Salud Bienestar Universitario · Edif. Uriel Gutiérrez",
    },
    "SISBienestar UNAL": {
        "contacto": "sisbienestar_bog@unal.edu.co",
        "extra":    "Sistema de Información de Bienestar · Apoyo integral al estudiante",
    },
    "Línea Nacional de Salud Mental": {
        "contacto": "106",
        "extra":    "Gratuita · 24 h · 7 días · Todo el territorio nacional",
    },
    "Línea de Crisis Emocional": {
        "contacto": "018000-112-999",
        "extra":    "Gratuita · 24 horas · Apoyo en crisis severa",
    },
}


# ==============================================================================
# SISTEMA DE DISEÑO — INYECCIÓN DE CSS GLOBAL (Sentia Design System v4)
# ==============================================================================

def _inyectar_css() -> None:
    """Inyecta el sistema de diseño corporativo de Sentia Academic v4.0.

    Cambios respecto a v3:
      • Layout wide: se elimina max-width del block-container.
      • Tipografía global escalada (+30 % en todos los tamaños) para lectura
        clara en pantallas grandes.
      • Padding amplio en tarjetas; texto nunca se corta ni desborda.
      • Nuevas clases para el Dashboard del Psicólogo: .sa-kpi-card,
        .sa-psico-badge, .sa-periodo-chip, .sa-dashboard-sep.
    """
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
              rel="stylesheet">

        <style>
        /* ═══════════════════════════════════════════════════════════════════
           TOKENS DE DISEÑO SENTIA v4
           ═══════════════════════════════════════════════════════════════════ */
        :root {
            --sa-blue-900:   #0F2444;
            --sa-blue-800:   #1E3A5F;
            --sa-blue-700:   #254D7E;
            --sa-blue-600:   #2B5C9A;
            --sa-blue-400:   #4A8AC4;
            --sa-blue-100:   #DBEAFE;
            --sa-blue-50:    #EFF6FF;
            --sa-slate-700:  #334155;
            --sa-slate-600:  #475569;
            --sa-slate-400:  #94A3B8;
            --sa-slate-200:  #E2E8F0;
            --sa-slate-100:  #F1F5F9;
            --sa-bg:         #F8FAFC;
            --sa-white:      #FFFFFF;
            --sa-emerald:    #059669;
            --sa-emerald-lt: #ECFDF5;
            --sa-amber:      #D97706;
            --sa-amber-lt:   #FFFBEB;
            --sa-crimson:    #B91C1C;
            --sa-crimson-lt: #FEF2F2;
            --sa-purple:     #6D28D9;
            --sa-purple-lt:  #F5F3FF;
            --sa-radius:     12px;
            --sa-radius-sm:  8px;
            --sa-shadow:     0 1px 4px rgba(15,36,68,.08);
            --sa-shadow-md:  0 4px 20px rgba(15,36,68,.13);
            --sa-text-strong: #1e293b;
        }

        /* ── TIPOGRAFÍA GLOBAL (escalada para wide layout) ─────────────── */
        html, body, [class*="css"] {
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
            font-size: 16px !important;
        }

        /* ── FONDO PRINCIPAL ────────────────────────────────────────────── */
        .stApp { background-color: var(--sa-bg) !important; }

        /* ── BLOCK CONTAINER — sin max-width, padding generoso ─────────── */
        .block-container {
            padding-top:    2.5rem !important;
            padding-bottom: 4rem   !important;
            padding-left:   3.5rem !important;
            padding-right:  3.5rem !important;
            max-width:      none   !important;
        }

        /* ── HEADINGS — fuentes grandes y claras ────────────────────────── */
        h1, h2, h3, h4 {
            font-family:    'Inter', sans-serif !important;
            color:          var(--sa-blue-900)  !important;
            letter-spacing: -0.02em            !important;
        }
        h1 { font-size: 2.3rem  !important; font-weight: 700 !important; }
        h2 { font-size: 1.65rem !important; font-weight: 600 !important; }
        h3 { font-size: 1.35rem !important; font-weight: 600 !important; }
        h4 { font-size: 1.1rem  !important; font-weight: 600 !important; }

        /* ── PÁRRAFOS ───────────────────────────────────────────────────── */
        p, li, span {
            color:       var(--sa-slate-600);
            line-height: 1.75;
            font-size:   1rem;
        }

        /* ── BOTÓN PRIMARIO ─────────────────────────────────────────────── */
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
            background:    var(--sa-blue-800) !important;
            color:         var(--sa-white)    !important;
            border:        none               !important;
            border-radius: var(--sa-radius)   !important;
            font-family:   'Inter', sans-serif !important;
            font-weight:   600                !important;
            font-size:     0.95rem            !important;
            letter-spacing: 0.01em           !important;
            padding:       0.65rem 1.6rem     !important;
            transition:    background .2s ease, box-shadow .2s ease !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            background: var(--sa-blue-600) !important;
            box-shadow: var(--sa-shadow-md) !important;
        }

        /* ── BOTÓN SECUNDARIO ───────────────────────────────────────────── */
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: var(--sa-radius) !important;
            font-family:   'Inter', sans-serif !important;
            font-weight:   600               !important;
            font-size:     0.9rem            !important;
            border:        1.5px solid var(--sa-slate-200) !important;
            color:         var(--sa-text-strong) !important;
        }

        /* ── BOTÓN DOWNLOAD ─────────────────────────────────────────────── */
        div[data-testid="stDownloadButton"] > button {
            background:    var(--sa-emerald)  !important;
            color:         var(--sa-white)    !important;
            border:        none               !important;
            border-radius: var(--sa-radius)   !important;
            font-family:   'Inter', sans-serif !important;
            font-weight:   600                !important;
            font-size:     0.95rem            !important;
            padding:       0.65rem 1.6rem     !important;
            transition:    background .2s ease, box-shadow .2s ease !important;
        }
        div[data-testid="stDownloadButton"] > button:hover {
            background: #047857 !important;
            box-shadow: var(--sa-shadow-md) !important;
        }

        /* ── TEXTAREA / INPUTS ──────────────────────────────────────────── */
        textarea, input {
            font-family:   'Inter', sans-serif !important;
            font-size:     0.98rem             !important;
            border:        1.5px solid var(--sa-slate-200) !important;
            border-radius: var(--sa-radius)    !important;
            background:    var(--sa-white)     !important;
            color:         var(--sa-blue-900)  !important;
            transition:    border-color .2s ease, box-shadow .2s ease !important;
        }
        textarea:focus, input:focus {
            border-color: var(--sa-blue-400) !important;
            box-shadow:   0 0 0 3px rgba(74,138,196,.15) !important;
        }

        /* ── EXPANDER ───────────────────────────────────────────────────── */
        details {
            border:        1px solid var(--sa-slate-200) !important;
            border-radius: var(--sa-radius)              !important;
            background:    var(--sa-white)               !important;
        }
        details summary {
            font-weight: 500           !important;
            color:       var(--sa-blue-800) !important;
            font-size:   0.95rem       !important;
        }

        /* ── DIVIDER ────────────────────────────────────────────────────── */
        hr {
            border-color: var(--sa-slate-200) !important;
            margin:       1.75rem 0           !important;
        }

        /* ── CAPTION ────────────────────────────────────────────────────── */
        [data-testid="stCaptionContainer"], .stCaption, small {
            color:     var(--sa-slate-400) !important;
            font-size: 0.82rem             !important;
        }

        /* ── SIDEBAR ────────────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            background:   var(--sa-white)         !important;
            border-right: 1px solid var(--sa-slate-200) !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top:   1.6rem !important;
            padding-left:  1.2rem !important;
            padding-right: 1.2rem !important;
        }
        section[data-testid="stSidebar"] label {
            font-size: 1.0rem              !important;
            color:     var(--sa-text-strong) !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            padding:       10px 12px !important;
            border-radius: 8px       !important;
            font-size:     0.95rem   !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background: var(--sa-slate-100) !important;
        }

        /* ── TABS ───────────────────────────────────────────────────────── */
        button[data-baseweb="tab"] {
            font-family: 'Inter', sans-serif !important;
            font-weight: 600                 !important;
            font-size:   0.95rem             !important;
            color:       var(--sa-slate-400) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--sa-blue-800) !important;
        }
        div[data-baseweb="tab-highlight"] {
            background-color: var(--sa-blue-800) !important;
        }

        /* ── FORMULARIOS ────────────────────────────────────────────────── */
        div[data-testid="stForm"] {
            background:    var(--sa-white)         !important;
            border:        1px solid var(--sa-slate-200) !important;
            border-radius: var(--sa-radius)        !important;
            box-shadow:    var(--sa-shadow)         !important;
            padding:       26px 28px 14px 28px     !important;
            box-sizing:    border-box               !important;
        }

        /* ══════════════════════════════════════════════════════════════════
           COMPONENTES SENTIA
           ══════════════════════════════════════════════════════════════════ */

        /* ── TARJETA MÉTRICA (estudiante) ───────────────────────────────── */
        .sa-metric-grid {
            display:   flex;
            flex-wrap: wrap;
            gap:       14px;
            margin:    1.2rem 0 1.5rem 0;
        }
        .sa-metric-card {
            background:    var(--sa-white);
            border:        1px solid var(--sa-slate-200);
            border-radius: var(--sa-radius);
            box-shadow:    var(--sa-shadow);
            padding:       22px 24px 20px 24px;
            flex:          1 1 180px;
            min-width:     165px;
            display:       flex;
            flex-direction: column;
            gap:           6px;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-metric-card--ire     { border-left: 4px solid var(--sa-blue-800); }
        .sa-metric-card--low     { border-left: 4px solid var(--sa-emerald);  }
        .sa-metric-card--medium  { border-left: 4px solid var(--sa-amber);    }
        .sa-metric-card--high    { border-left: 4px solid var(--sa-crimson);  }
        .sa-metric-card--neutral { border-left: 4px solid var(--sa-blue-400); }
        .sa-metric-card--purple  { border-left: 4px solid var(--sa-purple);   }

        .sa-metric-label {
            font-size:      0.74rem;
            font-weight:    600;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color:          var(--sa-slate-400);
            margin:         0;
        }
        .sa-metric-value {
            font-size:    2.0rem;
            font-weight:  700;
            color:        var(--sa-text-strong);
            margin:       0;
            line-height:  1.2;
            white-space:  normal;
            overflow-wrap: break-word;
            word-break:   break-word;
        }
        .sa-metric-sub {
            font-size: 0.78rem;
            color:     var(--sa-slate-400);
            margin:    0;
        }

        /* ── KPI CARD (psicólogo — más prominente) ──────────────────────── */
        .sa-kpi-grid {
            display:   flex;
            flex-wrap: wrap;
            gap:       16px;
            margin:    1.4rem 0 1.8rem 0;
        }
        .sa-kpi-card {
            background:    var(--sa-white);
            border:        1px solid var(--sa-slate-200);
            border-radius: var(--sa-radius);
            box-shadow:    var(--sa-shadow-md);
            padding:       28px 30px 24px 30px;
            flex:          1 1 200px;
            min-width:     180px;
            display:       flex;
            flex-direction: column;
            gap:           8px;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-kpi-card--blue   { border-top: 5px solid var(--sa-blue-800); }
        .sa-kpi-card--green  { border-top: 5px solid var(--sa-emerald);  }
        .sa-kpi-card--amber  { border-top: 5px solid var(--sa-amber);    }
        .sa-kpi-card--purple { border-top: 5px solid var(--sa-purple);   }
        .sa-kpi-label {
            font-size:      0.78rem;
            font-weight:    700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color:          var(--sa-slate-400);
            margin:         0;
        }
        .sa-kpi-value {
            font-size:    2.8rem;
            font-weight:  800;
            color:        var(--sa-text-strong);
            margin:       0;
            line-height:  1.1;
            overflow-wrap: break-word;
        }
        .sa-kpi-sub {
            font-size: 0.84rem;
            color:     var(--sa-slate-600);
            margin:    0;
        }

        /* ── BADGE ROL PSICÓLOGO ────────────────────────────────────────── */
        .sa-psico-badge {
            display:        inline-flex;
            align-items:    center;
            gap:            6px;
            background:     var(--sa-purple-lt);
            border:         1px solid rgba(109,40,217,.2);
            color:          var(--sa-purple);
            font-size:      0.74rem;
            font-weight:    700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            border-radius:  20px;
            padding:        4px 12px;
        }
        .sa-psico-badge::before {
            content:       "●";
            font-size:     0.6rem;
        }

        /* ── BADGE DE RIESGO ────────────────────────────────────────────── */
        .sa-badge {
            display:        inline-flex;
            align-items:    center;
            gap:            6px;
            font-size:      0.76rem;
            font-weight:    700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            padding:        5px 14px;
            border-radius:  20px;
            color:          var(--sa-text-strong);
            white-space:    normal;
            line-height:    1.3;
        }
        .sa-badge::before {
            content:      "";
            display:      inline-block;
            width:        8px;
            height:       8px;
            border-radius: 50%;
            flex-shrink:  0;
        }
        .sa-badge--low    { background: var(--sa-emerald-lt); }
        .sa-badge--medium { background: var(--sa-amber-lt);   }
        .sa-badge--high   { background: var(--sa-crimson-lt); }
        .sa-badge--low::before    { background: var(--sa-emerald); }
        .sa-badge--medium::before { background: var(--sa-amber);   }
        .sa-badge--high::before   { background: var(--sa-crimson); }

        /* ── BARRA DE PROGRESO IRE ──────────────────────────────────────── */
        .sa-ire-bar-track {
            width:         100%;
            height:        7px;
            background:    var(--sa-slate-200);
            border-radius: 4px;
            overflow:      hidden;
            margin-top:    10px;
        }
        .sa-ire-bar-fill   { height: 100%; border-radius: 4px; }
        .sa-ire-bar-labels {
            display:         flex;
            justify-content: space-between;
            font-size:       0.68rem;
            color:           var(--sa-slate-400);
            margin-top:      4px;
        }

        /* ── PANEL DE ALERTA ────────────────────────────────────────────── */
        .sa-panel {
            background:    var(--sa-white);
            border:        1px solid var(--sa-slate-200);
            border-radius: var(--sa-radius);
            box-shadow:    var(--sa-shadow);
            padding:       26px 30px;
            margin:        1.2rem 0;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-panel--low    { border-top: 5px solid var(--sa-emerald); }
        .sa-panel--medium { border-top: 5px solid var(--sa-amber);   }
        .sa-panel--high   { border-top: 5px solid var(--sa-crimson); }

        .sa-panel-title {
            font-size:   1.1rem;
            font-weight: 700;
            color:       var(--sa-text-strong);
            margin:      0 0 12px 0;
        }
        .sa-panel-body {
            font-size:   0.96rem;
            color:       var(--sa-slate-600);
            line-height: 1.78;
            margin:      0 0 8px 0;
        }

        /* ── GRILLA DE RECOMENDACIONES ──────────────────────────────────── */
        .sa-rec-grid {
            display:   flex;
            flex-wrap: wrap;
            gap:       12px;
            margin-top: 18px;
        }
        .sa-rec-card {
            background:    var(--sa-slate-100);
            border-radius: var(--sa-radius-sm);
            padding:       16px 18px;
            flex:          1 1 190px;
            min-width:     165px;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-rec-title {
            font-size:   0.86rem;
            font-weight: 700;
            color:       var(--sa-text-strong);
            margin:      0 0 6px 0;
        }
        .sa-rec-body {
            font-size:   0.85rem;
            color:       var(--sa-slate-600);
            margin:      0;
            line-height: 1.68;
        }

        /* ── TARJETA DE RECURSO DE APOYO ────────────────────────────────── */
        .sa-resource-grid {
            display:   flex;
            flex-wrap: wrap;
            gap:       12px;
            margin-top: 12px;
        }
        .sa-resource-card {
            background:    var(--sa-crimson-lt);
            border:        1px solid rgba(185,28,28,.12);
            border-left:   4px solid var(--sa-crimson);
            border-radius: var(--sa-radius-sm);
            padding:       16px 18px;
            flex:          1 1 200px;
            min-width:     175px;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-resource-name {
            font-size:      0.74rem;
            font-weight:    700;
            color:          var(--sa-text-strong);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin:         0 0 5px 0;
        }
        .sa-resource-contact {
            font-size:    0.96rem;
            font-weight:  600;
            color:        var(--sa-text-strong);
            margin:       0 0 3px 0;
            overflow-wrap: break-word;
        }
        .sa-resource-extra {
            font-size: 0.80rem;
            color:     var(--sa-slate-600);
            margin:    0;
        }

        /* ── RECURSO DE APOYO — VARIANTE AMBER (riesgo medio) ───────────── */
        .sa-resource-card--amber {
            background:  var(--sa-amber-lt);
            border:      1px solid rgba(217,119,6,.15);
            border-left: 4px solid var(--sa-amber);
        }

        /* ── DESGLOSE NLP ───────────────────────────────────────────────── */
        .sa-emo-grid {
            display:       flex;
            flex-wrap:     wrap;
            gap:           9px;
            margin-bottom: 16px;
        }
        .sa-emo-item {
            background:    var(--sa-slate-100);
            border-radius: 8px;
            padding:       10px 14px;
            flex:          1 1 90px;
            text-align:    center;
            overflow:      visible;
            box-sizing:    border-box;
        }
        .sa-emo-item--hl { background: var(--sa-blue-800); }
        .sa-emo-label {
            font-size:      0.68rem;
            font-weight:    600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color:          var(--sa-slate-400);
            margin:         0 0 4px 0;
        }
        .sa-emo-value {
            font-size:   1.1rem;
            font-weight: 700;
            color:       var(--sa-text-strong);
            margin:      0;
        }
        .sa-emo-item--hl .sa-emo-label,
        .sa-emo-item--hl .sa-emo-value { color: var(--sa-white) !important; }

        /* ── AVISO INFORMATIVO ──────────────────────────────────────────── */
        .sa-info-box {
            background:  var(--sa-blue-50);
            border-left: 4px solid var(--sa-blue-400);
            border-radius: 6px;
            padding:     14px 18px;
            margin-top:  14px;
            overflow:    visible;
            box-sizing:  border-box;
        }
        .sa-info-box p {
            font-size:   0.90rem;
            color:       #1E40AF;
            margin:      0;
            line-height: 1.7;
        }

        /* ── DISCLAIMER HEADER ──────────────────────────────────────────── */
        .sa-disclaimer {
            background:    var(--sa-slate-100);
            border-radius: 8px;
            padding:       12px 18px;
            margin-bottom: 22px;
        }
        .sa-disclaimer p {
            font-size:   0.86rem;
            color:       var(--sa-slate-600);
            margin:      0;
            line-height: 1.65;
        }

        /* ── SECTION LABEL ──────────────────────────────────────────────── */
        .sa-section-label {
            font-size:      0.74rem;
            font-weight:    600;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color:          var(--sa-slate-400);
            margin:         0 0 10px 0;
        }

        /* ── TARJETA HERO AUTH ──────────────────────────────────────────── */
        .sa-auth-subtitle {
            text-align:  center;
            color:       var(--sa-slate-600);
            font-size:   0.94rem;
            line-height: 1.7;
            margin:      6px 0 20px 0;
        }

        /* ── DASHBOARD: CHIP DE PERÍODO CRÍTICO ─────────────────────────── */
        .sa-periodo-chip {
            display:        inline-flex;
            align-items:    center;
            gap:            5px;
            background:     var(--sa-crimson-lt);
            border:         1px solid rgba(185,28,28,.2);
            color:          var(--sa-crimson);
            font-size:      0.74rem;
            font-weight:    700;
            letter-spacing: 0.04em;
            border-radius:  20px;
            padding:        4px 12px;
            margin-right:   6px;
            margin-bottom:  6px;
        }
        .sa-periodo-chip--amber {
            background: var(--sa-amber-lt);
            border:     1px solid rgba(217,119,6,.2);
            color:      var(--sa-amber);
        }

        /* ── DASHBOARD: SEPARADOR DE SECCIÓN ───────────────────────────── */
        .sa-dashboard-sep {
            font-size:      0.72rem;
            font-weight:    700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color:          var(--sa-slate-400);
            border-bottom:  2px solid var(--sa-slate-200);
            padding-bottom: 6px;
            margin:         2rem 0 1.2rem 0;
        }

        /* ── NOTA PSICÓLOGO ─────────────────────────────────────────────── */
        .sa-psico-note {
            background:    var(--sa-purple-lt);
            border-left:   4px solid var(--sa-purple);
            border-radius: 6px;
            padding:       14px 18px;
            margin:        12px 0;
        }
        .sa-psico-note p {
            font-size:   0.90rem;
            color:       var(--sa-purple);
            margin:      0;
            font-weight: 500;
            line-height: 1.6;
        }

        /* ── TABLA DE HISTORIAL ─────────────────────────────────────────── */
        .stDataFrame {
            border-radius: var(--sa-radius) !important;
            overflow:      hidden           !important;
            box-shadow:    var(--sa-shadow) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# COMPONENTE: LOGO SVG SENTIA ACADEMIC · UNAL
# ==============================================================================

LOGO_SVG: str = """
<div style="display:flex;align-items:center;gap:14px;margin-bottom:8px;padding:4px 0;">
  <svg width="44" height="44" viewBox="0 0 44 44" fill="none"
       xmlns="http://www.w3.org/2000/svg" aria-label="Sentia Academic logo">
    <rect width="44" height="44" rx="11" fill="#1E3A5F"/>
    <path d="M9 26 Q13 16 22 22 Q31 28 35 16"
          stroke="#10B981" stroke-width="3"
          stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <circle cx="9"  cy="26" r="2.4" fill="#10B981"/>
    <circle cx="35" cy="16" r="2.4" fill="#10B981"/>
  </svg>
  <div style="line-height:1.2;">
    <div style="font-family:'Inter',sans-serif;font-size:1.35rem;font-weight:700;
                color:#0F2444;letter-spacing:-0.025em;">Sentia Academic</div>
    <div style="font-family:'Inter',sans-serif;font-size:0.70rem;font-weight:500;
                color:#94A3B8;letter-spacing:0.06em;text-transform:uppercase;">
      Universidad Nacional de Colombia — Bienestar Estudiantil
    </div>
  </div>
</div>
"""


# ==============================================================================
# UTILIDADES — HASH DE CONTRASEÑA
# ==============================================================================

def _hashear_password(password: str) -> str:
    """SHA-256 simple. Suficiente para demo académico; usar bcrypt en producción."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ==============================================================================
# CAPA DE PERSISTENCIA — CONEXIÓN SQLITE Y CRUD
# ==============================================================================

@st.cache_resource(show_spinner=False)
def obtener_conexion_db() -> sqlite3.Connection:
    """Crea (o reutiliza desde caché) la conexión SQLite única del proceso."""
    conexion = sqlite3.connect(DB_PATH, check_same_thread=False)
    conexion.execute("PRAGMA foreign_keys = ON;")
    return conexion


def inicializar_base_datos() -> None:
    """Crea tablas y registra la cuenta admin si aún no existen."""
    conexion = obtener_conexion_db()

    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS reportes (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            fecha             TIMESTAMP NOT NULL,
            texto             TEXT NOT NULL,
            ire               REAL NOT NULL,
            emocion_dominante TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios (id)
        )
        """
    )
    conexion.commit()

    # ── Pre-registrar cuenta del psicólogo/coordinador ─────────────────────────
    existe = conexion.execute(
        "SELECT 1 FROM usuarios WHERE username = ?", (ADMIN_USERNAME,)
    ).fetchone()
    if not existe:
        conexion.execute(
            "INSERT INTO usuarios (username, password) VALUES (?, ?)",
            (ADMIN_USERNAME, _hashear_password(ADMIN_PASSWORD_INIT)),
        )
        conexion.commit()


def registrar_usuario(username: str, password: str, confirmar: str) -> Tuple[bool, str]:
    """Valida y registra un nuevo usuario. Devuelve (éxito, mensaje)."""
    username = username.strip()
    if not username or not password:
        return False, "El usuario y la contraseña no pueden estar vacíos."
    if len(username) < 3:
        return False, "El nombre de usuario debe tener al menos 3 caracteres."
    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."
    if password != confirmar:
        return False, "Las contraseñas no coinciden."

    conexion = obtener_conexion_db()
    try:
        conexion.execute(
            "INSERT INTO usuarios (username, password) VALUES (?, ?)",
            (username, _hashear_password(password)),
        )
        conexion.commit()
        return True, "Cuenta creada con éxito. Ya puedes iniciar sesión."
    except sqlite3.IntegrityError:
        return False, "Ese nombre de usuario ya está registrado. Elige otro."
    except Exception as e:  # noqa: BLE001
        return False, f"No fue posible crear la cuenta: {e}"


def autenticar_usuario(username: str, password: str) -> Optional[Tuple[int, str]]:
    """Verifica credenciales. Devuelve (user_id, username) o None."""
    if not username or not password:
        return None
    conexion = obtener_conexion_db()
    fila = conexion.execute(
        "SELECT id, username, password FROM usuarios WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    if fila is None:
        return None
    uid, uname, pw_hash = fila
    return (uid, uname) if pw_hash == _hashear_password(password) else None


def guardar_reporte(
    user_id: int, texto: str, ire: float, emocion_dominante: str
) -> bool:
    """Inserta un nuevo reporte en la tabla 'reportes'. Devuelve True si tuvo éxito."""
    conexion = obtener_conexion_db()
    try:
        conexion.execute(
            "INSERT INTO reportes (user_id, fecha, texto, ire, emocion_dominante) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, datetime.now().isoformat(timespec="seconds"), texto, ire, emocion_dominante),
        )
        conexion.commit()
        return True
    except Exception:  # noqa: BLE001
        return False


def obtener_historial(user_id: int) -> pd.DataFrame:
    """Devuelve el historial personal del estudiante ordenado por fecha."""
    conexion = obtener_conexion_db()
    df = pd.read_sql_query(
        "SELECT fecha, texto, ire, emocion_dominante FROM reportes "
        "WHERE user_id = ? ORDER BY fecha ASC",
        conexion,
        params=(user_id,),
    )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def obtener_datos_globales() -> pd.DataFrame:
    """Devuelve TODOS los reportes de forma anónima (sin user_id ni texto)."""
    conexion = obtener_conexion_db()
    df = pd.read_sql_query(
        "SELECT fecha, ire, emocion_dominante FROM reportes ORDER BY fecha ASC",
        conexion,
    )
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def obtener_estadisticas_globales() -> Dict:
    """Calcula los KPIs globales para el dashboard del psicólogo."""
    conexion = obtener_conexion_db()

    total_eval  = conexion.execute("SELECT COUNT(*) FROM reportes").fetchone()[0] or 0
    total_estud = conexion.execute(
        "SELECT COUNT(DISTINCT user_id) FROM reportes"
    ).fetchone()[0] or 0
    ire_prom_raw = conexion.execute("SELECT AVG(ire) FROM reportes").fetchone()[0]
    ire_prom    = round(ire_prom_raw, 1) if ire_prom_raw else 0.0

    fila_emoc = conexion.execute(
        """
        SELECT emocion_dominante, COUNT(*) AS cnt
        FROM   reportes
        WHERE  emocion_dominante IN ('Tristeza', 'Miedo', 'Ira', 'Disgusto')
        GROUP  BY emocion_dominante
        ORDER  BY cnt DESC
        LIMIT  1
        """
    ).fetchone()
    emocion_top = fila_emoc[0] if fila_emoc else "Sin datos"

    return {
        "total_eval":   total_eval,
        "total_estud":  total_estud,
        "ire_promedio": ire_prom,
        "emocion_top":  emocion_top,
    }


def _cerrar_sesion() -> None:
    """Restablece el estado de sesión hacia la pantalla de login."""
    st.session_state.logged_in = False
    st.session_state.user_id   = None
    st.session_state.username  = None


# ==============================================================================
# DETECCIÓN DE ROL
# ==============================================================================

def es_psicologo() -> bool:
    """Devuelve True si el usuario logueado es el coordinador de bienestar."""
    return st.session_state.username == ADMIN_USERNAME


# ==============================================================================
# FUNCIÓN 1 — CARGA Y CACHÉ DE MODELOS NLP
# ==============================================================================

@st.cache_resource(show_spinner=False)
def cargar_modelos_nlp() -> Tuple[Optional[object], Optional[object]]:
    """Carga (y cachea) los pipelines RoBERTuito de pysentimiento.

    Modelos:
        sentiment → POS / NEU / NEG
        emotion   → joy / sadness / anger / fear / surprise / disgust / others
    """
    try:
        from pysentimiento import create_analyzer  # type: ignore

        an_sent = create_analyzer(task="sentiment", lang="es")
        an_emoc = create_analyzer(task="emotion",   lang="es")
        return an_sent, an_emoc

    except ImportError:
        st.error(
            "**Dependencia faltante:** `pysentimiento` no está instalado.\n\n"
            "Ejecuta: `pip install pysentimiento torch` y reinicia la app."
        )
        return None, None

    except OSError as e:
        st.error(
            f"**Error al leer los archivos del modelo:** {e}\n\n"
            "Verifica conexión a internet y al menos 1 GB de espacio libre."
        )
        return None, None

    except Exception as e:  # noqa: BLE001
        st.error(f"**Error inesperado al cargar modelos NLP:** {e}")
        return None, None


# ==============================================================================
# FUNCIÓN 2 — CÁLCULO DEL ÍNDICE DE RIESGO EMOCIONAL (IRE)
# ==============================================================================

def calcular_indice_riesgo(
    texto: str,
    an_sent: object,
    an_emoc: object,
) -> Tuple[float, Dict[str, float], str, str]:
    """Calcula el IRE (0–100) combinando sentimiento y emociones del texto.

    Algoritmo (sin cambios respecto a v3):
        IRE = (NEG×0.6) + (tristeza×0.45 + miedo×0.35 + ira×0.20)×0.4
        Amplificador ×1.15 si NEG>60% y emoción_riesgo>50%.
        Factor protector: −10% de la alegría detectada.
    """
    r_sent = an_sent.predict(texto)
    r_emoc = an_emoc.predict(texto)

    p_pos  = float(r_sent.probas.get("POS", 0.0))
    p_neu  = float(r_sent.probas.get("NEU", 0.0))
    p_neg  = float(r_sent.probas.get("NEG", 0.0))

    p_joy  = float(r_emoc.probas.get("joy",      0.0))
    p_sad  = float(r_emoc.probas.get("sadness",  0.0))
    p_ang  = float(r_emoc.probas.get("anger",    0.0))
    p_fea  = float(r_emoc.probas.get("fear",     0.0))
    p_sur  = float(r_emoc.probas.get("surprise", 0.0))
    p_dis  = float(r_emoc.probas.get("disgust",  0.0))

    comp_sent  = p_neg * PESO_SENTIMIENTO
    riesgo_emoc = p_sad * PESO_TRISTEZA + p_fea * PESO_MIEDO + p_ang * PESO_IRA
    comp_emoc   = riesgo_emoc * PESO_EMOCION
    bruto       = comp_sent + comp_emoc

    if p_neg > UMBRAL_AMPLIF_SENTIM and riesgo_emoc > UMBRAL_AMPLIF_EMOC:
        bruto = min(1.0, bruto * FACTOR_AMPLIF)

    ajustado = max(0.0, bruto - p_joy * PESO_FACTOR_PROTECTOR)
    ire      = round(min(100.0, ajustado * 100), 1)

    mapa_sent = {"POS": "Positivo", "NEU": "Neutro", "NEG": "Negativo"}
    mapa_emoc = {
        "joy":      "Alegría",  "sadness": "Tristeza",
        "anger":    "Ira",      "fear":    "Miedo",
        "surprise": "Sorpresa", "disgust": "Disgusto",
        "others":   "Otros",
    }

    metricas: Dict[str, float] = {
        "Sentimiento Positivo": round(p_pos * 100, 1),
        "Sentimiento Neutro":   round(p_neu * 100, 1),
        "Sentimiento Negativo": round(p_neg * 100, 1),
        "Alegría":  round(p_joy * 100, 1),
        "Tristeza": round(p_sad * 100, 1),
        "Ira":      round(p_ang * 100, 1),
        "Miedo":    round(p_fea * 100, 1),
        "Sorpresa": round(p_sur * 100, 1),
        "Disgusto": round(p_dis * 100, 1),
    }

    return (
        ire,
        metricas,
        mapa_sent.get(r_sent.output, r_sent.output),
        mapa_emoc.get(r_emoc.output, r_emoc.output),
    )


# ==============================================================================
# COMPONENTES HTML — VISUALIZACIÓN DE RESULTADOS
# ==============================================================================

def _render_tarjetas_metricas(
    indice_ire: float,
    nivel_etiqueta: str,
    nivel_clase: str,
    sentim_dominante: str,
    emocion_dominante: str,
) -> None:
    """Tarjetas métricas principales usando HTML/Flexbox (sin truncado)."""
    bar_colors = {"low": "#059669", "medium": "#D97706", "high": "#B91C1C"}
    bar_color  = bar_colors[nivel_clase]

    st.markdown(
        f"""
        <div class="sa-metric-grid">

          <!-- IRE con barra de progreso -->
          <div class="sa-metric-card sa-metric-card--ire" style="flex:1 1 230px;">
            <p class="sa-metric-label">Índice de Riesgo Emocional</p>
            <p class="sa-metric-value">{indice_ire:.1f}
              <span style="font-size:1rem;font-weight:400;color:#94A3B8;"> / 100</span>
            </p>
            <div class="sa-ire-bar-track">
              <div class="sa-ire-bar-fill"
                   style="width:{indice_ire}%;background:{bar_color};"></div>
            </div>
            <div class="sa-ire-bar-labels">
              <span>0 — Óptimo</span><span>100 — Crítico</span>
            </div>
          </div>

          <!-- Nivel de Riesgo -->
          <div class="sa-metric-card sa-metric-card--{nivel_clase}">
            <p class="sa-metric-label">Nivel de Riesgo</p>
            <p class="sa-metric-value" style="font-size:1.15rem;margin-top:6px;">
              <span class="sa-badge sa-badge--{nivel_clase}">{nivel_etiqueta}</span>
            </p>
            <p class="sa-metric-sub">Bajo (0–39) · Medio (40–69) · Alto (70–100)</p>
          </div>

          <!-- Sentimiento Dominante -->
          <div class="sa-metric-card sa-metric-card--neutral">
            <p class="sa-metric-label">Sentimiento Dominante</p>
            <p class="sa-metric-value" style="font-size:1.3rem;">{sentim_dominante}</p>
            <p class="sa-metric-sub">Positivo · Neutro · Negativo</p>
          </div>

          <!-- Emoción Dominante -->
          <div class="sa-metric-card sa-metric-card--neutral">
            <p class="sa-metric-label">Emoción Dominante</p>
            <p class="sa-metric-value" style="font-size:1.3rem;">{emocion_dominante}</p>
            <p class="sa-metric-sub">Modelo RoBERTuito — 7 categorías</p>
          </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_desglose_nlp(
    metricas: Dict[str, float], emocion_dominante: str
) -> None:
    """Desglose granular de probabilidades NLP con mini-tarjetas HTML."""

    def _hl(nombre: str) -> str:
        return "sa-emo-item--hl" if nombre == emocion_dominante else ""

    st.markdown(
        f"""
        <p class="sa-section-label">Análisis de Sentimiento</p>
        <div class="sa-emo-grid">
          <div class="sa-emo-item">
            <p class="sa-emo-label">Positivo</p>
            <p class="sa-emo-value">{metricas['Sentimiento Positivo']}%</p>
          </div>
          <div class="sa-emo-item">
            <p class="sa-emo-label">Neutro</p>
            <p class="sa-emo-value">{metricas['Sentimiento Neutro']}%</p>
          </div>
          <div class="sa-emo-item">
            <p class="sa-emo-label">Negativo</p>
            <p class="sa-emo-value">{metricas['Sentimiento Negativo']}%</p>
          </div>
        </div>

        <p class="sa-section-label">
          Análisis de Emociones
          <span style="font-weight:400;text-transform:none;letter-spacing:0;
                       font-size:0.72rem;">&nbsp;— resaltada: emoción dominante</span>
        </p>
        <div class="sa-emo-grid">
          <div class="sa-emo-item {_hl('Alegría')}">
            <p class="sa-emo-label">Alegría</p>
            <p class="sa-emo-value">{metricas['Alegría']}%</p>
          </div>
          <div class="sa-emo-item {_hl('Tristeza')}">
            <p class="sa-emo-label">Tristeza</p>
            <p class="sa-emo-value">{metricas['Tristeza']}%</p>
          </div>
          <div class="sa-emo-item {_hl('Ira')}">
            <p class="sa-emo-label">Ira</p>
            <p class="sa-emo-value">{metricas['Ira']}%</p>
          </div>
          <div class="sa-emo-item {_hl('Miedo')}">
            <p class="sa-emo-label">Miedo</p>
            <p class="sa-emo-value">{metricas['Miedo']}%</p>
          </div>
          <div class="sa-emo-item {_hl('Sorpresa')}">
            <p class="sa-emo-label">Sorpresa</p>
            <p class="sa-emo-value">{metricas['Sorpresa']}%</p>
          </div>
          <div class="sa-emo-item {_hl('Disgusto')}">
            <p class="sa-emo-label">Disgusto</p>
            <p class="sa-emo-value">{metricas['Disgusto']}%</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_tarjetas_historial(
    promedio: float, minimo: float, maximo: float, total: int
) -> None:
    """Tarjetas resumen de la vista Historial y Tendencias."""
    st.markdown(
        f"""
        <div class="sa-metric-grid">
          <div class="sa-metric-card sa-metric-card--ire">
            <p class="sa-metric-label">Promedio Histórico de IRE</p>
            <p class="sa-metric-value">{promedio:.1f}
              <span style="font-size:1rem;font-weight:400;color:#94A3B8;"> / 100</span>
            </p>
            <p class="sa-metric-sub">Calculado sobre {total} evaluación(es)</p>
          </div>
          <div class="sa-metric-card sa-metric-card--low">
            <p class="sa-metric-label">IRE Mínimo Registrado</p>
            <p class="sa-metric-value">{minimo:.1f}</p>
            <p class="sa-metric-sub">Tu mejor momento registrado</p>
          </div>
          <div class="sa-metric-card sa-metric-card--high">
            <p class="sa-metric-label">IRE Máximo Registrado</p>
            <p class="sa-metric-value">{maximo:.1f}</p>
            <p class="sa-metric-sub">Tu pico de riesgo registrado</p>
          </div>
          <div class="sa-metric-card sa-metric-card--neutral">
            <p class="sa-metric-label">Evaluaciones Totales</p>
            <p class="sa-metric-value">{total}</p>
            <p class="sa-metric-sub">Desde tu primer registro</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# FUNCIONES AUXILIARES — PANELES DE ORIENTACIÓN POR NIVEL DE RIESGO
# Requerimiento 6: Recomendaciones profundas cruzando Riesgo × Emoción
# Requerimiento 5: Canales reales UNAL en niveles Medio y Alto
# ==============================================================================

def _mostrar_alerta_riesgo_bajo(indice: float, emocion_dominante: str) -> None:
    """Panel de retroalimentación positiva y mantenimiento del bienestar (IRE 0–39)."""

    if emocion_dominante == "Tristeza":
        nota = (
            "Tu texto muestra algunos matices de tristeza, algo completamente humano y "
            "válido. Incluso dentro de un rango saludable, reconocer y nombrar estas "
            "emociones es un signo de inteligencia emocional elevada. Mantén activas tus "
            "redes de apoyo y date permiso de sentir sin juzgarte."
        )
        cards_extra = [
            ("Journaling emocional",
             "Dedica 5–10 minutos al día a escribir sobre cómo te sientes. No para "
             "resolver nada, sino para dar espacio a las emociones que van surgiendo. "
             "Esta práctica reduce la rumiación y mejora la regulación afectiva."),
            ("Conexión social activa",
             "Planifica esta semana un encuentro presencial con alguien que te genere "
             "bienestar: un amigo, familiar o compañero de confianza. La conexión humana "
             "es el regulador emocional más poderoso que existe."),
        ]
    elif emocion_dominante in ("Miedo", "Ansiedad"):
        nota = (
            "Se detectan leves trazas de preocupación en tu reflexión. Anticipar "
            "dificultades es una respuesta adaptativa completamente normal; lo esencial "
            "es no permitir que la mente construya escenarios negativos que aún no han "
            "ocurrido. Tu nivel de manejo emocional actual es saludable y funcional."
        )
        cards_extra = [
            ("Mindfulness de 5 minutos",
             "Haz una pausa consciente: cierra los ojos, siente tu respiración, "
             "observa los pensamientos sin aferrarte a ellos y devuelve la atención "
             "al presente. Prácticas cortas y consistentes son más efectivas que "
             "sesiones largas esporádicas."),
            ("Lista de certezas",
             "Cuando el miedo anticipa lo peor, anota 3 cosas que sí son ciertas y "
             "estables en tu vida ahora mismo. Este ejercicio ancla la mente en la "
             "realidad actual y reduce la activación ansiosa."),
        ]
    elif emocion_dominante == "Ira":
        nota = (
            "Tu texto refleja algo de frustración, posiblemente ante situaciones que "
            "escapan a tu control inmediato. Canalizar esa energía hacia lo que sí "
            "puedes gestionar es la estrategia más efectiva. Tu bienestar general se "
            "mantiene en un rango equilibrado y saludable."
        )
        cards_extra = [
            ("Descarga física breve",
             "Cuando la frustración aparece, 10 minutos de movimiento físico "
             "(caminar rápido, estiramientos intensos, subir escaleras) metabolizan "
             "el cortisol y la adrenalina, reduciendo la tensión emocional de forma "
             "casi inmediata."),
            ("Reformulación cognitiva",
             "Ante lo que te irrita, pregúntate: ¿Esto importará en 5 años? "
             "¿Qué parte está en mis manos cambiar ahora? Separar lo controlable "
             "de lo no controlable reduce la intensidad emocional sustancialmente."),
        ]
    else:
        nota = (
            "Tu análisis refleja un estado emocional equilibrado. Las estrategias que "
            "estás utilizando para gestionar las demandas académicas están funcionando "
            "bien. Continúa con las prácticas que te sostienen."
        )
        cards_extra = [
            ("Diario de gratitud",
             "Anota tres momentos positivos al finalizar cada día. Esta práctica "
             "entrena el cerebro para detectar recursos y posibilidades en lugar "
             "de amenazas, fortaleciendo el bienestar basal."),
            ("Momentos de flujo",
             "Identifica qué actividad académica o personal te genera estado de "
             "flujo (concentración total y disfrute). Agenda al menos una sesión "
             "semanal dedicada exclusivamente a esa actividad."),
        ]

    cards_extra_html = "".join(
        f'<div class="sa-rec-card"><p class="sa-rec-title">{t}</p>'
        f'<p class="sa-rec-body">{c}</p></div>'
        for t, c in cards_extra
    )

    st.markdown(
        f"""
        <div class="sa-panel sa-panel--low">
          <p class="sa-panel-title">
            Bienestar en equilibrio &mdash; IRE {indice:.1f} / 100
          </p>
          <p class="sa-panel-body">
            Tu Índice de Riesgo Emocional se encuentra dentro del rango saludable, lo que
            indica que estás gestionando adecuadamente las demandas de tu entorno académico.
            {nota}
          </p>
          <div class="sa-rec-grid">
            <div class="sa-rec-card">
              <p class="sa-rec-title">Sueño reparador</p>
              <p class="sa-rec-body">
                Mantén horarios regulares de sueño (7–8 h diarias). La privación crónica
                de sueño amplifica la percepción del estrés académico y deteriora la memoria,
                la concentración y la regulación emocional de forma significativa.
              </p>
            </div>
            <div class="sa-rec-card">
              <p class="sa-rec-title">Movimiento diario</p>
              <p class="sa-rec-body">
                30 minutos de actividad física al menos 3 veces por semana liberan
                endorfinas, reducen el cortisol basal y mejoran el estado de ánimo de
                forma sostenida. La UNAL cuenta con instalaciones deportivas a tu disposición.
              </p>
            </div>
            <div class="sa-rec-card">
              <p class="sa-rec-title">Vínculos sociales significativos</p>
              <p class="sa-rec-body">
                Reserva tiempo de calidad para tus amistades y familia. La conexión
                social profunda es uno de los predictores más potentes del bienestar
                psicológico sostenido a largo plazo.
              </p>
            </div>
            <div class="sa-rec-card">
              <p class="sa-rec-title">Desconexión digital</p>
              <p class="sa-rec-body">
                Establece ventanas diarias sin pantallas (especialmente antes de dormir).
                La sobrestimulación digital aumenta la activación del sistema nervioso y
                reduce la capacidad de recuperación emocional nocturna.
              </p>
            </div>
            {cards_extra_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mostrar_alerta_riesgo_medio(indice: float, emocion_dominante: str) -> None:
    """Panel de advertencia con estrategias específicas y canales UNAL (IRE 40–69)."""

    if emocion_dominante == "Tristeza":
        diagnostico = (
            "El análisis detecta una coloración de <strong>tristeza o desánimo</strong> "
            "en tu reflexión, frecuentemente asociada a sentimientos de desmotivación, "
            "pérdida de interés o sensación de no avanzar. Es fundamental que no enfrentes "
            "este estado en soledad: busca un espacio seguro para expresar lo que sientes, "
            "ya sea con alguien de confianza, mediante escritura reflexiva o con el apoyo "
            "profesional del Área de Acompañamiento Integral de Bienestar Universitario UNAL."
        )
        recs_especificas = [
            ("Activación conductual",
             "Cuando la tristeza bloquea la motivación, la acción precede al ánimo, no "
             "al revés. Elige una sola tarea pequeña y complétala. El logro mínimo genera "
             "el impulso para la siguiente acción, creando un ciclo positivo progresivo."),
            ("Escala de placer y dominio",
             "Lleva un registro de actividades diarias calificando del 1 al 5 cuánto "
             "placer o dominio te generan. Esto te ayuda a identificar qué actividades "
             "nutren tu bienestar y cuáles lo drenan, para hacer ajustes conscientes."),
            ("Rutina de autocuidado básico",
             "En momentos de tristeza, los hábitos básicos (sueño, alimentación, higiene) "
             "son los primeros en deteriorarse. Establece una rutina mínima y cúmplela "
             "independientemente de cómo te sientas. Es tu andamiaje emocional."),
        ]
    elif emocion_dominante in ("Miedo", "Ansiedad"):
        diagnostico = (
            "Se detectan señales de <strong>preocupación o ansiedad anticipatoria</strong>. "
            "Este estado es especialmente frecuente en períodos de evaluación, decisiones "
            "académicas importantes o incertidumbre sobre el futuro. La ansiedad moderada "
            "puede ser funcional, pero cuando se vuelve persistente requiere estrategias "
            "de manejo activas. El Área de Acompañamiento Integral de Bienestar UNAL "
            "ofrece talleres gratuitos de manejo del estrés y la ansiedad."
        )
        recs_especificas = [
            ("Técnica de anclaje 5-4-3-2-1",
             "Para interrumpir el ciclo de preocupación: nombra 5 cosas que ves, "
             "4 que puedes tocar, 3 que escuchas, 2 que hueles y 1 que saboreas. "
             "Ancla la atención al momento presente y detiene la cadena de pensamientos "
             "anticipatorios en menos de 3 minutos."),
            ("Preocupación programada",
             "Designa 15 minutos diarios a las 5 p.m. exclusivamente para preocuparte. "
             "Fuera de ese horario, cuando aparezca un pensamiento ansioso, anótalo y "
             "deja de atenderlo hasta tu 'ventana de preocupación'. Esto reduce la "
             "intrusión cognitiva a lo largo del día."),
            ("Cuestionamiento socrático",
             "Ante un pensamiento ansioso, pregúntate: ¿Qué evidencia real tengo? "
             "¿Cuál es la probabilidad real de que ocurra? ¿Qué haría si ocurriera? "
             "Este proceso de CBT reduce la catastrofización y ancla el pensamiento "
             "en hechos concretos."),
        ]
    elif emocion_dominante == "Ira":
        diagnostico = (
            "Tu texto refleja señales de <strong>frustración o irritabilidad elevada</strong>, "
            "a menudo relacionadas con sobrecarga académica, percepción de injusticia o "
            "expectativas no cumplidas. Esta emoción es información valiosa: señala que "
            "algo en tu situación necesita cambiar, comunicarse o reorganizarse. "
            "No abordarlo activamente puede derivar en agotamiento emocional profundo "
            "(burnout). El Acompañamiento Integral UNAL puede ayudarte a gestionar "
            "estos conflictos de forma constructiva."
        )
        recs_especificas = [
            ("Descarga física controlada",
             "La ira genera tensión muscular y cortisol. Una caminata a paso rápido de "
             "15 min, ejercicio cardiovascular o respiración profunda permiten metabolizar "
             "esa activación fisiológica antes de abordar la situación que la genera. "
             "No intentes resolver nada en el pico emocional."),
            ("Comunicación asertiva",
             "Exprésate usando frases en primera persona: 'Me siento X cuando ocurre Y, "
             "y necesito Z.' Esto permite comunicar la frustración sin acusar ni atacar, "
             "y abre espacios de diálogo constructivo con docentes, compañeros o familia."),
            ("Análisis de límites",
             "Identifica qué situaciones o compromisos estás aceptando sin querer. "
             "La ira frecuentemente señala límites sobrepasados. Practica decir 'no' "
             "de forma cordial y renegociar cargas cuando sea posible."),
        ]
    else:
        diagnostico = (
            "El análisis detecta niveles de <strong>estrés académico moderados</strong>. "
            "Es completamente normal atravesar períodos de presión; lo importante es "
            "adoptar estrategias de afrontamiento activas antes de que escale a un nivel "
            "que afecte tu salud o rendimiento. El Área de Acompañamiento Integral de "
            "Bienestar Universitario UNAL cuenta con atención personalizada y gratuita "
            "para estudiantes."
        )
        recs_especificas = [
            ("Registro emocional diario",
             "5 minutos al día anotando qué ocurrió, cómo te sentiste y cómo lo "
             "gestionaste. Esto construye consciencia emocional progresiva y te permite "
             "identificar patrones de estrés para anticiparlos y afrontarlos mejor."),
            ("Gestión de la energía",
             "Clasifica tus tareas no solo por urgencia/importancia, sino también por "
             "cuánta energía mental requieren. Realiza las más demandantes cuando tu "
             "nivel cognitivo es más alto (usualmente en las primeras horas del día)."),
            ("Descanso activo",
             "Entre sesiones de estudio, haz descansos activos: camina, estira, respira "
             "profundo. Los descansos pasivos (redes sociales) no restauran la capacidad "
             "cognitiva; los activos sí lo hacen de forma efectiva."),
        ]

    recs_html = "".join(
        f'<div class="sa-rec-card"><p class="sa-rec-title">{t}</p>'
        f'<p class="sa-rec-body">{c}</p></div>'
        for t, c in recs_especificas
    )

    st.markdown(
        f"""
        <div class="sa-panel sa-panel--medium">
          <p class="sa-panel-title">
            Estrés académico moderado detectado &mdash; IRE {indice:.1f} / 100
          </p>
          <p class="sa-panel-body">{diagnostico}</p>

          <div class="sa-rec-grid">
            {recs_html}
            <div class="sa-rec-card">
              <p class="sa-rec-title">Técnica Pomodoro</p>
              <p class="sa-rec-body">
                Trabaja 25 min &rarr; Descansa 5 min. Tras 4 ciclos, pausa de 20 min.
                Esta estructura reduce la sensación de agobio ante tareas extensas y
                mejora la concentración sostenida sin agotar los recursos cognitivos.
              </p>
            </div>
            <div class="sa-rec-card">
              <p class="sa-rec-title">Respiración diafragmática 4-4-4-4</p>
              <p class="sa-rec-body">
                Inhala 4 s &rarr; Sostén 4 s &rarr; Exhala 4 s &rarr; Pausa 4 s.
                Repite 5 veces. Activa el sistema nervioso parasimpático y reduce
                la respuesta fisiológica de estrés en menos de 3 minutos.
              </p>
            </div>
            <div class="sa-rec-card">
              <p class="sa-rec-title">Matriz de Eisenhower</p>
              <p class="sa-rec-body">
                Clasifica tus pendientes en urgente/importante. Actúa primero sobre
                lo urgente e importante, programa lo importante no urgente, y delega
                o elimina el resto. Reduce la sobrecarga perceptual de inmediato.
              </p>
            </div>
          </div>
        </div>

        <div class="sa-info-box">
          <p>
            <strong>Orientación profesional UNAL:</strong> Si estas sensaciones persisten
            más de dos semanas o afectan tu sueño, concentración o rendimiento, te
            recomendamos contactar el <strong>Área de Acompañamiento Integral</strong> de
            la Dirección de Bienestar Universitario UNAL:
            <strong>acompanamiento_bog@unal.edu.co</strong>. El servicio es gratuito,
            confidencial y diseñado específicamente para la comunidad estudiantil.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mostrar_alerta_riesgo_alto(indice: float, emocion_dominante: str) -> None:
    """Panel de alarma prioritaria con directorio completo UNAL (IRE 70–100)."""

    if emocion_dominante == "Tristeza":
        diagnostico = (
            "Tu reflexión muestra indicadores consistentes de <strong>tristeza profunda o "
            "desánimo sostenido</strong>. En el contexto académico, este patrón puede estar "
            "relacionado con agotamiento emocional, pérdida de sentido o situaciones que "
            "trascienden el ámbito universitario. Estos sentimientos son completamente "
            "válidos y merecen atención profesional. La Unidad de Salud de Bienestar "
            "Universitario UNAL y el Área de Acompañamiento Integral cuentan con "
            "psicólogos y profesionales de salud mental disponibles para ti, de forma "
            "gratuita y confidencial."
        )
        pasos = [
            ("Contacto inmediato UNAL",
             "Escribe hoy a <strong>acompanamiento_bog@unal.edu.co</strong> o visita "
             "la Dirección de Bienestar Universitario en Ciudad Universitaria. "
             "No esperes a sentirte peor: la intervención temprana marca una diferencia real."),
            ("No estés solo o sola",
             "Comparte cómo te sientes con una persona de confianza hoy mismo: "
             "familiar, amigo cercano o compañero. Verbalizar el dolor emocional "
             "ya produce un alivio significativo y rompe el ciclo de aislamiento."),
            ("Activación mínima comprometida",
             "Comprométete con una sola actividad de autocuidado básico hoy: "
             "alimentarte, salir a caminar 15 minutos, o llamar a alguien. "
             "La tristeza profunda dificulta la iniciativa; pequeños pasos "
             "consecutivos construyen el camino de regreso."),
        ]
    elif emocion_dominante in ("Miedo", "Ansiedad"):
        diagnostico = (
            "El análisis detecta señales de <strong>ansiedad elevada o angustia "
            "significativa</strong>. Este nivel de activación emocional puede generar "
            "bloqueo cognitivo, dificultades para concentrarse, insomnio y afectar tu "
            "bienestar físico y relacional. Un profesional de salud mental cuenta con "
            "herramientas clínicas específicas —como la terapia cognitivo-conductual— "
            "para ayudarte a reducir esta carga de forma segura y efectiva. La "
            "Unidad de Salud UNAL ofrece atención psicológica gratuita para estudiantes "
            "de la institución."
        )
        pasos = [
            ("Atención médica o psicológica UNAL",
             "Contacta hoy la Unidad de Salud: <strong>saludbienestar.bog@unal.edu.co</strong>. "
             "La ansiedad severa tiene tratamientos efectivos y responde bien a la "
             "intervención temprana. No normalices ni minimices lo que estás viviendo."),
            ("Técnica de respiración de emergencia",
             "En el momento de crisis: inhala durante 4 segundos por la nariz, "
             "aguanta 1 segundo y exhala lentamente durante 8 segundos por la boca. "
             "Repite 5 veces. Esto activa el nervio vago y regula el sistema nervioso."),
            ("Reduce estímulos de inmediato",
             "En las próximas horas, reduce deliberadamente las fuentes de estrés: "
             "silencia notificaciones, delega lo que puedas, y comunica a tus "
             "profesores si necesitas una prórroga. Tu salud es la prioridad."),
        ]
    elif emocion_dominante == "Ira":
        diagnostico = (
            "Tu texto refleja niveles elevados de <strong>frustración o agotamiento "
            "extremo</strong>, señalando un posible estado avanzado de burnout académico. "
            "Sostenida en el tiempo, esta emoción afecta gravemente las relaciones "
            "interpersonales, la calidad de las decisiones y la salud física. Buscar "
            "apoyo profesional ahora es la acción más inteligente que puedes tomar: "
            "el Área de Acompañamiento Integral de Bienestar UNAL está diseñada "
            "exactamente para estos momentos."
        )
        pasos = [
            ("Solicita acompañamiento UNAL hoy",
             "Envía un correo a <strong>acompanamiento_bog@unal.edu.co</strong> "
             "describiendo brevemente tu situación. El equipo de bienestar responde "
             "con rapidez y agenda citas de orientación individualizadas."),
            ("Establece un límite inmediato",
             "Identifica la fuente más aguda de tu agotamiento y elimina o reduce "
             "su intensidad esta semana, aunque sea temporalmente. La sostenibilidad "
             "a largo plazo requiere reducir la carga a niveles manejables ahora."),
            ("Descarga física supervisada",
             "Antes de cualquier conversación difícil sobre tu situación, descarga "
             "físicamente: 20 minutos de ejercicio intenso, una ducha de agua fría, "
             "o ejercicios de respiración. Actuar en el pico de la ira empeora "
             "los conflictos y las decisiones."),
        ]
    else:
        diagnostico = (
            "El análisis detecta indicadores de <strong>malestar emocional significativo</strong> "
            "que pueden estar asociados con agotamiento, ansiedad elevada o estados que "
            "requieren atención especializada. Es fundamental que no enfrentes esto en "
            "soledad. La Universidad Nacional de Colombia pone a tu disposición canales "
            "institucionales gratuitos y confidenciales para apoyarte."
        )
        pasos = [
            ("Contacta Bienestar UNAL hoy",
             "Escribe a <strong>acompanamiento_bog@unal.edu.co</strong> o visita "
             "presencialmente la Dirección de Bienestar Universitario en Ciudad "
             "Universitaria. El primer paso es el más difícil, pero el más importante."),
            ("Habla con alguien de confianza",
             "Comparte cómo te sientes con un familiar, amigo o docente hoy. "
             "El aislamiento amplifica el malestar; la conexión humana lo modera "
             "incluso cuando pareciera que nada puede ayudar."),
            ("Autocuidado de emergencia",
             "Prioriza en las próximas horas: hidratarte, comer algo, y descansar "
             "lo que puedas. Son la base fisiológica mínima desde la que tu sistema "
             "nervioso puede comenzar a regularse."),
        ]

    pasos_html = "".join(
        f'<div class="sa-rec-card"><p class="sa-rec-title">{t}</p>'
        f'<p class="sa-rec-body">{c}</p></div>'
        for t, c in pasos
    )

    # ── Panel de alarma principal ──────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="sa-panel sa-panel--high">
          <p class="sa-panel-title" style="color:#B91C1C;font-size:1.2rem;">
            Malestar emocional significativo detectado &mdash; IRE {indice:.1f} / 100
          </p>
          <p class="sa-panel-body">{diagnostico}</p>
          <p class="sa-panel-body"
             style="font-weight:700;color:#0F2444;margin-top:12px;font-size:1.0rem;">
            Pedir ayuda es un acto de fortaleza, no de debilidad.
            No estás solo o sola en esto.
          </p>
          <div class="sa-rec-grid">
            {pasos_html}
            <div class="sa-rec-card">
              <p class="sa-rec-title">Evita el aislamiento</p>
              <p class="sa-rec-body">
                Permanece en compañía de otras personas en las próximas horas. "
                La presencia de otros regula el sistema nervioso y reduce la
                intensidad del malestar emocional, incluso sin hablar de ello.
              </p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Directorio institucional UNAL completo ─────────────────────────────────
    recursos_html = "".join(
        f"""
        <div class="sa-resource-card">
          <p class="sa-resource-name">{nombre}</p>
          <p class="sa-resource-contact">{datos['contacto']}</p>
          <p class="sa-resource-extra">{datos['extra']}</p>
        </div>
        """
        for nombre, datos in RECURSOS_APOYO.items()
    )

    st.markdown(
        f"""
        <div style="margin-top:8px;">
          <p class="sa-section-label">
            Directorio Oficial — Bienestar Universitario UNAL y Líneas de Crisis
          </p>
          <div class="sa-resource-grid">{recursos_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _calcular_tendencia(ire_values: List[float]) -> Tuple[str, str]:
    """Compara mitad inicial vs. final del historial para detectar tendencia."""
    n = len(ire_values)
    if n < 2:
        return (
            "insuficiente",
            "Aún no hay suficientes registros para identificar una tendencia confiable. "
            "Completa evaluaciones periódicas —al menos una por semana— para obtener un "
            "panorama más preciso de tu evolución emocional.",
        )

    punto_medio    = max(1, n // 2)
    primera_mitad  = ire_values[:punto_medio]
    segunda_mitad  = ire_values[punto_medio:] or ire_values[-1:]
    prom_inicial   = statistics.mean(primera_mitad)
    prom_reciente  = statistics.mean(segunda_mitad)
    diferencia     = prom_reciente - prom_inicial

    if diferencia > UMBRAL_CAMBIO_TENDENCIA:
        return (
            "aumento",
            "Tu promedio de riesgo emocional ha **aumentado** en tus evaluaciones más "
            "recientes. Esto sugiere que el nivel de estrés o malestar podría estar "
            "acentuándose. Te recomendamos prestar especial atención a tus hábitos de "
            "autocuidado y considerar agendar una orientación con el Área de "
            "Acompañamiento Integral de Bienestar UNAL "
            "(acompanamiento_bog@unal.edu.co).",
        )
    elif diferencia < -UMBRAL_CAMBIO_TENDENCIA:
        return (
            "mejora",
            "Tu promedio de riesgo emocional ha **disminuido** en tus evaluaciones "
            "más recientes. Esta es una señal positiva de que las estrategias que "
            "has implementado están funcionando. Continúa con las prácticas que te "
            "han ayudado a sostener este progreso.",
        )
    else:
        return (
            "estable",
            "Tu nivel de riesgo emocional se ha mantenido relativamente **estable**. "
            "Mantener consistencia en tus hábitos de bienestar es una base sólida; "
            "continúa monitoreando tu estado para detectar a tiempo cualquier cambio.",
        )


# ==============================================================================
# GENERADOR DE DATOS DEMO — SEMESTRE UNAL (para el Dashboard del Psicólogo)
# ==============================================================================

def _generar_df_semestre_demo() -> pd.DataFrame:
    """Genera datos sintéticos de un semestre completo para la visualización.

    Simula 18 semanas con picos realistas en períodos críticos (parciales y
    finales) típicos del calendario académico de la UNAL Sede Bogotá.
    Usa semilla fija (42) para reproducibilidad.
    """
    random.seed(42)
    ahora = datetime.now()

    # (semana, IRE_base, etiqueta_periodo)
    semanas_data = [
        (1,  22, "Inicio"),       (2,  27, ""),
        (3,  31, ""),              (4,  35, ""),
        (5,  38, ""),              (6,  42, ""),
        (7,  60, "1er Parcial"),  (8,  67, "1er Parcial"),
        (9,  52, ""),              (10, 46, ""),
        (11, 44, ""),              (12, 48, ""),
        (13, 62, "2do Parcial"),  (14, 70, "2do Parcial"),
        (15, 56, ""),              (16, 72, "Finales"),
        (17, 81, "Finales"),       (18, 76, "Entregas"),
    ]

    registros = []
    for i, (sem, ire_base, periodo) in enumerate(semanas_data):
        fecha = ahora - timedelta(weeks=18 - i)
        variacion = random.uniform(-2.5, 2.5)
        ire = round(min(100.0, max(0.0, ire_base + variacion)), 1)
        registros.append({
            "Fecha":   fecha,
            "Semana":  f"Sem {sem:02d}" + (f" — {periodo}" if periodo else ""),
            "IRE Promedio (Simulado)": ire,
        })

    return pd.DataFrame(registros).set_index("Semana")


# ==============================================================================
# FUNCIÓN 3 — PANTALLA DE AUTENTICACIÓN (LOGIN / REGISTRO)
# ==============================================================================

def mostrar_pantalla_autenticacion() -> None:
    """Interfaz de login y registro centrada en pantalla."""
    _inyectar_css()

    col_izq, col_centro, col_der = st.columns([1, 2.0, 1])
    with col_centro:
        st.markdown(LOGO_SVG, unsafe_allow_html=True)
        st.markdown(
            """
            <p class="sa-auth-subtitle">
              Plataforma institucional de monitoreo del bienestar académico.<br>
              Inicia sesión o crea una cuenta para comenzar tu seguimiento personal.
            </p>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])

        # ── Pestaña: Iniciar sesión ─────────────────────────────────────────
        with tab_login:
            with st.form("form_login"):
                username_login = st.text_input("Usuario", placeholder="nombre.usuario")
                password_login = st.text_input(
                    "Contraseña", type="password", placeholder="••••••••"
                )
                enviar_login = st.form_submit_button(
                    "Ingresar", type="primary", use_container_width=True
                )

            if enviar_login:
                resultado = autenticar_usuario(username_login, password_login)
                if resultado is None:
                    st.error("Usuario o contraseña incorrectos. Inténtalo de nuevo.")
                else:
                    uid, uname = resultado
                    st.session_state.logged_in = True
                    st.session_state.user_id   = uid
                    st.session_state.username  = uname
                    st.rerun()

        # ── Pestaña: Registrarse ────────────────────────────────────────────
        with tab_registro:
            with st.form("form_registro"):
                username_reg = st.text_input(
                    "Elige un nombre de usuario", placeholder="nombre.usuario"
                )
                password_reg = st.text_input(
                    "Elige una contraseña", type="password",
                    placeholder="Mínimo 4 caracteres"
                )
                confirmar_reg = st.text_input(
                    "Confirma tu contraseña", type="password"
                )
                enviar_reg = st.form_submit_button(
                    "Crear cuenta", type="primary", use_container_width=True
                )

            if enviar_reg:
                exito, mensaje = registrar_usuario(
                    username_reg, password_reg, confirmar_reg
                )
                if exito:
                    st.success(mensaje)
                else:
                    st.error(mensaje)

        st.caption(
            "Tus credenciales se almacenan localmente y tus evaluaciones "
            "sólo son visibles para tu propia cuenta."
        )


# ==============================================================================
# FUNCIÓN 4 — NAVEGACIÓN LATERAL (SIDEBAR) — adaptada por rol
# ==============================================================================

def mostrar_sidebar_navegacion() -> str:
    """Menú lateral adaptado al rol del usuario.

    Psicólogo (admin_psico): muestra sólo el Dashboard Institucional.
    Estudiante: muestra Nueva Evaluación e Historial y Tendencias.
    """
    with st.sidebar:
        # ── Encabezado ────────────────────────────────────────────────────────
        if es_psicologo():
            st.markdown(
                f"""
                <div style="padding:4px 0 10px 0;">
                  <p style="font-weight:700;color:#0F2444;font-size:1.05rem;margin:0;">
                    Sentia Academic
                  </p>
                  <p style="color:#94A3B8;font-size:.78rem;margin:4px 0 8px 0;">
                    Sesión: <strong style="color:#1e293b;">{st.session_state.username}</strong>
                  </p>
                  <span class="sa-psico-badge">Psicólogo · Bienestar UNAL</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="padding:4px 0 14px 0;">
                  <p style="font-weight:700;color:#0F2444;font-size:1.05rem;margin:0;">
                    Sentia Academic
                  </p>
                  <p style="color:#94A3B8;font-size:.78rem;margin:3px 0 0 0;">
                    Sesión de <strong style="color:#1e293b;">{st.session_state.username}</strong>
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<hr style='margin:0 0 14px 0;'>", unsafe_allow_html=True)

        # ── Opciones de navegación por rol ────────────────────────────────────
        if es_psicologo():
            opciones = [OPCION_DASHBOARD]
        else:
            opciones = [OPCION_EVALUACION, OPCION_HISTORIAL]

        vista_seleccionada = st.radio(
            "Navegación",
            opciones,
            label_visibility="collapsed",
            key="nav_radio",
        )

        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("Cerrar sesión", use_container_width=True, type="secondary"):
            _cerrar_sesion()
            st.rerun()

    return vista_seleccionada


# ==============================================================================
# FUNCIÓN 5 — VISTA: NUEVA EVALUACIÓN (Estudiante)
# ==============================================================================

def mostrar_vista_evaluacion() -> None:
    """Vista de análisis de bienestar personal para el estudiante.

    Flujo:
      1. Logo + separador.
      2. Aviso de alcance.
      3. Área de texto (columna principal).
      4. Botón de análisis y validación.
      5. Carga de modelos NLP.
      6. Inferencia NLP + cálculo IRE.
      7. Persistencia en SQLite.
      8. Dashboard de resultados.
      9. Nota legal.
    """
    # ── Layout: columna principal + columna lateral informativa ───────────────
    col_main, col_side = st.columns([3, 1], gap="large")

    with col_main:
        st.markdown(LOGO_SVG, unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

        # 2. Aviso de alcance
        st.markdown(
            """
            <div class="sa-disclaimer">
              <p>
                <strong>Sistema preventivo y orientativo.</strong> Este análisis no
                constituye un diagnóstico clínico ni reemplaza la evaluación de un
                profesional de la salud mental. Tu reflexión se guarda únicamente en
                tu historial personal y no es visible para otros usuarios.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 3. Área de texto
        st.markdown("### Tu reflexión académica")
        st.markdown(
            "<p style='font-size:.95rem;color:#475569;margin-bottom:14px;'>"
            "Describe libremente tu estado emocional: cómo te has sentido en tus "
            "actividades académicas, qué desafíos has enfrentado y cómo los has "
            "gestionado. <em>Se recomienda un mínimo de 20 palabras para un análisis "
            "más preciso.</em>"
            "</p>",
            unsafe_allow_html=True,
        )

        texto_estudiante: str = st.text_area(
            label="Reflexión libre",
            placeholder=(
                "Esta semana ha sido muy difícil. Me siento agotado con tantos trabajos y "
                "exámenes acumulados. A veces siento que no voy a poder con todo y me "
                "cuesta mucho concentrarme..."
            ),
            height=200,
            max_chars=2000,
            label_visibility="collapsed",
            help="Escribe entre 20 y 2000 caracteres.",
        )

        if texto_estudiante:
            n_palabras = len(texto_estudiante.split())
            n_chars    = len(texto_estudiante)
            color_p    = "green" if n_palabras >= 20 else "orange"
            st.caption(f":{color_p}[{n_palabras} palabras] · {n_chars}/2000 caracteres")

        # 4. Botón de análisis
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            analizar: bool = st.button(
                "Analizar mi bienestar",
                type="primary",
                use_container_width=True,
            )

        if not analizar:
            with st.expander("¿Cómo funciona este sistema?", expanded=False):
                st.markdown(
                    "**Proceso en cuatro pasos:**\n\n"
                    "1. Escribe una reflexión libre sobre tu estado emocional académico.\n"
                    "2. El modelo RoBERTuito analiza el sentimiento y las emociones.\n"
                    "3. El sistema calcula tu **IRE** (0–100) combinando sentimiento "
                    "(60 %) y emociones (40 %).\n"
                    "4. Recibes orientación personalizada según tu nivel y emoción dominante.\n\n"
                    "Cada evaluación se guarda automáticamente en tu historial."
                )
            return

        # ── Validación ────────────────────────────────────────────────────────
        texto_limpio = texto_estudiante.strip()
        if len(texto_limpio) < 10:
            st.warning(
                "Por favor, escribe al menos algunas frases sobre tu estado actual. "
                "Cuanto más descriptivo seas, más preciso será el resultado."
            )
            return

        # 5. Carga de modelos NLP
        with st.spinner("Cargando modelos de lenguaje…"):
            an_sent, an_emoc = cargar_modelos_nlp()

        if an_sent is None or an_emoc is None:
            return

        # 6. Inferencia NLP + cálculo IRE
        with st.spinner("Analizando tu texto con inteligencia artificial…"):
            try:
                indice_ire, metricas, sentim_dom, emocion_dom = calcular_indice_riesgo(
                    texto_limpio, an_sent, an_emoc
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"**Error durante el análisis NLP:** {e}")
                return

        time.sleep(0.3)

        # 7. Persistencia
        guardado = guardar_reporte(
            st.session_state.user_id, texto_limpio, indice_ire, emocion_dom
        )

        # 8. Dashboard de resultados
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### Resultados del análisis")

        if guardado:
            st.caption("✅ Este resultado se guardó en tu historial personal.")
        else:
            st.caption("⚠️ El resultado se generó pero no pudo guardarse en tu historial.")

        # Nivel de riesgo
        if indice_ire <= IRE_BAJO_MAX:
            nivel_etiqueta, nivel_clase = "Riesgo Bajo", "low"
        elif indice_ire <= IRE_MEDIO_MAX:
            nivel_etiqueta, nivel_clase = "Riesgo Medio", "medium"
        else:
            nivel_etiqueta, nivel_clase = "Riesgo Alto", "high"

        _render_tarjetas_metricas(
            indice_ire, nivel_etiqueta, nivel_clase, sentim_dom, emocion_dom
        )

        with st.expander("Ver desglose completo del análisis NLP", expanded=False):
            _render_desglose_nlp(metricas, emocion_dom)

        st.markdown("### Orientación personalizada")

        if indice_ire <= IRE_BAJO_MAX:
            _mostrar_alerta_riesgo_bajo(indice_ire, emocion_dom)
        elif indice_ire <= IRE_MEDIO_MAX:
            _mostrar_alerta_riesgo_medio(indice_ire, emocion_dom)
        else:
            _mostrar_alerta_riesgo_alto(indice_ire, emocion_dom)

        # 9. Nota legal
        st.markdown("<hr>", unsafe_allow_html=True)
        st.caption(
            "Este análisis fue generado por un sistema automatizado de NLP con fines "
            "preventivos y orientativos únicamente. No constituye un diagnóstico clínico "
            "ni reemplaza la evaluación de un profesional de la salud mental. En caso de "
            "crisis, llama a la Línea Nacional de Salud Mental: 106 (gratuita, 24 h)."
        )

    # ── Columna lateral: tips contextuales ───────────────────────────────────
    with col_side:
        st.markdown(
            """
            <div style="margin-top:72px;">
              <p class="sa-section-label">Bienestar UNAL</p>
              <div style="background:#EFF6FF;border-radius:10px;padding:16px 18px;margin-bottom:14px;">
                <p style="font-size:.85rem;color:#1E40AF;font-weight:600;margin:0 0 6px 0;">
                  Acompañamiento Integral
                </p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  acompanamiento_bog@unal.edu.co<br>
                  Dirección de Bienestar Universitario · Ciudad Universitaria
                </p>
              </div>
              <div style="background:#ECFDF5;border-radius:10px;padding:16px 18px;margin-bottom:14px;">
                <p style="font-size:.85rem;color:#065F46;font-weight:600;margin:0 0 6px 0;">
                  Unidad de Salud UNAL
                </p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  saludbienestar.bog@unal.edu.co<br>
                  Edif. Uriel Gutiérrez
                </p>
              </div>
              <div style="background:#FEF2F2;border-radius:10px;padding:16px 18px;">
                <p style="font-size:.85rem;color:#B91C1C;font-weight:600;margin:0 0 6px 0;">
                  Línea de Crisis
                </p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  106 · Gratuita · 24 h<br>
                  018000-112-999
                </p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# FUNCIÓN 6 — VISTA: HISTORIAL Y TENDENCIAS (Estudiante) + Exportación CSV
# ==============================================================================

def mostrar_vista_historial() -> None:
    """Historial personal del estudiante con gráfico, tendencia y exportación CSV.

    Requerimiento 4: botón de descarga CSV elegante al pie del historial.
    """
    st.markdown(LOGO_SVG, unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### 📊 Historial y Tendencias")
    st.markdown(
        f"<p style='font-size:.95rem;color:#475569;margin-bottom:16px;'>"
        f"Resumen de tu evolución emocional registrada hasta hoy, "
        f"{st.session_state.username}.</p>",
        unsafe_allow_html=True,
    )

    df_hist = obtener_historial(st.session_state.user_id)

    if df_hist.empty:
        st.info(
            f"Aún no tienes evaluaciones registradas. Ve a '{OPCION_EVALUACION}' "
            "en el menú lateral para completar tu primera evaluación."
        )
        return

    promedio = float(df_hist["ire"].mean())
    minimo   = float(df_hist["ire"].min())
    maximo   = float(df_hist["ire"].max())
    total    = int(len(df_hist))

    # ── Tarjetas resumen ──────────────────────────────────────────────────────
    _render_tarjetas_historial(promedio, minimo, maximo, total)

    # ── Gráfico de evolución ──────────────────────────────────────────────────
    st.markdown("#### Evolución del IRE en el tiempo")
    datos_grafico = df_hist.set_index("fecha")[["ire"]].rename(columns={"ire": "IRE"})
    st.line_chart(datos_grafico, height=320)

    # ── Tendencia y orientación macro ─────────────────────────────────────────
    st.markdown("#### Tendencia detectada")
    clase_tend, msg_macro = _calcular_tendencia(df_hist["ire"].tolist())
    panel_clase = {
        "aumento": "high", "mejora": "low",
        "estable": "medium", "insuficiente": "medium",
    }[clase_tend]
    titulo_tend = {
        "aumento":      "Tu riesgo emocional muestra una tendencia al alza",
        "mejora":       "Tu riesgo emocional muestra una tendencia a la baja",
        "estable":      "Tu riesgo emocional se mantiene estable",
        "insuficiente": "Historial todavía insuficiente para detectar tendencia",
    }[clase_tend]

    st.markdown(
        f"""
        <div class="sa-panel sa-panel--{panel_clase}">
          <p class="sa-panel-title">{titulo_tend}</p>
          <p class="sa-panel-body">{msg_macro}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Detalle tabular ───────────────────────────────────────────────────────
    with st.expander("Ver historial detallado de evaluaciones", expanded=False):
        tabla = df_hist[["fecha", "ire", "emocion_dominante"]].copy()
        tabla = tabla.sort_values("fecha", ascending=False)
        tabla["fecha"] = tabla["fecha"].dt.strftime("%Y-%m-%d %H:%M")
        tabla = tabla.rename(columns={
            "fecha": "Fecha", "ire": "IRE", "emocion_dominante": "Emoción Dominante"
        })
        st.dataframe(tabla, use_container_width=True, hide_index=True)

    # ── Exportación CSV — Requerimiento 4 ─────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("#### Exportar historial personal")
    st.markdown(
        "<p style='font-size:.92rem;color:#475569;margin-bottom:14px;'>"
        "Descarga tu historial completo en formato CSV para consultarlo o compartirlo "
        "con un profesional de salud mental de tu confianza.</p>",
        unsafe_allow_html=True,
    )

    csv_df = df_hist[["fecha", "ire", "emocion_dominante"]].copy()
    csv_df["fecha"] = csv_df["fecha"].dt.strftime("%Y-%m-%d %H:%M")
    csv_df = csv_df.rename(columns={
        "fecha": "Fecha", "ire": "IRE", "emocion_dominante": "Emoción Dominante"
    })
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8")

    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="⬇️  Descargar historial CSV",
            data=csv_bytes,
            file_name=f"sentia_historial_{st.session_state.username}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.caption(
        "Estos datos provienen exclusivamente de tus propias evaluaciones y "
        "no se comparten con otros usuarios ni con la institución."
    )


# ==============================================================================
# FUNCIÓN 7 — VISTA: DASHBOARD INSTITUCIONAL (Psicólogo / Coordinador UNAL)
# ==============================================================================

def mostrar_dashboard_psicologo() -> None:
    """Panel de analítica macro e institucional para el Coordinador de Bienestar.

    Muestra de forma anónima y agregada:
      - 4 KPIs globales: evaluaciones totales, estudiantes activos,
        IRE promedio de la comunidad, emoción negativa más recurrente.
      - Gráfico temporal del IRE por semana (datos reales o simulados si la
        base todavía tiene pocos registros).
      - Distribución de emociones negativas registradas.
      - Chips de períodos críticos del semestre.
    """
    # ── Encabezado ─────────────────────────────────────────────────────────────
    st.markdown(LOGO_SVG, unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    col_titulo, col_badge = st.columns([3, 1])
    with col_titulo:
        st.markdown("### 🏛️ Dashboard Institucional — Bienestar Estudiantil UNAL")
    with col_badge:
        st.markdown(
            "<div style='padding-top:8px;text-align:right;'>"
            "<span class='sa-psico-badge'>Psicólogo · Coordinador Bienestar</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="sa-psico-note">
          <p>
            <strong>Vista exclusiva — Coordinador de Bienestar Universitario UNAL.</strong>
            Todos los datos se presentan de forma <strong>completamente anónima y agregada</strong>;
            no es posible identificar estudiantes individuales. Esta información tiene
            carácter orientativo para la planificación de intervenciones preventivas.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Obtener datos ──────────────────────────────────────────────────────────
    stats     = obtener_estadisticas_globales()
    df_global = obtener_datos_globales()

    # ── KPIs globales ──────────────────────────────────────────────────────────
    st.markdown(
        "<p class='sa-dashboard-sep'>Indicadores Globales — Comunidad Estudiantil</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        st.markdown(
            f"""
            <div class="sa-kpi-card sa-kpi-card--blue">
              <p class="sa-kpi-label">Evaluaciones Totales</p>
              <p class="sa-kpi-value">{stats['total_eval']:,}</p>
              <p class="sa-kpi-sub">Registros acumulados en la plataforma</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="sa-kpi-card sa-kpi-card--green">
              <p class="sa-kpi-label">Estudiantes Activos</p>
              <p class="sa-kpi-value">{stats['total_estud']:,}</p>
              <p class="sa-kpi-sub">Usuarios únicos con al menos 1 registro</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        # Color del IRE promedio según nivel
        if stats["ire_promedio"] <= IRE_BAJO_MAX:
            kpi_class = "sa-kpi-card--green"
        elif stats["ire_promedio"] <= IRE_MEDIO_MAX:
            kpi_class = "sa-kpi-card--amber"
        else:
            kpi_class = "sa-kpi-card"
            kpi_class += " sa-kpi-card--blue"  # rojo no definido; usar alerta visual

        st.markdown(
            f"""
            <div class="sa-kpi-card sa-kpi-card--amber">
              <p class="sa-kpi-label">IRE Promedio Global</p>
              <p class="sa-kpi-value">{stats['ire_promedio']:.1f}<span style="font-size:1.4rem;font-weight:400;color:#94A3B8;"> /100</span></p>
              <p class="sa-kpi-sub">Índice de Riesgo Emocional de la comunidad</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="sa-kpi-card sa-kpi-card--purple">
              <p class="sa-kpi-label">Emoción Negativa más Recurrente</p>
              <p class="sa-kpi-value" style="font-size:1.8rem;">{stats['emocion_top']}</p>
              <p class="sa-kpi-sub">Emoción de riesgo dominante en la base</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Forzar renderizado de las tarjetas KPI (que son HTML)
    st.markdown("&nbsp;", unsafe_allow_html=True)

    # ── Gráfico temporal del IRE ───────────────────────────────────────────────
    st.markdown(
        "<p class='sa-dashboard-sep'>Evolución del IRE Global — Semestre Actual</p>",
        unsafe_allow_html=True,
    )

    hay_datos_reales = not df_global.empty and len(df_global) >= 5

    if hay_datos_reales:
        # Agrupar datos reales por semana
        df_global_copia = df_global.copy()
        df_global_copia["semana_inicio"] = df_global_copia["fecha"].dt.to_period("W").dt.start_time
        df_agrupado = (
            df_global_copia
            .groupby("semana_inicio")["ire"]
            .mean()
            .reset_index()
        )
        df_agrupado.columns = ["Semana", "IRE Promedio (Real)"]
        df_agrupado = df_agrupado.set_index("Semana")

        st.line_chart(df_agrupado, height=380)
        st.caption(
            "Datos reales agregados de la plataforma, agrupados por semana. "
            "Los valores representan el IRE promedio semanal de toda la comunidad estudiantil."
        )
    else:
        # Mostrar datos simulados del semestre si no hay suficientes reales
        st.markdown(
            """
            <div class="sa-info-box" style="margin-bottom:16px;">
              <p>
                <strong>Proyección simulada:</strong> La base de datos aún no cuenta con
                suficientes registros reales (mínimo 5) para generar tendencias confiables.
                A continuación se muestra una simulación de un semestre tipo UNAL con
                picos en períodos de parciales y finales, para ilustrar el comportamiento
                esperado de la herramienta.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        df_demo = _generar_df_semestre_demo()
        st.line_chart(df_demo[["IRE Promedio (Simulado)"]], height=380)
        st.caption(
            "Simulación de 18 semanas de semestre. Picos visibles en semanas 7–8 "
            "(Primer Parcial), 13–14 (Segundo Parcial) y 16–18 (Exámenes Finales)."
        )

    # ── Chips de períodos críticos ─────────────────────────────────────────────
    st.markdown(
        """
        <div style="margin:18px 0 8px 0;">
          <p class="sa-section-label">Períodos críticos identificados en el semestre</p>
          <span class="sa-periodo-chip">🔴 Sem 7–8: Primer Parcial</span>
          <span class="sa-periodo-chip">🔴 Sem 13–14: Segundo Parcial</span>
          <span class="sa-periodo-chip">🔴 Sem 16–18: Exámenes Finales</span>
          <span class="sa-periodo-chip--amber sa-periodo-chip">🟡 Sem 1–2: Adaptación</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Distribución de emociones negativas ───────────────────────────────────
    st.markdown(
        "<p class='sa-dashboard-sep'>Distribución de Emociones Negativas Registradas</p>",
        unsafe_allow_html=True,
    )

    col_grafico_emoc, col_tabla_emoc = st.columns([2, 1], gap="large")

    with col_grafico_emoc:
        if hay_datos_reales:
            emoc_neg = df_global[
                df_global["emocion_dominante"].isin(["Tristeza", "Miedo", "Ira", "Disgusto"])
            ]["emocion_dominante"].value_counts()

            if not emoc_neg.empty:
                df_emoc_chart = emoc_neg.reset_index()
                df_emoc_chart.columns = ["Emoción", "Frecuencia"]
                df_emoc_chart = df_emoc_chart.set_index("Emoción")
                st.bar_chart(df_emoc_chart, height=300)
            else:
                st.info("No hay registros de emociones negativas suficientes aún.")
        else:
            # Datos simulados de distribución de emociones
            df_emoc_demo = pd.DataFrame({
                "Frecuencia": [42, 35, 18, 5]
            }, index=["Tristeza", "Miedo", "Ira", "Disgusto"])
            st.bar_chart(df_emoc_demo, height=300)
            st.caption("Distribución simulada — se actualizará con datos reales.")

    with col_tabla_emoc:
        st.markdown(
            """
            <div style="margin-top:12px;">
              <p class="sa-section-label">Interpretación clínica</p>
              <div style="background:#FEF2F2;border-radius:10px;padding:16px 18px;margin-bottom:12px;">
                <p style="font-size:.84rem;font-weight:700;color:#B91C1C;margin:0 0 4px 0;">Tristeza dominante</p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  Indicador de riesgo de depresión o agotamiento emocional severo.
                  Priorizar intervención temprana individual.
                </p>
              </div>
              <div style="background:#FFFBEB;border-radius:10px;padding:16px 18px;margin-bottom:12px;">
                <p style="font-size:.84rem;font-weight:700;color:#D97706;margin:0 0 4px 0;">Miedo/Ansiedad dominante</p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  Frecuente en períodos de evaluación. Indica necesidad de
                  talleres grupales de manejo del estrés y la ansiedad.
                </p>
              </div>
              <div style="background:#F5F3FF;border-radius:10px;padding:16px 18px;">
                <p style="font-size:.84rem;font-weight:700;color:#6D28D9;margin:0 0 4px 0;">Ira/Frustración dominante</p>
                <p style="font-size:.82rem;color:#475569;margin:0;line-height:1.6;">
                  Señal de burnout académico o conflictos interpersonales.
                  Recomienda orientación en habilidades de comunicación.
                </p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Registros anónimos recientes ───────────────────────────────────────────
    if hay_datos_reales:
        with st.expander(
            "Ver registros anónimos recientes (últimos 20 — sin datos identificativos)",
            expanded=False,
        ):
            tabla_anon = df_global.tail(20).copy()
            tabla_anon["fecha"] = tabla_anon["fecha"].dt.strftime("%Y-%m-%d")
            tabla_anon = tabla_anon.rename(columns={
                "fecha": "Fecha",
                "ire":   "IRE",
                "emocion_dominante": "Emoción Dominante",
            })
            st.dataframe(tabla_anon, use_container_width=True, hide_index=True)
            st.caption(
                "Los registros no incluyen nombre de usuario, código estudiantil "
                "ni el texto de la reflexión. Solo fecha, IRE y emoción dominante."
            )

    # ── Pie del dashboard ──────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption(
        "Dashboard para uso exclusivo del equipo de Bienestar Universitario UNAL. "
        "Los datos se procesan de forma anonimizada y agregada. Ningún registro "
        "individual permite identificar a un estudiante específico. "
        "Contacto institucional: sisbienestar_bog@unal.edu.co"
    )


# ==============================================================================
# PUNTO DE ENTRADA DE LA APLICACIÓN
# ==============================================================================

def main() -> None:
    """Orquesta el flujo completo de la aplicación.

    1. Inicializa la base de datos SQLite (idempotente).
    2. Inyecta el sistema de diseño CSS.
    3. Si el usuario no está autenticado → pantalla de login.
    4. Si está autenticado → detecta el rol y enruta:
       - admin_psico → Dashboard Institucional del Psicólogo.
       - Estudiante  → Nueva Evaluación o Historial y Tendencias.
    """
    inicializar_base_datos()

    if not st.session_state.logged_in:
        mostrar_pantalla_autenticacion()
        return

    _inyectar_css()
    vista_actual = mostrar_sidebar_navegacion()

    # ── Enrutamiento por rol ───────────────────────────────────────────────────
    if es_psicologo():
        mostrar_dashboard_psicologo()
    elif vista_actual == OPCION_EVALUACION:
        mostrar_vista_evaluacion()
    else:
        mostrar_vista_historial()


if __name__ == "__main__":
    main()